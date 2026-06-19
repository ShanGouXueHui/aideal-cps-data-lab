# 新对话无缝启动 Prompt

> 最后更新：2026-06-19  
> 用途：复制到新对话后，直接从当前 GitHub 事实和商用阶段继续，不从头设计。

复制以下内容到新对话：

---

你现在继续 **AIdeal CPS / 智省优选 — 京东联盟 DL2 数据采集与商用推进** 项目。

## 1. 先读 GitHub，不要从头设计

仓库：`ShanGouXueHui/aideal-cps-data-lab`  
主分支：`main`，它是唯一主流分支。

按顺序读取：

1. `docs/COMMERCIALIZATION_HANDOFF_20260619.md`
2. `docs/PROJECT_MEMORY.md`
3. `docs/CONVERSATION_ARCHIVE_2026-06-19.md`
4. `docs/CURRENT_PROGRESS.md`
5. `docs/DL2_COMMERCIAL_ARCHITECTURE.md`
6. `docs/ENGINEERING_STANDARDS.md`
7. `docs/ENVIRONMENT_AND_OPERATIONS.md`
8. `README.md`
9. 当前 HZ24 代码、配置、测试、workflow、最新 report/manifest 和最近相关 commit

不要依赖聊天记忆替代 GitHub。发生冲突时，优先级为：当前代码/配置/manifest/report/CI/脱敏现场日志 > `COMMERCIALIZATION_HANDOFF_20260619.md` > 其余设计与历史文档。

必须区分：

- 已验证事实；
- 代码已实现但未现场验证；
- 设计决策；
- 风险/假设。

## 2. 项目、环境与周边系统边界

- Data Lab 负责人工授权网页采集、标准化、验证、发布候选和生产导入前门禁。
- Data Lab 不承载终端用户流量；生产请求不得实时读取远端采集数据库。
- 杭州采集机：`121.41.111.36`，用户 `cpsdata`，路径 `/home/cpsdata/projects/aideal-cps-data-lab`，CDP `127.0.0.1:19228`，observer 为 `aideal-hz23-observer.service`（实际值以配置为准）。
- 杭州生产机：`8.136.28.6`，用户 `deploy`，路径 `/home/deploy/projects/aideal-cps`，本地 MySQL `aideal_cps`；禁止浏览器自动化和京东账号登录。
- 新加坡 `43.106.55.255` / `cpsdev` 用于应用开发，不是当前 DL2 双主采集源。
- Data Lab MySQL 目标库为 `aideal_cps_data_lab`，仅监听 localhost；是否已初始化、DDL 是否已执行、published view 是否可用必须现场核验，不能把设计文档当运行事实。
- 生产交付每个发布版本只能选择一条 canonical delivery path：
  1. validated JSONL/artifact → importer → AIdeal CPS 本地 MySQL；或
  2. Data Lab published view → 短生命周期 SSH Tunnel sync → AIdeal CPS 本地 MySQL。
- 不并行维护两套互相漂移的生产交付实现。无论选择哪条路径，都必须经过 manifest/hash、dry-run、样本核验、显式批准、幂等写入、landed validation 和回滚证据。
- Data Lab 核心链路保持确定性，不使用大模型判断价格、佣金、短链、hash 或导入门禁；模型 Provider 属于 `aideal-cps`，ZenMux 已排除。

## 3. 交互规则

1. 使用中文，职业化、直接、结构化。
2. 默认直接读取和修改 GitHub，不让我执行超长文件修改命令。
3. 不使用 Codex CLI；Linux 命令不使用 `set -e`。
4. 命令分小步，一次只解决一个问题。
5. 每一步包含路径、`git status --short`、最小动作、检查、日志路径；屏幕只 tail 关键 80–180 行或返回最终 SUMMARY。
6. GitHub 是长期事实源；运行态无法从 GitHub 证明时，明确标为“待现场验证”。
7. 详细日志优先留在服务器，只提交脱敏 summary/report。
8. 京东联盟只允许人工登录；凭证、Cookie、session、二维码、HAR、HTML、原始账户页面不得进入 GitHub。
9. 出现验证码、滑块、风险页、登录失效或页面身份不确定时立即停止，写 STOP_REQUIRED，不绕过验证。
10. 价格、佣金和短链准确性依靠数据合同、字段来源、hash、时间戳、Decimal/DECIMAL、幂等和 landed validation，不依赖话术。

## 4. 编程、分层与版本规则

- 修改前先检查目标文件同作用域重复定义、全仓同类实现、重复配置、硬编码、文件/函数规模。
- 分层：entrypoint / configuration / browser-page adapter / application-session / outcome / repository-state / contracts-validation / importer-sync。
- selector 不散落到业务层；validator 不连接浏览器或生产数据库。
- host、port、scheme、URL、路径、timeout、sleep、batch、risk、频道、schema、service 全部配置化；环境变量覆盖 TOML。
- 同一能力只有一个 canonical implementation；兼容入口只能委托主实现，迁移后删除。
- `main` 是唯一主流分支；备份使用 tag、release、artifact、数据库快照或归档，不维护长期 `v2/v3/backup/rewrite` 平行主线。
- 通用商用版本必须幂等、可恢复、可审计、可回滚、fail closed、进程互斥、linked/unavailable 数据互斥，生产导入和发布默认关闭。
- SKU 唯一；金额使用 Decimal/DECIMAL；不物理删除商品。
- 单函数目标不超过约 80 行，单文件目标不超过约 300 行；按职责拆分，不做机械分片。
- 每项改动同步代码、配置、测试、报告和文档；不为快速修复重新引入大文件、重复实现或硬编码。

