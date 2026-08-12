#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PT 站点每日签到脚本（无第三方依赖，仅用 Python 标准库）
- 读取同目录 config.json 中已配置 cookie 的站点
- 用 cookie 访问 sign_url 完成签到
- 签到后抓取 attendance.php?type=list 解析「已签到天数 / 已连续签到天数」
- 输出结果并打印 + 追加到 sign_log.txt
- 支持随机延迟（配合 0:00 触发，使实际签到落在 0:00-0:30 窗口）
- 支持微信推送（PushPlus / Server 酱 / 企业微信群机器人），配置在 config.json 的 push 段
- 推送消息含：每站 成功/失败 + 已签到x天 + 已连续签到x天

用法：
    python pt_sign.py
"""
import json
import os
import sys
import re
import time
import random
import datetime
import urllib.request
import urllib.error
import urllib.parse

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sign_log.txt")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# 随机延迟上限（秒）：配合自动化 0:00 触发，使实际签到落在 0:00-0:30 窗口
RANDOM_DELAY_MAX = 1800


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def fetch_text(url, cookie="", referer=""):
    """GET 页面并返回去标签后的纯文本；失败返回空串。"""
    headers = {"User-Agent": UA}
    if cookie:
        headers["Cookie"] = cookie
    if referer:
        headers["Referer"] = referer
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=25) as resp:
            html = resp.read().decode("utf-8", "ignore")
        text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", text)
    except Exception:
        return ""


def parse_pt_days(text):
    """从 attendance.php?type=list 的纯文本解析 总签到 / 连续天数。"""
    total = "—"
    consec = "—"
    m = re.search(r"总签到[:：]?\s*(\d+)\s*天", text)
    if m:
        total = m.group(1)
    # 连续天数优先（列表页首条记录即当前连续）；退而求其次用「已连续签到 / 连续签到」
    m = re.search(r"连续天数[:：]?\s*(\d+)\s*天", text)
    if not m:
        m = re.search(r"已连续签到\s*(\d+)\s*天", text)
    if not m:
        m = re.search(r"连续签到\s*(\d+)\s*天", text)
    if m:
        consec = m.group(1)
    return total, consec


def parse_pt_extra(text):
    """解析 本次获得魔力 / 签到排名 / 总魔力值（best-effort，抓不到返回 —）。"""
    # 本次获得魔力：拾刻「本次签到获得 500 个魔力值」/ PTTime 列表首条「获得魔力值：200」
    magic_gain = "—"
    m = re.search(r"本次签到获得\s*(\d+)\s*个魔力值", text)
    if not m:
        m = re.search(r"获得魔力值[:：]?\s*(\d+)", text)
    if m:
        magic_gain = m.group(1)
    # 签到排名：拾刻「今日签到排名：611 / 2859」/ 福利吧风格「今日第 X 个签到」
    rank = "—"
    m = re.search(r"今日签到排名[:：]?\s*(\d+)\s*/\s*(\d+)", text)
    if not m:
        m = re.search(r"今日第\s*(\d+)\s*个签到", text)
    if m:
        if m.re.groups == 2:
            rank = "%s/%s" % (m.group(1), m.group(2))
        else:
            rank = "第%s个" % m.group(1)
    # 总魔力值：资料页/列表页「魔力值: 46796.6」
    total_magic = "—"
    m = re.search(r"魔力值.*?(\d[\d,]+\.\d+)", text)
    if m:
        total_magic = m.group(1).replace(",", "")
    return magic_gain, rank, total_magic


def sign_site(site):
    name = site.get("name", "未命名")
    url = (site.get("sign_url") or "").strip()
    cookie = (site.get("cookie") or "").strip()

    if not url:
        return name, "SKIP", "未配置 sign_url（暂不参与自动签到）", "—", "—", "—", "—", "—"
    if not cookie:
        return name, "SKIP", "未配置 cookie", "—", "—", "—", "—", "—"

    headers = {"Cookie": cookie, "User-Agent": UA, "Referer": site.get("base_url", url)}
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = resp.read().decode("utf-8", "ignore")
        text = data.lower()
        if ("已签到" in data) or ("签到成功" in data) or ("attended" in text) or ("sign in success" in text):
            status, msg = "OK", "签到成功 / 今日已签到"
        elif ("请先登录" in data) or ("未登录" in data) or ("login" in text and "not" in text):
            return name, "FAIL", "cookie 失效，请重新获取后填入 config.json", "—", "—"
        else:
            status, msg = "UNKNOWN", "已访问，需人工确认页面内容 -> " + data[:160].replace("\n", " ")

        # 签到成功/已访问后，抓列表页解析天数与魔力/排名（best-effort）
        total, consec = "—", "—"
        magic_gain, rank, total_magic = "—", "—", "—"
        if status in ("OK", "UNKNOWN"):
            list_url = url.rsplit("/", 1)[0] + "/attendance.php?type=list"
            list_text = fetch_text(list_url, cookie, site.get("base_url", url))
            if list_text:
                total, consec = parse_pt_days(list_text)
                magic_gain, rank, total_magic = parse_pt_extra(list_text)
        return name, status, msg, total, consec, magic_gain, rank, total_magic
    except urllib.error.HTTPError as e:
        return name, "ERROR", "HTTP %s: %s" % (e.code, e.reason), "—", "—", "—", "—", "—"
    except Exception as e:
        return name, "ERROR", str(e), "—", "—", "—", "—", "—"


def push_http(url, payload, is_json=True):
    data = json.dumps(payload).encode("utf-8") if is_json else payload
    headers = {"Content-Type": "application/json; charset=utf-8"} if is_json else \
        {"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"}
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception as e:
        return "ERR:%s" % e


def push_wecom_app(content, app):
    """企业微信自建应用消息（可推送到个人微信，需配合微信插件）。"""
    if not isinstance(app, dict):
        return
    corpid = (app.get("corpid") or "").strip()
    secret = (app.get("corpsecret") or "").strip()
    agentid = (app.get("agentid") or "").strip()
    userid = (app.get("userid") or "").strip()
    if not (corpid and secret and agentid and userid):
        print("  [企业微信应用] 未配置(corpid/secret/agentid/userid)，跳过")
        return
    try:
        with urllib.request.urlopen(
            "https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=%s&corpsecret=%s" % (corpid, secret),
            timeout=10,
        ) as r:
            tk = json.loads(r.read().decode("utf-8", "ignore"))
        if tk.get("errcode", 0) != 0:
            print("  [企业微信应用] 获取token失败: %s" % tk.get("errmsg"))
            return
        token = tk["access_token"]
        payload = {
            "touser": userid,
            "msgtype": "markdown",
            "agentid": int(agentid),
            "markdown": {"content": content},
        }
        req = urllib.request.Request(
            "https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=%s" % token,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            res = json.loads(r.read().decode("utf-8", "ignore"))
        print("  [企业微信应用] %s" % res.get("errmsg"))
    except Exception as e:
        print("  [企业微信应用] 发送失败: %s" % e)


def send_notification(title, content):
    """推送策略：主通道=企业微信 webhook（纯 text）；
    若 webhook 未配置或发送失败，则兜底走 Server酱。
    保证只推送一份（不重复发到多个通道）。"""
    if os.environ.get("DISABLE_PUSH", "").strip().lower() in ("1", "true", "on"):
        print("  (推送已禁用 DISABLE_PUSH，跳过)")
        return
    cfg = load_config()
    push = cfg.get("push", {}) if isinstance(cfg, dict) else {}
    webhook = (push.get("wecom_webhook") or "").strip()
    key = (push.get("serverchan_key") or "").strip()

    # —— 主通道：企业微信 webhook 纯 text ——
    ok = False
    if webhook:
        r = push_http(webhook, {"msgtype": "text", "text": {"content": content}}, is_json=True)
        print("  [企业微信] %s" % r[:160])
        # 发送成功判定：HTTP 正常返回且 errcode 为 0
        # （异常时 push_http 返回 "ERR:..." 前缀；errcode!=0 视为失败触发兜底）
        ok = (not r.startswith("ERR")) and ("errcode" in r) and \
             ('"errcode":0' in r or '"errcode": 0' in r)
    else:
        print("  (未配置企业微信 webhook，跳过主通道)")

    # —— 兜底通道：主通道失败或未配置时走 Server酱 ——
    if not ok:
        if key:
            body = urllib.parse.urlencode({"title": title, "desp": content}).encode("utf-8")
            r = push_http("https://sctapi.ftqq.com/%s.send" % key, body, is_json=False)
            print("  [Server酱-兜底] %s" % r[:160])
        else:
            print("  (主通道失败且未配置 Server酱，无法兜底)")


def random_sleep():
    sec = random.randint(0, RANDOM_DELAY_MAX)
    print("[调度] 随机延迟 %d 秒（自动化 0:00 触发，使签到落在 0:00-0:30 窗口）" % sec)
    if sec > 0:
        time.sleep(sec)


def format_block(name, status, msg, total, consec, magic_gain="—", rank="—", total_magic="—"):
    if status == "OK":
        icon = "✅"
    elif status == "FAIL" or status == "ERROR":
        icon = "❌"
    else:
        icon = "⚠️"
    return ("%s %s 签到%s\n"
            "  已签到：%s 天\n"
            "  已连续签到：%s 天\n"
            "  本次获得魔力：%s\n"
            "  签到排名：%s\n"
            "  魔力值：%s\n"
            "  （%s）" % (icon, name, "成功" if status == "OK" else "失败",
                         total, consec, magic_gain, rank, total_magic, msg))


def main():
    if "--no-push" in sys.argv:
        os.environ["DISABLE_PUSH"] = "1"
    random_sleep()
    try:
        cfg = load_config()
    except Exception as e:
        print("读取 config.json 失败: %s" % e)
        return

    raw = [sign_site(s) for s in cfg.get("sites", [])]
    # 过滤掉 SKIP（如福利吧，由另一脚本独立处理），只汇报真正参与的 PT 站
    results = [r for r in raw if r[1] != "SKIP"]

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    date_str = now.split()[0]

    ok_count = sum(1 for r in results if r[1] == "OK")
    fail_count = sum(1 for r in results if r[1] in ("FAIL", "ERROR"))
    summary = "全部成功" if fail_count == 0 else ("%d 成功 / %d 失败" % (ok_count, fail_count))

    lines = ["📅 PT 站点每日签到 (%s)" % date_str, "汇总：%s" % summary, ""]
    for name, status, msg, total, consec, magic_gain, rank, total_magic in results:
        lines.append(format_block(name, status, msg, total, consec, magic_gain, rank, total_magic))
        lines.append("")
    out = "\n".join(lines).rstrip()

    print(out)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(out + "\n\n")
    except Exception:
        pass

    send_notification("[PT签到] %s · %s" % (date_str, summary), out)


if __name__ == "__main__":
    main()
