# DL2 当前进展与商用推进计划

> 截止：2026-06-19  
> 当前结论：**HZ24 已完成核心重构与上下文归档，但当前代码的静态检查证据、杭州授权 E2E、221 SKU 全量 accounting、validation pass 和生产 dry-run 尚未闭环，因此不能标记为已商用。**

## 1. 已验证事实

### 1.1 业务与数据范围

- 特殊频道：超补爆品、限量高佣、秒杀专区、定向高佣、粉丝爱买。
- HZ23 商业候选基线：3304 SKU。
- HZ24 频道 membership：250。
- HZ24 跨频道唯一 SKU：239。
- 特殊频道跨频道重复 membership：11。
- 与 HZ23 3304 基线重叠：18。
- HZ24 真实增量队列：221 SKU。
- 队列 manifest 绑定数据 SHA-256 与结构 SHA-256，`commercial_enabled=false`。

### 1.2 最近提交的采集运行结果

最近已提交的 collection report 表明：

- queue：221
- linked：72
- pending：149
- 最近批次 processed：7
- success：2
- fail：5
- stop reason：`item_fail_fuse`
- complete：false
- risk：空数组

失败样本包含“已抢光”并命中 disabled card。旧运行把该业务终态错误计为 `click_failed`，触发技术失败熔断。

### 1.3 工程审计

- 当前已提交的全仓工程审计快照为 605 blocker、243 files scanned。
- 该数字是动态快照，主要来自 HZ11–HZ23 历史脚本的大文件、重复实现和硬编码。
- 它不等于 HZ24 主线存在 605 个运行故障。
- 后续必须拆分：当前商用主线门禁、legacy debt、退役计划。

### 1.4 GitHub HEAD 与 CI 证据

归档前观测到的 `main` HEAD 为 `febdeae72e6701305896f797a06bb25c63db40bb`，是文档更新提交。随后已继续提交本轮归档文档。

对该观测 HEAD：

- combined status 返回空；
- PR-triggered workflow runs 返回空。

这不能证明 Actions 已通过或失败。该提交只修改文档，而 HZ24 workflow 使用 path filter，因此可能没有触发。下一步必须查询 HZ24 Static Checks 最近实际 run，必要时通过 `workflow_dispatch` 主动触发并读取 job/step/log。

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

- `run/hz24_collect_increment_links.py` 为主入口。
- `run/hz24_collect_increment_links_v2.py` 委托同一 application service。
- 两个 HZ24 validator 入口委托同一 validation service。
- `scripts/hz24_run_one_increment_batch.sh` 使用 canonical collector，项目路径和 observer service 已配置化。
- `main` 是唯一主流分支；兼容入口不是第二套实现。

### 2.3 可靠性能力

已实现或已建立代码骨架：

- queue hash 完整性校验；
- JSON/JSONL 原子写；
- SKU 级 upsert 与去重；
- linked/unavailable/pending accounting；
- `sold_out`、`delisted`、`not_promotable` 分类；
- 连续技术失败熔断；
- trusted short URL scheme/host 校验；
- record hash、manifest、collection report、validation report；
- HZ24 单元测试；
- HZ24 Static Checks workflow；
- 工程审计汇总字段与部分误报收敛。

以上属于“代码已实现”，不是“已通过当前 CI 和杭州现场验证”。

### 2.4 文档与项目记忆归档

权威文档：

- `docs/COMMERCIALIZATION_HANDOFF_20260619.md`
- `docs/PROJECT_MEMORY.md`
- `docs/CONVERSATION_ARCHIVE_2026-06-19.md`
- `docs/CURRENT_PROGRESS.md`
- `docs/DL2_COMMERCIAL_ARCHITECTURE.md`
- `docs/ENGINEERING_STANDARDS.md`
- `docs/ENVIRONMENT_AND_OPERATIONS.md`
- `docs/NEXT_DIALOG_HANDOFF.md`

这些文档归档了环境、周边系统、数据库与同步目标、交互习惯、编程规范、HZ23/HZ24 数据事实、风险和商用路线。

## 3. 未完成与待验证项

### P0：商用阻断

1. **当前代码静态状态未证明为 green**  
   必须查询或主动触发最新 HZ24 Static Checks，确认 compile/import/unit/contract。

2. **杭州授权 smoke/E2E 未完成**  
   当前代码尚未在杭州采集机用有效人工登录会话验证正常 SKU、已抢光 SKU、checkpoint、报告和退出码。

3. **221 SKU accounting 未完成**  
   仍缺 pending 清零和最新 unavailable 计数。