## 5. 当前已验证事实

- HZ23 完整轮次 `20260615_100135`：67 页、`scanned_total=4020`、无 unfinished page、无 stop reason；商业候选 3304，candidate integrity 和 observation ready。3304 不等于页面约 4000 条商品全部已生成推广链接，也不等于已经写入生产数据库。
- HZ24 5 个特殊频道完成结构与重叠分析：250 membership、239 unique SKU、11 duplicate membership、与 3304 基线重叠 18、真实增量队列 221。
- HZ24 队列 `commercial_enabled=false`。
- 最近已提交 HZ24 采集结果：72 linked、149 pending、`complete=false`。
- 最近旧批次：7 processed、2 success、5 fail，停止原因为 `item_fail_fuse`。
- 5 个失败样本实际包含“已抢光”并命中 disabled card；旧运行错误计为 click failure。当前代码已加入 terminal unavailable 分类，但仍需杭州当前 HEAD smoke 证明。
- 已提交全仓工程审计快照为 605 blocker、243 files scanned，主要属于 HZ11–HZ23 legacy debt；该数字不等于 HZ24 有 605 个运行故障。
- 当前没有可证明通过的 HZ24 validation report，商业状态为 `NOT_READY`。

## 6. 当前代码进展与未闭环项

GitHub 已完成或加入：

- HZ24 typed settings 与 TOML 配置；
- browser contract、JD page adapter、application、session、tab runner、outcome、link、records、repository、state、validation 分层；
- canonical collector 与 validator 入口委托；
- `sold_out`、`delisted`、`not_promotable` 终态分类；
- JSONL SKU upsert、原子写、hash、manifest、accounting；
- HZ24 单元测试和静态 workflow；
- shell runner 路径与 observer service 配置化；
- 工程审计汇总与部分误报收敛；
- 项目记忆、对话归档、环境手册、工程规范、商用架构和推进计划。

以上只能标记为“代码已实现”。归档核验时观测到的最新交接提交为 `3fadceaa21e46c560df60659b2183b0ccca0d046`；combined status 和 PR-triggered workflow runs 均为空。该证据不能证明 CI 通过或失败，且后续文档提交同样不能替代 HZ24 workflow 结果。

仍需闭环：

- 查询或主动触发当前 HZ24 Static Checks；
- validation 改为纯 URL validator，不加载 browser/HZ21 adapter；
- repository 强制 linked/unavailable 互斥；
- STOP_REQUIRED contract、稳定退出码和 supervisor 禁止重启语义；
- 最终 checkpoint；
- 单进程 lock；
- observer 恢复 trap/finally；
- disabled + 已抢光不计技术 failure fuse 的测试和现场证明；
- 221 SKU 全量 accounting；
- validation `merge_allowed=true`；
- 选定并验证一条 canonical production delivery path；
- dry-run、正式写入、landed validation、回滚和至少一周稳定运行。

## 7. 新对话第一项任务

只推进 **Phase A：当前 GitHub HEAD 的 HZ24 静态基线**，不要直接运行 221 SKU，也不要直接初始化数据库：

1. 查询 `main` 最新 commit。
2. 查询 HZ24 Static Checks 最近实际 workflow run；若没有匹配 run，使用 `workflow_dispatch` 触发。
3. 读取 job、step 和日志，确定第一个真实 compile/import/unit/contract 错误。
4. 只修复第一个真实阻断项，直接修改 GitHub；同步测试和文档。
5. 按风险与依赖顺序推进：
   - 纯 URL validator；
   - linked/unavailable repository 互斥；
   - 最终 checkpoint；
   - STOP_REQUIRED + 稳定退出码 + supervisor 语义；
   - 单进程 lock；
   - observer 恢复 trap/finally；
   - terminal unavailable 不计 failure fuse。
6. 保持小提交、单一 canonical implementation、配置分离。
7. Actions 全绿后更新 `docs/CURRENT_PROGRESS.md`，再给杭州采集机 2–3 SKU 最小授权 smoke 步骤。

Phase A 完成标准：

- HZ24 modules 与 entrypoints compile 通过；
- unit/contract tests 通过；
- Actions green；
- 当前主线门禁和 legacy debt 分开报告；
- 文档同步；
- 明确列出仍待杭州现场验证的事项。

开始时先汇报：

- 已读取的 GitHub 文件；
- 当前 HEAD 与 CI 状态；
- 已验证事实、代码已实现但未验证、风险；
- Phase A 的第一个最小问题。

---

阶段顺序：Phase A 静态基线 → Phase B 2–3 SKU 授权 smoke → Phase C 完成 221 SKU accounting → Phase D validation pass → Phase E 选定一条 canonical delivery path 并完成 dry-run/landed validation/回滚 → Phase F 稳定运行一周并显式批准商用 → Phase G refresh queue、监控与 HZ11–HZ23 遗留脚本退役。
