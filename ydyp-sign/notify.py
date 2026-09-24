# -*- coding: utf-8 -*-
"""青龙兼容 notify.py：把 send(title, content) 桥接到双通道：
1) 个人微信（Server酱，需 config.json 配 push.serverchan_key）
2) 企业微信群机器人（push.wecom_webhook，text 格式）
配置读取同目录 config.json 的 push 段。"""
import json
import os
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent


def _load_push():
    if os.environ.get("YDYP_NO_PUSH", "").strip().lower() in ("1", "true", "on"):
        return {}
    try:
        cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
        return cfg.get("push", {}) or {}
    except Exception:
        return {}


def _send_serverchan(key, title, content):
    try:
        resp = requests.post(
            f"https://sctapi.ftqq.com/{key}.send",
            data={"title": title, "desp": content},
            timeout=15,
        )
        data = resp.json()
        if data.get("code") == 0:
            print("📨 Server酱推送: ok")
        else:
            print(f"⚠️ Server酱推送异常: {data}")
    except Exception as exc:
        print(f"⚠️ Server酱推送失败: {exc}")


def send(title, content):
    """青龙面板风格的通知入口，title/content 均为字符串。推 Server酱 + 企微。"""
    prefix = os.environ.get("YDYP_NOTIFY_PREFIX", "")
    if prefix:
        title = prefix + title
        content = prefix + content
    push = _load_push()
    text = content or ""

    serverchan_key = (push.get("serverchan_key") or "").strip()
    if serverchan_key:
        _send_serverchan(serverchan_key, title, text)
    else:
        print("⚠️ 未配置 serverchan_key，跳过 Server酱推送")

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
    send("测试通知", "ydyp_sign notify.py 推送链路测试（Server酱 + 企微）")
