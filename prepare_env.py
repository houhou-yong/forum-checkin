#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云端运行时配置生成器（不进版本库密钥）
=====================================
从 GitHub Secrets（以环境变量注入）生成：
  - pt_sign/config.json     （PT 站 cookie + 推送通道）
  - wnflb-checkin/secrets.json （福利吧账号密码）

这样仓库里只提交模板（空密钥），真实密钥永远不落盘到 git。
本地调试也可：把下面 6 个变量 export 后跑本脚本即可。
"""
import os
import json

ROOT = os.path.dirname(os.path.abspath(__file__))
PT_DIR = os.path.join(ROOT, "pt_sign")
WN_DIR = os.path.join(ROOT, "wnflb-checkin")


def main():
    pttime_cookie = os.environ.get("PTTIME_COOKIE", "").strip()
    ptskit_cookie = os.environ.get("PTSKIT_COOKIE", "").strip()
    wecom = os.environ.get("WECOM_WEBHOOK", "").strip()
    serverchan = os.environ.get("SERVERCHAN_KEY", "").strip()

    config = {
        "sites": [
            {
                "name": "PTTime",
                "base_url": "https://www.pttime.org",
                "sign_url": "https://www.pttime.org/attendance.php",
                "cookie": pttime_cookie,
            },
            {
                "name": "拾刻(PTSkitt)",
                "base_url": "https://www.ptskit.org",
                "sign_url": "https://www.ptskit.org/attendance.php",
                "cookie": ptskit_cookie,
            },
        ],
        "push": {
            "wecom_webhook": wecom,
            "serverchan_key": serverchan,
        },
    }
    with open(os.path.join(PT_DIR, "config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    un = os.environ.get("WNFLB_USERNAME", "").strip()
    pw = os.environ.get("WNFLB_PASSWORD", "").strip()
    secrets = {"username": un, "password": pw}
    with open(os.path.join(WN_DIR, "secrets.json"), "w", encoding="utf-8") as f:
        json.dump(secrets, f, ensure_ascii=False, indent=2)

    print("[prepare_env] 已从环境变量生成 pt_sign/config.json 与 wnflb-checkin/secrets.json")


if __name__ == "__main__":
    main()
