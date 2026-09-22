# -*- coding: utf-8 -*-
"""移动云盘签到启动器：读 config.json 的 accounts -> 设 ydyp 环境变量 -> 跑 ydyp.py。
用法: python run_ydyp.py

返回码约定（供 GitHub Actions 重试/通知判断）：
  0 = 成功（输出含"签到成功"且无"失效账号"）
  1 = 失败（账号失效 / 签到失败 / 异常）
"""
import json
import os
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "config.json"

FAIL_KEYWORDS = ("失效账号", "ck可能失效", "登录失败")


def main():
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    accounts = [a.strip() for a in (cfg.get("accounts") or []) if a and a.strip()]
    if not accounts:
        print("⛔️ config.json 中 accounts 为空，请填入 Authorization值#手机号")
        return 1

    env = os.environ.copy()
    env["ydyp"] = "&".join(accounts)
    print(f"📱 共 {len(accounts)} 个账号，开始执行 ydyp.py ...")
    proc = subprocess.run(
        [sys.executable, str(BASE / "ydyp.py")],
        env=env,
        cwd=str(BASE),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    # 回显完整输出，便于 Actions 日志排查
    print(out)

    ok_mark = ("签到成功" in out) or ("已签到" in out)
    fail_hit = any(k in out for k in FAIL_KEYWORDS)
    if ok_mark and not fail_hit:
        return 0
    if proc.returncode != 0:
        return proc.returncode
    return 1


if __name__ == "__main__":
    sys.exit(main())
