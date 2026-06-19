# 新对话无缝启动 Prompt

> 最后更新：2026-06-19

复制以下内容到新对话：

---

你现在继续 **AIdeal CPS / 智省优选 — 京东联盟 DL2 数据采集与商用推进** 项目。

## 1. 先读 GitHub

仓库：`ShanGouXueHui/aideal-cps-data-lab`  
主分支：`main`，它是唯一主流分支。

按顺序读取：

1. `docs/PROJECT_MEMORY.md`
2. `docs/CONVERSATION_ARCHIVE_2026-06-19.md`
3. `docs/CURRENT_PROGRESS.md`
4. `docs/DL2_COMMERCIAL_ARCHITECTURE.md`
5. `docs/ENGINEERING_STANDARDS.md`
6. `docs/ENVIRONMENT_AND_OPERATIONS.md`
7. `README.md`
8. 当前 HZ24 代码、配置、测试、Actions 和最新报告

不要从头设计。GitHub 代码、配置、manifest、报告和 CI 是事实源。必须区分：

- 已验证事实；
- 代码已实现但未现场验证；
- 设计决策；
- 风险/假设。

## 2. 项目与环境边界

- Data Lab 负责授权网页采集、标准化、验证和 validated artifact 交付，不直接写生产 MySQL。
- 杭州采集机：`121.41.111.36`，用户 `cpsdata`，路径 `/home/cpsdata/projects/aideal-cps-data-lab`，CDP `127.0.0.1:19228`。
- 杭州生产机：`8.136.28.6`，用户 `deploy`，路径 `/home/deploy/projects/aideal-cps`；禁止浏览器自动化和京东账号登录。
- 新加坡 `43.106.55.255` / `cpsdev` 可用于应用开发，但不是当前 DL2 双主采集源。
- 生产导入必须经过 validated artifact、manifest/hash 校验、dry-run、landed validation、显式批准和幂等写入。
- Data Lab 核心链路保持确定性，不使用大模型判断价格、佣金、短链、哈希或导入门禁。

## 3. 交互规则

1. 使用中文，职业化、直接、结构化。
2. 默认直接读取和修改 GitHub，不让我执行超长文件修改命令。
3. 不使用 Codex CLI；Linux 命令不使用 `set -e`。
4. 命令分小步，一次只解决一个问题。
5. 每一步包含路径、git 状态、最小动作、检查、日志路径；屏幕只 tail 关键 80–180 行。
6. GitHub 是长期事实源；运行态无法从 GitHub 证明时，明确标为待现场验证。
7. 京东联盟只允许人工登录；凭证、Cookie、session、二维码、HAR、HTML、原始账户页面不得进入 GitHub。
8. 出现验证码、滑块、风险页或登录失效时立即停止，写 STOP_REQUIRED，不绕过验证。
9. 价格、佣金和短链准确性依靠数据合同、字段来源、hash、时间戳、幂等和 landed validation。

## 4. 编程规则

- 分层：entrypoint / configuration / browser-page adapter / application-session / outcome / repository-state / validation / importer。
- host、port、scheme、URL、路径、timeout、sleep、batch、risk、频道、schema、service 全部配置化。
- 同一能力只有一个 canonical implementation；兼容入口只能委托主实现。
- `main` 是唯一主流分支；备份使用 tag、release、artifact 或快照，不维护长期 v2/v3/backup 平行主线。
- 通用商用版本必须幂等、可恢复、可审计、可回滚、fail closed、进程互斥、数据互斥，生产导入默认关闭。
- 每项改动同步代码、配置、测试和文档。
- 不为“快速修复”重新引入大型单文件、重复实现或硬编码。

## 5. 当前已验证事实

- 5 个特殊频道已完成结构与重叠分析。
- 商业候选池 3304 SKU；跨频道重复 11 SKU。
- HZ24 增量队列 221 SKU，`commercial_enabled=false`。
- 最近提交的采集结果：72 linked、149 pending、complete=false。
- 最近批次：7 processed、2 success、5 fail，停止原因为 `item_fail_fuse`。
- 5 个失败样本实际包含“已抢光”并命中 disabled card；旧运行错误计为 click failure。
- 最新已看到的全仓工程审计快照为 605 blocker，主要属于 HZ11–HZ23 legacy debt；该数字是动态值，不等于 HZ24 主线有 605 个运行故障。
- 当前没有可证明通过的 HZ24 validation report，因此尚未达到商用条件。

## 6. 当前代码进展

GitHub 已完成或已加入：

- HZ24 typed settings 与 TOML 配置；
- browser contract、JD page adapter、application、session、tab runner、outcome、link、records、repository、state、validation 分层；
- canonical collector 与 validator 入口委托；
- `sold_out`、`delisted`、`not_promotable` 终态分类；
- JSONL SKU upsert、hash、manifest、accounting；
- HZ24 单元测试和静态 workflow；
- shell runner 的路径与 observer service 配置化；
- 工程审计汇总与部分误报收敛；
- 完整对话归档：`docs/CONVERSATION_ARCHIVE_2026-06-19.md`。

这些只能标记为“代码已实现”。必须查询当前 HEAD 的 Actions 和日志，确认 compile/unit 结果；杭州授权 E2E 仍待现场验证。

## 7. 新对话第一项任务

只推进 **Phase A：当前 GitHub HEAD 的 HZ24 静态基线**，不要直接运行 221 SKU：

1. 查询 `main` 最新 commit。
2. 查询 HZ24 Static Checks 和相关 workflow 状态。
3. 若失败，读取 job/step/log，确定第一个真实错误。
4. 单主题修复 compile/import/unit 问题，直接修改 GitHub。
5. 补齐并验证：
   - disabled + 已抢光不计技术 failure fuse；
   - linked/unavailable repository 互斥；
   - STOP_REQUIRED contract；
   - 最终 checkpoint；
   - validation 使用纯 URL validator，不加载 browser/HZ21 adapter；
   - 单进程 lock。
6. 保持小提交、单一 canonical implementation、配置分离。
7. Actions 全绿后更新 `docs/CURRENT_PROGRESS.md`，再给杭州采集机 2–3 SKU 最小 smoke 步骤。

Phase A 完成标准：

- HZ24 modules 与 entrypoints compile 通过；
- unit/contract tests 通过；
- Actions green；
- 文档同步；
- 明确列出仍待杭州现场验证的事项。

开始时先汇报：

- 已读取的 GitHub 文件；
- 当前 HEAD 与 CI 状态；
- 已验证事实、代码已实现但未验证、风险；
- Phase A 的第一个最小问题。

---

阶段顺序：Phase A 静态基线 → Phase B 2–3 SKU 授权 smoke → Phase C 完成 221 SKU accounting → Phase D validation pass → Phase E 生产 dry-run/landed validation → Phase F 通用商用运行与历史脚本退役。
