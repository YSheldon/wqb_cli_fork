# wqb_cli fork — sqlitesimu 4-slot patch (on official 0.6.1)

本目录跟踪官方 `untuitivist/wqb_cli`，基线 **v0.6.1**（2026-09-25, commit `0726a66`），
外加一处本地补丁。快照目录 `wqb_cli/` 不进 git（187MB 官方资源 + 含账号数据的
`local/`），仓库只保留可审的补丁与说明。

## 与官方 0.6.1 的差异

### `sqlitesimu/runtime.py` — 并发槽上限 4

`_step_simulation()` 在取新 simulate batch 前检查在途批次
（状态 `SIMULATING / POLLING / CHILD_POLLING`），满 4 个直接跳过本轮。
轮询、child 轮询、enrich 不受限。

动机：BRAIN 账号级并发墙（GLB ≤ 4）。官方 0.6.1 依旧"客户端不设槽、
靠 429 背压"，多 result/enrichment 线程只并行读结果；simulation lane
是单线程，本补丁线程安全。

注意：多进程同时 resume 各自 ≤4 仍会叠加，跨进程需要账号级闸（方案 B）。

## 旧补丁去哪了

0.4.0 时代的 `alpha_checks` 去重补丁**已废弃**：官方 v6 schema 把
`alpha_checks` 主键从 `(alpha_id, name)` 改为 `(alpha_id, ordinal)`，
同名 check（如两条 `MATCHES_THEMES`）按行号多行存储，不再撞 UNIQUE。

## 使用

升级/重装 wqb_cli 0.6.1 后重放补丁：

```cmd
python reapply_patches.py
```

幂等：已打补丁跳过，锚点丢失报 `ANCHOR NOT FOUND` 并退出码 1。
仅适配 0.6.1 runtime；升级更高版本需重新对锚点。

## 0.6.1 数据外发审查结论（2026-10-26）

出站仅 WorldQuant 自有三域：`api.worldquantbrain.com`、
`support.worldquantbrain.com`、`worldquantbrain.zendesk.com`（SSO 白名单，
带严格 origin 校验）。无 telemetry/analytics/sentry/webhook，无 aiohttp/httpx/
raw socket。`.NOTE.md` 为作者调试笔记，多处声明发布物排除本地数据库、
凭据与 cookie，写路径从未 live 执行。
