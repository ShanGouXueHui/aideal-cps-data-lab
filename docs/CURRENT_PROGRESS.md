# DL2 当前进展与商用推进计划

> 截止：2026-06-19  
> 当前结论：**HZ23 候选基线和 HZ24 增量队列已形成，HZ24 核心重构与上下文归档已完成；但当前代码的静态检查证据、杭州授权 E2E、221 SKU 全量 accounting、validation pass、生产交付路径和 dry-run 尚未闭环，因此商业状态仍为 `NOT_READY`。**

## 1. 已验证事实

### 1.1 HZ23 全部商品候选基线

- 京东页面展示池约 4000 条，不能描述为 4000 条全部已生成推广链接。
- HZ23 完整观察轮次：`20260615_100135`。
- `completed_pages=67`、`unfinished_pages=0`、`scanned_total=4020`、`stop_reason=null`。
- 后续商业候选：3304 SKU。
- duplicate、invalid、payload hash mismatch 均为 0。
- `candidate_integrity_ready=true`、`observation_ready=true`、`gate_failures=[]`。
- 3304 是当前可信候选基线，不等于已经正式写入生产 MySQL。

### 1.2 HZ24 特殊频道增量

特殊频道：超补爆品、限量高佣、秒杀专区、定向高佣、粉丝爱买。

结构与重叠：

- 频道 membership：250；
- 跨频道唯一 SKU：239；
- 重复 membership：11；
- 与 HZ23 3304 基线重叠：18；
- 真实增量队列：221；
- 队列 manifest 绑定 data SHA-256、structure SHA-256，`commercial_enabled=false`。

最近已提交 collection report：

- queue：221；
- linked：72；
- pending：149；
- 最近旧批次 processed：7；
- success：2；
- fail：5；
- stop reason：`item_fail_fuse`；
- complete：false；
- risk：空数组。

5 个失败样本包含“已抢光”并命中 disabled card。旧运行将该 terminal business state 错误计为 `click_failed` 并触发技术失败熔断。当前代码已加入 `sold_out`、`delisted`、`not_promotable` 分类，但仍需当前 HEAD 的杭州授权 smoke 证明。

### 1.3 工程审计

- 当前已提交的全仓工程审计快照：605 blocker、243 files scanned。
- 该数字是动态快照，主要来自 HZ11–HZ23 legacy 脚本的大文件、重复实现和硬编码。
- 它不等于 HZ24 主线存在 605 个运行故障。
- 后续必须分别报告：当前商用主线 gate、legacy debt、退役计划。

### 1.4 GitHub HEAD 与 CI 证据

归档核验时观测到的最新交接提交为：`3fadceaa21e46c560df60659b2183b0ccca0d046`。

对该提交：

- combined status 返回空；
- PR-triggered workflow runs 返回空。

这不能证明 Actions 已通过或失败。该提交和随后本轮归档提交主要修改文档，且 HZ24 workflow 存在 path filter。下一对话必须查询 HZ24 Static Checks 最近实际 run；若没有匹配 run，使用 `workflow_dispatch` 主动触发并读取 job/step/log。

## 2. 本轮已完成的 GitHub 改动

### 2.1 配置与分层

已加入或重构：

- `config/hz24-browser.toml`
- `config/hz24-collection.toml`
- `config/hz24-contracts.toml`
- `config/hz24-domain.toml`
- `config/hz24-validation.toml`
- typed settings
- browser contract / JD page adapter
- application / session / tab runner
- outcome service / link service / records
- repository / state store
- validation config / IO / rules / service

### 2.2 Canonical implementation

- `run/hz24_collect_increment_links.py` 为 canonical collector 入口。
- `run/hz24_collect_increment_links_v2.py` 仅委托同一 application service，不是第二套主实现。
- 两个 HZ24 validator 入口委托同一 validation service。
- `scripts/hz24_run_one_increment_batch.sh` 使用 canonical collector，项目路径和 observer service 已配置化。
- `main` 是唯一主流分支；备份使用 tag、release、artifact、数据库快照或归档。

### 2.3 已实现或已建立的可靠性骨架

