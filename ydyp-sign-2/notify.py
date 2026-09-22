# -*- coding: utf-8 -*-
"""青龙兼容 notify.py：把 send(title, content) 只桥接到企业微信群机器人（text 格式）。
配置读取同目录 config.json 的 push 段。"""
import json
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent


def _load_push():
    try:
        cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
        return cfg.get("push", {}) or {}
    except Exception:
        return {}


def send(title, content):
    """青龙面板风格的通知入口，title/content 均为字符串。只推企业微信群。"""
    push = _load_push()
    text = content or ""

    webhook = (push.get("wecom_webhook") or "").strip()
    if webhook:
        try:
            resp = requests.post(
                webhook,
                json={"msgtype": "text", "text": {"content": f"{title}\n{text}"}},
                timeout=15,
            )
            print(f"📨 企微推送: {resp.json().get('errmsg')}")
        except Exception as exc:
            print(f"⚠️ 企微推送失败: {exc}")
    else:
        print("⚠️ 未配置企业微信 webhook，跳过推送")


if __name__ == "__main__":
    send("测试通知", "ydyp_sign notify.py 推送链路测试（仅企微）")
