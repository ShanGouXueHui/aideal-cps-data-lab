# 新对话无缝启动 Prompt V2

> 最后更新：2026-06-19。本文覆盖旧 handoff 中过时的工程审计数字和任务状态。

复制以下内容到新对话：

---

你现在继续 **AIdeal CPS / 智省优选 — 京东联盟 DL2 数据采集与商用推进** 项目。

## 一、先读 GitHub，不要从头设计

仓库：`ShanGouXueHui/aideal-cps-data-lab`  
唯一主流分支：`main`

按顺序读取：

1. `docs/PROJECT_MEMORY.md`
2. `docs/CURRENT_PROGRESS.md`
3. `docs/SESSION_ARCHIVE_2026-06-19.md`
4. `docs/DL2_COMMERCIAL_ARCHITECTURE.md`
5. `docs/ENGINEERING_STANDARDS.md`
6. `docs/ENVIRONMENT_AND_OPERATIONS.md`
7. `docs/NEXT_DIALOG_HANDOFF_V2.md`
8. `README.md`
9. 当前 HZ24 代码、配置、测试、Actions、manifest 和最新报告

GitHub 当前代码、配置、报告、manifest 和 CI 是事实源。必须明确区分：

- 已验证事实；
- 代码已实现但未现场验证；
- 已确定设计但未实现；
- 风险或假设。

## 二、项目边界

- Data Lab 负责人工授权网页采集、标准化、验证、文件制品和生产导入前门禁。
- Data Lab 不直接写生产 MySQL，不承担用户对话、推荐排序、会员、支付或返佣结算。
- 生产导入必须经过 validated artifact、manifest/hash、dry-run、显式批准、幂等导入、landed validation 和 rollback evidence。
- 采集成功不等于允许商用。

## 三、环境事实

- 杭州采集机：`121.41.111.36`，用户 `cpsdata`，路径 `/home/cpsdata/projects/aideal-cps-data-lab`，CDP `127.0.0.1:19228`，noVNC `18772`，x11vnc `59072`。
- 杭州生产机：`8.136.28.6`，用户 `deploy`，路径 `/home/deploy/projects/aideal-cps`；禁止浏览器自动化和京东账号登录。
- 新加坡开发机：`43.106.55.255`，用户 `cpsdev`；可用于应用开发，但不是当前 DL2 双主采集源。
- 生产数据库为 MySQL，凭证不得写入代码、聊天、日志或 GitHub。
- DL2 采集和验证链路不依赖大模型；模型 Provider 属于 `aideal-cps`，ZenMux 默认排除。

## 四、交互规则

1. 使用中文，职业化、直接、结构化。
2. 默认直接读取和修改 GitHub；不要让我执行超长文件修改命令。
3. 不使用 Codex CLI。
4. Linux 命令不使用 `set -e`。
5. 命令分小步，一次只解决一个问题。
6. 每一步包含路径确认、`git status --short`、最小动作、检查、日志路径；屏幕只 tail 关键 80–180 行。
7. 运行状态优先从 GitHub 的报告、manifest、Actions 和 job log 查询；GitHub 无法确认时再让我从服务器 tail 指定日志。
8. 京东联盟只允许人工登录；账号密码、Cookie、session、二维码、HAR、HTML 和原始账户页面不得进入 GitHub。
9. 出现验证码、滑块、风险页、登录失效或身份不确定时立即停止，写 STOP_REQUIRED，不绕过验证。
10. 价格、佣金和短链准确性必须通过来源、字段合同、hash、时间、幂等和 landed validation 保证。

## 五、编程与交付规范

