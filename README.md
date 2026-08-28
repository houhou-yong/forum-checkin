# 每日签到（GitHub Actions 云端版）

PTTime / PTSkit / 福利吧 三站签到 + 移动云盘签到，合并推送。

## 定时策略

| 时间（北京） | 触发方式 | 说明 |
|---|---|---|
| 05:00 | GitHub schedule | 主签到 |
| 12:10 | GitHub schedule | 补签 |
| 19:00 | EasyCron watchdog | 兜底巡检，检查当天有无成功 run |

## Workflow

- `all-checkin.yml` — 三站签到 + 移动云盘 + 汇总推送（1条消息）
- `watchdog.yml` — 19:00 巡检，未成功则自动补发

## Secrets

| 名 | 说明 |
|---|---|
| PTTIME_COOKIE | PTTime cookie |
| PTSKIT_COOKIE | PTSkit cookie |
| WNFLB_USERNAME | 福利吧账号 |
| WNFLB_PASSWORD | 福利吧密码 |
| YDYP_ACCOUNT | 移动云盘账号 |
| WECOM_WEBHOOK | 企微推送 webhook |
| SERVERCHAN_KEY | Server酱 key（兜底） |

## 注意

- 仓库为 public（免费账户 schedule 仅在公开仓库生效）
- Secrets 中的敏感信息不会因公开而泄露
- PAT 到期需更新 GitHub Secrets 和 EasyCron header
