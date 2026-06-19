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
2. `docs/CURRENT_PROGRESS.md`
3. `docs/DL2_COMMERCIAL_ARCHITECTURE.md`
4. `docs/ENGINEERING_STANDARDS.md`
5. `docs/ENVIRONMENT_AND_OPERATIONS.md`
6. `README.md`
7. 当前 HZ24 代码、配置、测试、Actions 和最新报告

不要从头设计。GitHub 当前代码、配置、manifest、报告和 CI 是事实源。必须区分：已验证事实、代码已实现但未现场验证、设计决策、风险假设。

## 2. 项目和环境边界

- Data Lab 负责授权网页采集、标准化、验证和文件交付，不直接写生产 MySQL。
- 杭州采集机：`121.41.111.36`，用户 `cpsdata`，路径 `/home/cpsdata/projects/aideal-cps-data-lab`，CDP `127.0.0.1:19228`。
- 杭州生产机：`8.136.28.6`，用户 `deploy`，路径 `/home/deploy/projects/aideal-cps`；禁止浏览器自动化和京东账号登录。
- 新加坡 `43.106.55.255` / `cpsdev` 可用于应用开发，但不是当前 DL2 双主采集源。
- 生产导入必须经过 validated artifact、dry-run、landed validation、显式批准和幂等写入。

## 3. 交互规则

1. 使用中文，职业化、直接、结构化。
2. 默认直接读取和修改 GitHub，不让我执行超长文件修改命令。
3. 不使用 Codex CLI；Linux 命令不使用 `set -e`。
4. 命令分小步，一次只解决一个问题。
5. 每一步包含路径、git 状态、最小动作、检查、日志路径；屏幕只 tail 关键 80–180 行。
6. 京东联盟只允许人工登录；凭证、Cookie、session、二维码、HAR、HTML 和原始账户页面不得进入 GitHub。
7. 出现验证码、滑块、风险页或登录失效时立即停止，写 STOP_REQUIRED，不绕过验证。
8. 价格、佣金和短链准确性必须依靠数据合同、来源、哈希、时间和验证机制。

## 4. 编程规则

- 分层：entrypoint / configuration / browser adapter / application / outcome / repository / validation / importer。
- 配置分离：host、port、URL、路径、timeout、sleep、batch、risk、schema、service 全部配置化。
- 同一能力只有一个 canonical implementation；兼容入口只能委托主实现。
- 备份使用 tag、release、artifact 或快照，不维护长期 v2/v3/backup 平行主线。
- 通用商用版本必须幂等、可恢复、可审计、fail closed，生产导入默认关闭。
- 每项改动同步代码、配置、测试和文档。

## 5. 当前事实

- 5 个特殊频道已完成结构和重叠分析。
- 商业候选池 3304 SKU；跨频道重复 11 SKU。
- HZ24 增量队列 221 SKU，`commercial_enabled=false`。
- 最近提交的采集结果：72 linked、149 pending、complete=false。
- 最近批次 7 个 SKU：2 成功、5 失败，停止原因为 `item_fail_fuse`。
- 5 个失败样本实际均包含“已抢光”并命中 disabled card；旧运行将其错误计为 click failure。
- 当前代码已加入 sold_out/delisted/not_promotable 分类，并完成主要分层、配置化、幂等写、hash、manifest、validation、测试和静态 workflow。
- 这些重构尚未用当前 GitHub HEAD 在杭州采集机完成新的授权 E2E。
- 当前没有已提交的 `reports/hz24_increment_validation_latest.json`，因此尚未达到商用条件。
- 全仓审计约 390 个 blocker 主要属于 HZ11–HZ23 历史脚本；要区分 HZ24 主线阻断项与 legacy debt。

## 6. 新对话第一项任务

只推进 **Phase A：确认 GitHub HEAD 的 HZ24 静态基线**，不要直接全量采集：

1. 查询最新 HZ24 commit 的 Actions 状态和失败日志。
2. 修复 HZ24 compile/import/unit 问题。
3. 补齐：已抢光不计 failure fuse、linked/unavailable 互斥、STOP_REQUIRED、最终 checkpoint、纯 URL validator、单进程 lock 的测试和实现。
4. 直接修改 GitHub，保持小提交、单主题。
5. 静态 workflow 全绿后，再给杭州采集机 2–3 SKU 最小 smoke；不要先运行 221 SKU。

Phase A 完成标准：模块和入口 compile 通过、unit/contract tests 通过、Actions green、文档更新，并明确仍待杭州现场验证的事项。

开始时先汇报：已读取的 GitHub 文件、当前事实/推断/待验证项，以及 Phase A 的第一个最小问题。

---

阶段顺序：Phase A 静态基线 → Phase B 2–3 SKU 授权 smoke → Phase C 完成 221 SKU accounting → Phase D validation pass → Phase E 生产 dry-run/landed validation → Phase F 通用商用运行和历史脚本退役。