- 分层：entrypoint / configuration / browser adapter / application / outcome / repository / state / validation / importer。
- entrypoint 必须薄；外部副作用集中在 adapter/repository/session 边界。
- host、port、scheme、URL、路径、timeout、sleep、batch、risk、schema、service 全部配置化。
- `main` 是唯一主流分支；同一能力只有一个 canonical implementation。
- `v2/v3/backup` 仅可作为短期兼容入口，必须委托 canonical service，迁移完成后删除。
- 备份使用 tag、release、artifact、数据库快照或受控归档，不维护平行主流实现。
- JSONL 按 SKU 幂等 upsert，临时文件原子替换；linked/unavailable 必须互斥。
- validator 必须纯文件、纯配置，不连接京东页面或生产库。
- 风险/session failure 与 terminal business state、retryable interaction failure、integrity failure 必须分开。
- terminal state 不计入 consecutive technical failure fuse。
- 每项改动同步代码、配置、测试和文档。
- 通用商用版本必须可恢复、可审计、fail closed，生产导入默认关闭。

## 六、当前已验证事实

- 特殊频道 5 个：超补爆品、限量高佣、秒杀专区、定向高佣、粉丝爱买。
- 商业候选池 3304 SKU；跨频道重复 11 SKU。
- HZ24 增量队列 221 SKU，`commercial_enabled=false`。
- 最近提交采集结果：72 linked、149 pending、complete=false。
- 最近批次 processed=7、success=2、fail=5、stop_reason=`item_fail_fuse`。
- 5 个失败样本实际包含“已抢光”并命中 disabled card；旧运行错误计为 click failure。
- 最新全仓工程审计报告记录 `blocker_count=605`、`files_scanned=243`；主要是 HZ11–HZ23 历史脚本债务，不等于 HZ24 有 605 个直接运行故障。
- 当前没有完整 HZ24 validation pass，也没有生产 importer dry-run/landed validation 证据。

## 七、当前代码已实现但未完成现场证明

- typed settings 与 TOML/env 配置；
- browser contract、JD page adapter、application、session、tab runner、outcome、link、repository、state、validation 分层；
- JSON/JSONL 原子写入和 SKU upsert；
- queue hash/row-count 校验；
- linked/unavailable/pending accounting；
- sold_out、delisted、not_promotable 终态；
- failure fuse、可信短链、record hash、manifest/report；
- canonical collector/validator 入口；
- `tests/test_hz24_refactor.py` 和 HZ24 static workflow。

这些内容尚未用当前 GitHub HEAD 在杭州采集机完成新的授权 E2E。

## 八、当前 P0/P1 缺口

1. 查询最新 HZ24 Actions，修复 compile/import/unit 问题。
2. validator 去除 `JDPageAdapter`/HZ21 动态依赖，改为纯 URL validator。
3. linked/unavailable repository 互斥写保护。
4. STOP_REQUIRED 机器可读合同、稳定退出码和 supervisor 禁止自动重启。
5. collector 单进程 lock。
6. 最终 checkpoint 的完整测试。
7. batch shell 在所有异常路径恢复 observer，使用 trap/finally 语义。
8. HZ21 adapter 逐步替换为真正通用的点击/modal 协议。
9. 完成 221 accounting 和 validation pass。
10. 生产 importer dry-run、显式批准、幂等导入、landed validation、回滚演练。

## 九、新对话第一项任务

只推进 **Phase A：确认当前 GitHub HEAD 的 HZ24 静态基线**，不要直接全量采集：

1. 查询最新 HZ24 commit、Actions 状态和失败 job log。
2. 先处理第一个 compile/import/unit failure；一次只修一个问题。
3. 补齐纯 URL validator、linked/unavailable 互斥、STOP_REQUIRED、最终 checkpoint、单进程 lock 的实现与测试。
4. 直接修改 GitHub，保持小提交、单主题。
5. 静态 workflow 全绿后，再给杭州采集机 2–3 SKU 最小 smoke；不要先运行 221 SKU。

Phase A 完成标准：模块和入口 compile 通过、unit/contract tests 通过、Actions green、文档更新，并明确仍待杭州现场验证的事项。

开始时先汇报：已读取的 GitHub 文件、当前事实/推断/待验证项，以及 Phase A 的第一个最小问题。

阶段顺序固定为：Phase A 静态基线 → Phase B 2–3 SKU 授权 smoke → Phase C 221 SKU accounting → Phase D validation pass → Phase E 生产 dry-run/landed validation → Phase F 通用商用运行和历史脚本退役。

---
