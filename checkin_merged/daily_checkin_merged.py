#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日签到合并推送脚本
====================
把 PTTime / 拾刻(PTSkitt) / 福利吧 三个站点的签到结果汇总成 **一条** 纯 text 消息，
经企业微信 webhook（优先）+ Server酱（兜底）推送一次。

设计：
  - 复用 pt_sign.py 的 sign_site()/format_block()（PT 站，纯标准库）
  - 复用 wnflb_checkin.py 的 do_login/check_already_signed/do_checkin/parse_result 等
    （福利吧，需 requests + ddddocr）
  - 子脚本自身的 send_notification 一律不触发（本脚本统一推一条）
  - 推送逻辑沿用 pt_sign.send_notification：webhook 纯 text 优先，失败兜底 Server酱

运行环境：必须用能 import requests / ddddocr 的 python（wnflb venv）：
  C:/Users/kaka/.workbuddy/binaries/python/envs/wnflb/Scripts/python.exe

用法：
    python daily_checkin_merged.py            # 签到 + 合并推送
    python daily_checkin_merged.py --no-push  # 只签到汇总，不推送（预览/静默）
"""
import os
import sys
import json
import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(BASE)
PT_DIR = os.path.join(PROJECT, "pt_sign")
WN_DIR = os.path.join(PROJECT, "wnflb-checkin")

sys.path.insert(0, PT_DIR)
sys.path.insert(0, WN_DIR)

import pt_sign  # noqa: E402
import wnflb_checkin as wn  # noqa: E402

# 子脚本内部不得自行推送（本脚本统一处理）
os.environ["DISABLE_PUSH"] = "1"


def run_pt():
    """跑 PT 站点，返回 [(name,status,msg,total,consec,magic,rank,magic_total), ...]"""
    cfg = pt_sign.load_config()
    raw = [pt_sign.sign_site(s) for s in cfg.get("sites", [])]
    return [r for r in raw if r[1] != "SKIP"]


def format_wnflb(status, msg, total, consec, gain, rank, credit):
    if status == "OK":
        icon, label = "✅", "成功"
    elif status in ("FAIL", "ERROR"):
        icon, label = "❌", "失败"
    else:
        icon, label = "⚠️", "异常"
    return (
        f"{icon} 福利吧 签到{label}\n"
        f"  已签到：{total} 天\n"
        f"  已连续签到：{consec} 天\n"
        f"  本次获得积分：{gain}\n"
        f"  今日签到名次：{rank}\n"
        f"  积分：{credit}\n"
        f"  （{msg}）"
    )


def run_wnflb():
    """跑福利吧，返回 (status, msg, total, consec, gain, rank, credit)"""
    import requests  # 仅 wnflb venv 有，放在函数内 import 以便隔离

    session = requests.Session()
    session.headers.update(wn.HEADERS)

    secrets_path = os.path.join(WN_DIR, "secrets.json")
    try:
        with open(secrets_path, encoding="utf-8") as f:
            sec = json.load(f)
    except Exception:
        sec = {}
    username = sec.get("username", "")
    password = sec.get("password", "")
    cookie_file = os.path.join(WN_DIR, "cookies.json")

    logged = False
    html = None
    if wn.load_cookies(session, "", cookie_file):
        logged, html = wn.verify_login(session)

    if not logged or html is None:
        if not (username and password):
            return "FAIL", "未配置账号密码", "—", "—", "—", "—", "—"
        ok, msg = wn.do_login(session, username, password)
        if not ok:
            return "FAIL", "登录失败：%s" % msg, "—", "—", "—", "—", "—"
        logged, html = wn.verify_login(session)
        if logged:
            wn.save_cookies(session, cookie_file)

    days_total, days_consec = wn.parse_wnflb_days(html or "")
    today_rank, total_credit, gain = wn.parse_wnflb_extra(html or "")

    if wn.check_already_signed(html):
        return "OK", "今日已签到", days_total, days_consec, gain, today_rank, total_credit

    formhash, fx_formhash = wn.extract_formhash(html)
    if not formhash:
        return "FAIL", "无法提取 formhash", days_total, days_consec, gain, today_rank, total_credit
    text = wn.do_checkin(session, formhash, fx_formhash)
    success, message = wn.parse_result(text)
    status = "OK" if success else "FAIL"
    return status, message, days_total, days_consec, gain, today_rank, total_credit


def main():
    if "--no-push" in sys.argv:
        os.environ["DISABLE_PUSH"] = "1"

    # —— PT 站点 ——
    pt_results = run_pt()
    pt_blocks = [pt_sign.format_block(*r) for r in pt_results]

    # —— 福利吧 ——
    wn_status, wn_msg, wn_total, wn_consec, wn_gain, wn_rank, wn_credit = run_wnflb()
    wn_block = format_wnflb(wn_status, wn_msg, wn_total, wn_consec, wn_gain, wn_rank, wn_credit)

    # —— 汇总 ——
    all_rows = [(r[0], r[1]) for r in pt_results] + [("福利吧", wn_status)]
    ok_count = sum(1 for _, s in all_rows if s == "OK")
    fail_count = sum(1 for _, s in all_rows if s in ("FAIL", "ERROR"))
    summary = "全部成功" if fail_count == 0 else ("%d 成功 / %d 失败" % (ok_count, fail_count))

    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    lines = ["📅 每日签到结果 (%s)" % date_str, "汇总：%s" % summary, ""]
    lines += pt_blocks
    lines.append("")
    lines.append(wn_block)
    content = "\n".join(lines).rstrip()
    title = "[每日签到] %s · %s" % (date_str, summary)

    print(content)

    # —— 推送（仅当非 --no-push） ——
    if "--no-push" not in sys.argv:
        os.environ.pop("DISABLE_PUSH", None)  # 允许推送
        pt_sign.send_notification(title, content)
    else:
        print("\n  (--no-push 已启用，跳过推送)")


if __name__ == "__main__":
    main()
