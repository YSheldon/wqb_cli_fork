# wqb_cli fork — sqlitesimu 补丁

本目录是 site-packages 里 `wqb_cli` 的完整快照，外加两处补丁。
快照基线：2026-10-26 的 `Python313\Lib\site-packages\wqb_cli`。

## 改了什么

### 1. `sqlitesimu/runtime.py` — 并发槽上限 4

`_step()` 在新建/提交 simulate batch 之前检查在途批次
（状态 `SIMULATING / POLLING / CHILD_POLLING`），满 4 个就跳过本轮，
等下一轮空闲再试。轮询、child 轮询、enrich 不受限。

动机：BRAIN 账号级并发墙。单 run 的在途 batch 不设限会一路打满
GLB ≤ 4 的账号上限；工具自己先限到 4，429 就只剩账号真满的情况。
多进程同时 resume 各自 ≤4 仍会叠加，跨进程要另外加账号级闸（方案 B）。

### 2. `sqlitesimu/db.py` — checks 去重

`/alphas/{id}` 会对同一 check 名（如 `MATCHES_THEMES`）返回多条记录，
原代码直接 INSERT 触发 `UNIQUE(alpha_id, name)` 崩掉 worker。
现在同名只取第一条。

## 怎么用

升级/重装 wqb_cli 后重放补丁：

```cmd
python E:\Work\WorldQuant-Brain-Alpha\wqb_cli_fork\reapply_patches.py
```

幂等：已打补丁跳过，锚点丢失会报 `ANCHOR NOT FOUND` 并退出码 1。
快照目录本身已是补丁后状态。

## 验证

- `run_af8a23907c9d452dbd680ea0d35a4037`（1200 条 F1c）在 4 槽下运行。
- 查询在途槽：
  `sqlite3 ... "SELECT state, COUNT(*) FROM simulation_batches WHERE run_id='<run>' AND state IN ('SIMULATING','POLLING','CHILD_POLLING') GROUP BY state;"`