- queue hash 完整性校验；
- JSON/JSONL 临时文件 + 原子替换；
- SKU 级 upsert 与去重；
- linked/unavailable/pending accounting；
- terminal unavailable 分类；
- 连续技术失败熔断；
- trusted short URL scheme/host 校验；
- record hash、manifest、collection report、validation report；
- HZ24 单元测试；
- HZ24 Static Checks workflow；
- 工程审计汇总字段与部分误报收敛。

以上属于“代码已实现”，不是“当前 CI 已通过”或“杭州现场 E2E 已通过”。

### 2.4 环境、数据库和同步设计归档

已明确：

- 杭州采集机：`121.41.111.36` / `cpsdata` / `/home/cpsdata/projects/aideal-cps-data-lab`；
- 杭州生产机：`8.136.28.6` / `deploy` / `/home/deploy/projects/aideal-cps`；
- 新加坡开发机：`43.106.55.255` / `cpsdev`，不是当前 DL2 双主采集源；
- Data Lab MySQL 目标库：`aideal_cps_data_lab`，仅监听 localhost，实际初始化状态待现场核验；
- AIdeal CPS 生产本地库：`aideal_cps`；
- 生产请求始终读取本地 MySQL，不实时依赖远端 Data Lab；
- 每个发布版本只能选择一条 canonical delivery path：validated artifact/importer，或 Data Lab published view/短生命周期 Tunnel sync；不得维护两套互相漂移的生产交付实现。

### 2.5 项目记忆与交接文档

权威读取顺序：

1. `docs/COMMERCIALIZATION_HANDOFF_20260619.md`
2. `docs/PROJECT_MEMORY.md`
3. `docs/CONVERSATION_ARCHIVE_2026-06-19.md`
4. `docs/CURRENT_PROGRESS.md`
5. `docs/DL2_COMMERCIAL_ARCHITECTURE.md`
6. `docs/ENGINEERING_STANDARDS.md`
7. `docs/ENVIRONMENT_AND_OPERATIONS.md`
8. `docs/NEXT_DIALOG_HANDOFF.md`
9. `README.md`

文档已覆盖：项目边界、环境、周边系统、数据库与同步目标、交互习惯、编程规范、HZ23/HZ24 数据事实、风险、商用门禁和新对话启动 Prompt。

## 3. 未完成与待验证项

### P0：商用阻断

1. **当前代码静态状态未证明为 green**  
   必须查询或主动触发最新 HZ24 Static Checks，确认 compile/import/unit/contract。

2. **杭州授权 smoke/E2E 未完成**  
   尚未用当前 GitHub HEAD 验证正常 SKU、已抢光 SKU、checkpoint、报告、exit code、observer 恢复和风险停止。

3. **221 SKU accounting 未完成**  
   仍需将 pending 清零，生成最新 linked/unavailable 计数，并证明 overlap=0。

4. **validation pass 未证明**  
   必须生成并提交 `reports/hz24_increment_validation_latest.json`，要求全部 gate 通过、`merge_allowed=true`。

5. **生产交付路径尚未选定并验证**  
   必须为首个商用版本只选一条 canonical path，完成 manifest/hash、dry-run、样本核验、显式批准、幂等写入、landed validation 和回滚。

6. **稳定性未证明**  
   商用批准前至少需要一周稳定运行证据。

### P1：主线工程缺口

1. validation 层仍通过 `JDPageAdapter` 复用 URL 判断；需改为纯 URL validator，避免加载 HZ21/browser 依赖。
2. linked 与 unavailable 必须在 repository 层强制互斥。
3. 缺少统一进程级 lock，可能发生 observer/supervisor 与手工任务并发双写。
4. STOP_REQUIRED contract 尚未统一：需机器可读 stop 文件、原因、时间、风险标记、稳定退出码和 supervisor 禁止重启语义。
5. 最终 checkpoint 必须确保写入 `complete`、最终 pending 和 stop reason。
6. shell runner 应使用 trap/finally 保证 observer 原状态恢复。
7. HZ21 adapter 仍是历史兼容依赖，应抽取通用点击/modal 协议。
8. URL builder、typed settings 和配置键仍需通过当前 CI 最终确认。

### P2：数据库与同步待核验

