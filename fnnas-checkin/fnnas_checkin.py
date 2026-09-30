#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""飞牛私有云论坛（club.fnnas.com）「天天打卡」自动签到。

Discuz 插件 zqlj_sign：
  1) GET  plugin.php?id=zqlj_sign            -> 页面里有打卡链接 <a href="...&sign=XXXX">点击打卡</a>
  2) GET  plugin.php?id=zqlj_sign&sign=XXXX  -> 完成打卡
  3) 复核：再看一次插件页，打卡按钮消失 = 成功

凭据：cookies（JSON，由技能 browser-cookie-capture 导出；用 --cookies 指定）
推送：企业微信 webhook（--webhook 或 env WECOM_WEBHOOK）

⚠️ 论坛打卡公告：「请勿使用插件打卡，异常打卡经核实，将会扣除飞牛币。」
   本脚本按“真人点一次的等价请求”实现（同 IP、带 Referer/UA、每天仅 1 次），但风险请自担。
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta

HOME = "https://club.fnnas.com"
SIGN_PAGE = HOME + "/plugin.php?id=zqlj_sign"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")

TAG = "GitHub" if os.environ.get("GITHUB_ACTIONS") else ("飞牛" if os.name == "posix" else "本地")


def log(msg):
    print(msg, flush=True)


def load_cookie_header(path):
    d = json.load(open(path, encoding="utf-8"))
    cks = d.get("cookies", d if isinstance(d, list) else [])
    parts = ["%s=%s" % (c["name"], c["value"])
             for c in cks if "fnnas.com" in (c.get("domain") or "")]
    return "; ".join(parts)


def http_get(url, cookie, referer=None):
    import urllib.request
    headers = {
        "User-Agent": UA,
        "Cookie": cookie,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Connection": "keep-alive",
    }
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace"), r.status


def signed_already(html):
    return ("您今天已经打过卡" in html) or ("今天已经打卡" in html) or ("已打卡，请明天再来" in html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cookies", required=True, help="browser-cookie-capture 导出的 cookie JSON")
    ap.add_argument("--webhook", default=os.environ.get("WECOM_WEBHOOK", ""))
    ap.add_argument("--no-push", action="store_true")
    args = ap.parse_args()

    cookie = load_cookie_header(args.cookies)
    if not cookie:
        log("ERROR: cookie 为空（确认 JSON 里有 fnnas.com 的 cookie）")
        return 1

    log("=" * 50)
    log("飞牛论坛打卡 START %s  tag=%s" % (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), TAG))

    # 1) 取插件页
    try:
        html, http = http_get(SIGN_PAGE, cookie)
    except Exception as e:
        log("插件页请求失败: %s" % e)
        return fail(args, "插件页请求失败：%s" % e)

    if "action=logout" not in html:
        msg = "未登录 / cookie 已失效（页面无退出链接）→ 需重新抓 cookie"
        log(msg)
        return fail(args, msg)

    m = re.search(r'href="(plugin\.php\?id=zqlj_sign(?:&amp;|&)sign=[0-9a-zA-Z]+)"[^>]*>\s*[^<]*打卡', html)
    if not m:
        if signed_already(html):
            log("今日已打卡（无需重复）")
            return ok(args, "☑️ 今日已打卡（无需重复）")
        # 找不到打卡按钮、也没明确"已打卡"文案 —— 报告原文片段便于排查
        log("未找到打卡按钮，且无已打卡文案（可能站点改版）")
        return fail(args, "未找到打卡入口（站点可能改版或需人机验证）")

    sign_path = m.group(1).replace("&amp;", "&")
    log("打卡链接: %s" % sign_path)

    # 2) 执行打卡（带 Referer，模拟真人点击）
    try:
        html2, http2 = http_get(HOME + "/" + sign_path, cookie, referer=SIGN_PAGE)
    except Exception as e:
        log("打卡请求异常: %s" % e)
        return fail(args, "打卡请求异常：%s" % e)

    # 3) 复核
    coin = re.search(r"飞牛币[^\d]{0,6}(\d+)", html2)
    success_kw = any(k in html2 for k in ("打卡成功", "签到成功", "获得", "恭喜"))
    try:
        html3, _ = http_get(SIGN_PAGE, cookie)
        gone = not re.search(r"sign=[0-9a-zA-Z]+\"[^>]*>\s*[^<]*打卡", html3)
    except Exception:
        gone = False

    if success_kw or gone:
        extra = ("，+%s 飞牛币" % coin.group(1)) if coin else ""
        log("✅ 打卡成功%s" % extra)
        return ok(args, "✅ 打卡成功%s" % extra)
    if signed_already(html2):
        log("今日已打卡")
        return ok(args, "☑️ 今日已打卡（无需重复）")
    log("打卡结果未确认（可能需要人机验证）")
    return fail(args, "❌ 打卡结果未确认（站点可能弹了人机验证）")


def push(args, text):
    if args.no_push or not args.webhook:
        return
    import urllib.request
    ts = (datetime.utcnow() + timedelta(hours=8)).strftime("%m-%d %H:%M")
    content = "【%s】飞牛论坛 天天打卡\n时间：%s\n结果：%s" % (TAG, ts, text)
    body = json.dumps({"msgtype": "text", "text": {"content": content}}).encode("utf-8")
    req = urllib.request.Request(args.webhook, data=body, headers={"Content-Type": "application/json"})
    try:
        print("push:", urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore"))
    except Exception as e:
        print("push failed:", e)


def ok(args, text):
    push(args, text)
    return 0


def fail(args, text):
    push(args, text)
    return 1


if __name__ == "__main__":
    sys.exit(main())