4. **validation pass 未证明**  
   必须生成并提交 `reports/hz24_increment_validation_latest.json`，要求全部门禁通过、`merge_allowed=true`。

5. **生产 importer 未执行**  
   未完成 manifest/hash 校验、dry-run、显式批准、幂等写入、landed validation 和回滚证据。

### P1：主线工程缺口

1. validation 层仍通过 `JDPageAdapter` 复用 URL 判断；需要改为纯 URL validator，避免加载 HZ21/browser 依赖。
2. linked 与 unavailable 必须在 repository 层强制互斥。
3. 缺少统一进程级 lock，可能发生 observer/supervisor 与手工任务并发写。
4. STOP_REQUIRED contract 尚未统一：需要机器可读 stop 文件、原因、时间、风险标记、稳定退出码和 supervisor 禁止重启语义。
5. 最终 checkpoint 必须确保写入 `complete`、最终 pending 和 stop reason。
6. shell runner 应使用 trap/finally 保证 observer 原状态恢复。
7. HZ21 adapter 仍是历史兼容依赖，应抽取通用点击/modal 协议。
8. URL builder、typed settings 和配置键仍需通过当前 CI 最终确认。

### P2：历史工程债

- HZ11–HZ23 多版本脚本仍大量存在。
- 不应一次性重写全部历史代码。
- 只允许一个当前商用主流实现；历史脚本按依赖确认、归档、退役顺序处理。
- 全仓 legacy debt 不能阻止先建立 HZ24 独立的商用门禁，但不能被隐藏或误称为已解决。

## 4. 下一步计划

### Phase A：静态基线

按顺序执行：

1. 查询 `main` 最新 commit 和 HZ24 Static Checks 最近实际 run。
2. 若没有对应 run，通过 `workflow_dispatch` 触发。
3. 获取失败 job、step 和日志，确定第一个真实错误。
4. 单主题修复 compile、import、typing、unit 或 contract failure。
5. 补齐并验证：
   - disabled + 已抢光不计技术 failure fuse；
   - linked/unavailable repository 互斥；
   - STOP_REQUIRED；
   - 最终 checkpoint；
   - 纯 URL validator；
   - 进程 lock；
   - observer 恢复 trap/finally。
6. HZ24 workflow 全绿后更新本文。

完成标准：所有 HZ24 module/entrypoint compile 通过，unit/contract tests 通过，Actions green，且文档同步。

### Phase B：杭州 2–3 SKU 最小 smoke

1. 人工确认京东联盟登录有效。
2. 只读检查 CDP、page host 和风险标记。
3. 选 1 个正常可推广 SKU。
4. 选 1 个已抢光 SKU。
5. batch limit 设为 2–3。
6. 检查 linked、unavailable、state、collection report 和退出码。
7. 出现验证码、滑块、风险页或登录失效立即 STOP_REQUIRED。

完成标准：正常 SKU 得可信短链；已抢光进入 unavailable；不计入技术熔断；无风险事件；observer 状态恢复正确。

### Phase C：完成 221 SKU accounting

- 复用已有 72 linked；
- 按 linked/unavailable 重建 pending；
- 每批 20–35；
- 每批提交脱敏 report/manifest，不提交敏感原始页面内容；
- 最终要求 linked + unavailable = 221、pending = 0、overlap = 0。

### Phase D：validation candidate

- 运行 canonical validation service；
- 校验 queue hash、row count、duplicate、extra、overlap、trusted URL、required fields、record hash、source tab；
- 生成 outcome manifest；
- 只有 `merge_allowed=true` 才可标记 validated candidate；
- `commercial_enabled` 继续保持 false。

### Phase E：生产 dry-run 与导入

在杭州生产机：

1. 拉取固定 commit 对应的 validated artifact；
2. 校验 manifest/hash；
3. importer 或受控 sync dry-run；
4. 输出 insert/update/skip/reject；
5. 样本核验价格、佣金、短链、过期时间、payload hash；
6. 显式批准；
7. 幂等写入 AIdeal CPS 本地 MySQL；
8. landed validation 与回滚证据。

### Phase F：通用商用运行

- 安全 timer/supervisor；
- 不绕过人工登录和平台风控；
- 链接刷新队列；
- 运行摘要、质量指标、异常分类；
- 至少一周稳定运行；
- 显式批准打开发布；
- 逐步退役 HZ11–HZ23 并行实现。

## 5. 新对话第一项任务

**只推进 Phase A，不直接运行 221 SKU。** 先读取最新 GitHub HEAD、Actions、HZ24 代码、配置和测试；查询或触发 HZ24 Static Checks；确认第一个确定的 compile/import/unit/contract failure，再做单主题修复。