- `aideal_cps_data_lab` 是否已初始化待现场核验；
- MySQL V1 DDL、表、view、backfill、dual-write、publish 和 consumer sync 的实际启用状态不能仅凭历史代码判断；
- 若首个商用版本选择 artifact/importer 路径，Data Lab MySQL 可作为后续阶段，但不得与 importer 形成两套漂移主线；
- 若选择 published view/sync 路径，必须先完成本地监听、Tunnel 生命周期、只读发布、同步幂等和断链恢复测试。

### P3：历史工程债

- HZ11–HZ23 多版本脚本仍大量存在；
- 不一次性重写全部历史代码；
- 按依赖确认、归档、退役顺序处理；
- legacy debt 不能阻止建立 HZ24 独立商用 gate，但不能被隐藏或误称为已解决。

## 4. 下一步计划

### Phase A：当前 HEAD 静态基线

1. 查询 `main` 最新 commit。
2. 查询 HZ24 Static Checks 最近实际 run；若无匹配 run，使用 `workflow_dispatch` 触发。
3. 获取 job、step 和日志，确定第一个真实 compile/import/unit/contract failure。
4. 只修复第一个阻断项，直接修改 GitHub，同步测试和文档。
5. 按依赖顺序闭环：
   - 纯 URL validator；
   - linked/unavailable repository 互斥；
   - 最终 checkpoint；
   - STOP_REQUIRED contract、稳定退出码和 supervisor 语义；
   - 单进程 lock；
   - observer 恢复 trap/finally；
   - terminal unavailable 不计技术 failure fuse。
6. workflow 全绿后更新本文。

完成标准：HZ24 modules/entrypoints compile 通过，unit/contract tests 通过，Actions green，文档同步，主线 gate 与 legacy debt 分开报告。

### Phase B：杭州 2–3 SKU 最小授权 smoke

1. 人工确认京东联盟登录有效。
2. 只读检查 CDP、page host、登录态和风险标记。
3. 选 1 个正常可推广 SKU。
4. 选 1 个已抢光 SKU；必要时增加 1 个普通失败样本。
5. batch limit 设为 2–3。
6. 检查 linked、unavailable、state、collection report、STOP_REQUIRED、exit code 和 observer 原状态恢复。
7. 出现验证码、滑块、风险页或登录失效立即停止，不绕过。

完成标准：正常 SKU 获得可信短链；已抢光进入 unavailable；不计技术熔断；无风险事件；checkpoint 和 observer 恢复正确。

### Phase C：完成 221 SKU accounting

- 复用已有 72 linked；
- 按 linked/unavailable 重建 pending；
- 每批 20–35；
- 每批提交脱敏 report/manifest，不提交敏感原始页面内容；
- 最终 linked + unavailable = 221、pending = 0、overlap = 0、duplicate = 0。

### Phase D：validation candidate

- 运行 canonical validation service；
- 校验 queue hash、row count、duplicate、extra、overlap、trusted URL、required fields、record hash、source tab；
- 生成 outcome manifest；
- 只有 `merge_allowed=true` 才可标记 validated candidate；
- `commercial_enabled` 继续保持 false。

### Phase E：选择并验证 canonical production delivery path

只选择一条：

- Path A：validated artifact → importer → AIdeal CPS 本地 MySQL；或
- Path B：Data Lab published view → 短生命周期 Tunnel sync → AIdeal CPS 本地 MySQL。

完成：manifest/hash、dry-run、insert/update/skip/reject、价格/佣金/短链/过期时间/payload hash 样本核验、显式批准、幂等写入、landed validation、回滚演练。

### Phase F：通用商用运行

- 安全 timer/supervisor；
- 不绕过人工登录和平台风控；
- refresh queue 和链接生命周期；
- 运行摘要、质量指标、异常分类；
- 至少一周稳定运行；
- 显式批准打开商用发布；
- 逐步退役 HZ11–HZ23 并行实现。

## 5. 新对话第一项任务

**只推进 Phase A，不直接运行 221 SKU，也不直接初始化数据库。** 先读取最新 GitHub HEAD、workflow、HZ24 代码、配置、测试和报告；查询或触发 HZ24 Static Checks；确认第一个确定的 compile/import/unit/contract failure，再做单主题修复。
