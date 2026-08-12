# 每日三站签到合并推送（GitHub Actions 云端版）

把 PTTime / 拾刻(PTSkitt) / 福利吧 三站签到结果合并成**一条**纯 text，经企业微信 webhook（主）+ Server酱（兜底）推送。
脚本跑在 GitHub Actions 云端，**无需开电脑**，每天北京时间 07:00 自动执行。

> 说明：原脚本来自本地 `pt_sign/` + `wnflb-checkin/` + `checkin_merged/`，本仓库将其原样打包，仅把**密钥外置成 GitHub Secrets**，运行时由 `prepare_env.py` 生成 `config.json` / `secrets.json`，真实密钥永不入库。

---

## 目录结构

```
checkin_cloud/
├── .github/workflows/daily-checkin.yml   # 定时任务（UTC 23:00 = 北京 07:00）
├── prepare_env.py                         # 从 Secrets 生成运行时配置
├── requirements.txt                        # requests + ddddocr
├── .gitignore                              # 忽略生成的 config.json / secrets.json / cookies.json
├── pt_sign/
│   ├── pt_sign.py                          # 核心脚本（未改）
│   └── config.template.json                # 模板（cookie 为空，由 Secrets 填）
├── wnflb-checkin/
│   ├── wnflb_checkin.py                     # 核心脚本（未改，含 ddddocr 验证码识别）
│   └── secrets.template.json               # 模板（账号密码为空）
└── checkin_merged/
    └── daily_checkin_merged.py             # 合并三站 + 推送（未改）
```

---

## 部署步骤（一次性）

### 1. 建私有仓库
在 GitHub 新建一个 **Private** 仓库（如 `forum-checkin`），把本目录内容 push 上去：

```bash
cd checkin_cloud
git init
git add .
git commit -m "init: cloud checkin"
git remote add origin git@github.com:<你的用户名>/forum-checkin.git
git push -u origin main
```

> 必须 Private：虽然仓库里没有明文密钥，但仓库地址/结构仍不宜公开；且 Actions 日志可能泄露部分页面文本。

### 2. 配置 6 个 Secrets
仓库 `Settings → Secrets and variables → Actions → New repository secret`，逐个添加：

| Secret 名 | 取值来源 |
|---|---|
| `PTTIME_COOKIE` | 本地 `pt_sign/config.json` 里 PTTime 的 `cookie` 整串 |
| `PTSKIT_COOKIE` | 本地 `pt_sign/config.json` 里 拾刻 的 `cookie` 整串 |
| `WNFLB_USERNAME` | 福利吧账号（本地 `wnflb-checkin/secrets.json` 的 `username`） |
| `WNFLB_PASSWORD` | 福利吧密码（本地 `secrets.json` 的 `password`） |
| `WECOM_WEBHOOK` | 企业微信群机器人 Webhook（本地 config.json 的 `push.wecom_webhook`） |
| `SERVERCHAN_KEY` | Server酱 key（本地 config.json 的 `push.serverchan_key`，兜底用） |

> PT 站 cookie 会过期，失效时 Actions 日志会报 `cookie 失效`——届时更新对应 Secret 即可。

### 3. 开启并验证
- 仓库 `Actions` 标签页 → 找到 `每日三站签到合并推送` → 点 `Run workflow` 手动跑一次，看日志确认三站成功 + 微信收到推送。
- 之后每天北京 07:00 自动跑（GitHub Actions 定时为 best-effort，可能延迟几分钟，签到幂等无害）。

---

## 本地调试（不用 GitHub）
```bash
cd checkin_cloud
export PTTIME_COOKIE="..." PTSKIT_COOKIE="..." WNFLB_USERNAME="..." WNFLB_PASSWORD="..."
export WECOM_WEBHOOK="..." SERVERCHAN_KEY="..."
python prepare_env.py
python checkin_merged/daily_checkin_merged.py --no-push   # 只合并不推送预览
```

---

## 注意事项
- **福利吧**：云端每次用账号密码 + `ddddocr` 自动识别验证码重新登录（不依赖本地 cookie 缓存），最稳。
- **PT 站**：靠 cookie，云端无持久 cookie，需你定期更新 `PTTIME_COOKIE` / `PTSKIT_COOKIE` 两个 Secret。
- **推送**：主通道企业微信 webhook 成功则只推一条；失败自动兜底 Server酱。
- 免费额度足够（每日约 1 分钟，远在 2000 分钟/月之内）。
