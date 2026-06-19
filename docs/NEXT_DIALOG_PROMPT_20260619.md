# AIdeal CPS / 智省优选 — DL2 新对话无缝启动 Prompt

复制以下内容到新对话：

---

你现在继续 AIdeal CPS / 智省优选——京东联盟佣金商品 Data Lab 商用化项目。

不要从头重新设计，不要依赖聊天短期上下文。先直接读取 GitHub：`ShanGouXueHui/aideal-cps-data-lab`，分支 `main`。

按顺序读取：

1. `docs/COMMERCIALIZATION_HANDOFF_20260619.md`
2. `docs/PROJECT_MEMORY.md`
3. `docs/CURRENT_PROGRESS_20260619_FINAL.md`
4. `docs/ENGINEERING_COMMERCIAL_RULES_20260619.md`
5. `docs/ENVIRONMENT_OPERATIONS_20260619.md`
6. `docs/DL2_COMMERCIAL_ARCHITECTURE.md`
7. `docs/NEXT_DIALOG_PROMPT_20260619.md`
8. `reports/project_status_20260619_final.json`
9. `reports/hz24_static_ci_latest.json`
10. `reports/hz24_increment_collection_latest.json`
11. HZ24 当前代码、配置、测试和 GitHub workflows。

## 交互规则

- 使用中文，职业化、直接、结构化。
- 默认直接读取和修改 GitHub，不在对话中打印大段代码。
- 代码、配置、文档修改直接提交 GitHub；每次写入后通过 `fetch_file`、`fetch_commit` 或服务器 `git log` 二次确认。
- 不使用 Codex CLI。
- 只有必须访问人工浏览器会话、systemd、服务器进程、Secret 或本地数据库时才给我最小命令。
- Linux 命令可直接 copy-paste、分小步、不使用 `set -e`、不退出当前用户。
- 日志写入 `logs/`、`reports/` 或 `docs/debug/`；我只返回最终 SUMMARY，不复制大段日志。
- 自动化测试不得调用 JD live；真实联盟页面只用于明确的人工授权 smoke/E2E。
- 京东联盟只允许人工登录；出现验证码、滑块、风险页、登录失效立即停止，不绕过验证。

## 修改前强制门禁

任何代码修改前必须先扫描：

1. 同作用域重复定义；
2. 相邻模块和全仓重复实现；
3. 重复常量和重复配置；
4. host、port、scheme、URL、路径、timeout、sleep、batch、频道、risk、selector、schema、service、数据库名硬编码；
5. 大文件和长函数。

分层解耦：browser/collector、application/service、domain、persistence/repository、contracts/schema、configuration、ops、tests、importer/sync。selector 不散落到业务层。入口保持薄。大文件按职责拆分。

`main` 是唯一主流分支。同一能力只有一个 canonical implementation。兼容入口只能委托 canonical service。备份使用 tag、release、artifact、归档包或数据库快照，不维护长期 v2/v3/backup 平行主线。

## 环境

杭州采集机：

- `121.41.111.36`
- 用户 `cpsdata`
- `/home/cpsdata/projects/aideal-cps-data-lab`
- CDP `127.0.0.1:19228`
- systemd `aideal-hz23-observer.service`
- noVNC `http://121.41.111.36:18772/vnc.html?autoconnect=true&resize=scale`

杭州生产机：

- `8.136.28.6`
- 用户 `deploy`
- `/home/deploy/projects/aideal-cps`
- 本地 MySQL `aideal_cps`
- 禁止运行京东浏览器自动化。

新加坡开发机：

- `43.106.55.255`
- 用户 `cpsdev`
- 用于 `aideal-cps` 开发，不是 DL2 第二采集主源。

Data Lab MySQL 目标：

- DB `aideal_cps_data_lab`
- 表 `commission_products`、`commission_refresh_runs`、`commission_product_history`、`commission_publish_versions`
- 视图 `v_published_commission_products`
- 只监听 `127.0.0.1:3306`
- AIdeal CPS 同步时使用短生命周期 Tunnel：生产机 `127.0.0.1:13306` → `cpsdata@121.41.111.36` → Data Lab `127.0.0.1:3306`
- 用户请求始终读取 AIdeal CPS 本地 MySQL。
- Secret 不进入 GitHub。
- write、dual-write、publish、sync 默认关闭；实际部署状态必须现场核验。

## 已验证事实

HZ23：

- 完整轮次 `20260615_100135`
- 67 页完成
- `scanned_total=4020`
- unfinished=0
- stop reason=null
- 商业候选 3304
- duplicate=0
- invalid=0
- payload hash mismatch=0
- candidate integrity ready=true
- observation ready=true

不要把京东显示约 4000 条描述为 4000 条全部已生成推广链接或全部已入库。

HZ24：

- 5 个特殊频道
- membership 250
- 跨频道唯一 SKU 239
- 重复 membership 11
- 与 3304 基线重叠 18
- 增量队列 221
- 当前已提交 linked 72
- pending 149
- complete=false
- 旧批次 5 个失败实际为“已抢光”disabled card，旧实现错误触发 `item_fail_fuse`
- 当前代码已增加 sold_out/delisted/not_promotable terminal unavailable 分类，但尚未由当前 HEAD 杭州 smoke 证明。

当前商用状态：`NOT_READY`。

## 新对话第一任务

只推进 Phase A，不直接运行 221 SKU，不直接初始化数据库，不宣称商用。

第一步：读取 GitHub 最新 main commit、HZ24 Static Checks/Actions、当前 HZ24 代码和测试。确认当前 HEAD 的 compile/import/unit 状态。若失败，只定位并修复第一个真实阻断项。

Phase A 还要逐项完成：纯 URL validator、linked/unavailable repository 互斥、进程 lock、STOP_REQUIRED 合同、observer trap/finally、最终 checkpoint 测试。所有修改都直接提交 GitHub并二次确认。

Phase A 全绿后，再给杭州采集机 2–3 SKU 最小授权 smoke；不要提前全量运行。

完成每个阶段后更新 GitHub 权威文档和 `reports/project_status_20260619_final.json`。

---
