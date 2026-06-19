# DL2 当前进展与商用推进计划 — 2026-06-19 最终归档

> 状态：当前权威进展文档。旧 `CURRENT_PROGRESS*` 文档中的固定审计数量、HZ23 未完成判断或 file-only 架构描述均以本文和 `COMMERCIALIZATION_HANDOFF_20260619.md` 为准。

## 1. 当前结论

当前商用状态：`NOT_READY`。

HZ23 全部商品主链路已经完成完整观察轮次和 3304 条商业候选完整性门禁。HZ24 已完成五个特殊频道的结构与重叠分析，形成 221 SKU 增量队列，并已提交 72 条 linked 结果；剩余 149 条尚未完成 linked/unavailable accounting。

当前 HZ24 代码经过大规模分层和配置化重构，但当前 `main` HEAD 尚未形成新的 compile/unit/Actions 全绿证据，也尚未完成杭州授权最小 smoke。因此不得直接恢复 221 SKU 全量运行，也不得宣称已可商用。

## 2. 已验证数据事实

### 2.1 HZ22/HZ23 基线

- 京东页面展示池约 4000 条；不得描述为 4000 条全部已生成推广链接或全部已入库。
- HZ22 page 61–67：新增成功 162，失败 5；当时可信推广短链 SKU 2385。
- HZ23 完整轮次：`20260615_100135`。
- 完成页：67。
- unfinished page：0。
- `scanned_total=4020`。
- `stop_reason=null`。
- 商业候选：3304。
- duplicate SKU：0。
- invalid row：0。
- payload hash mismatch：0。
- `candidate_integrity_ready=true`。
- `observation_ready=true`。
- gate failures：空。

3304 是当前可信候选基线，不代表已实际写入 Data Lab MySQL 或 AIdeal CPS 生产 MySQL；数据库运行态需要重新核验。

### 2.2 HZ24 特殊频道

频道：超补爆品、限量高佣、秒杀专区、定向高佣、粉丝爱买。

- membership 总数：250。
- 跨频道唯一 SKU：239。
- 重复 membership：11。
- 与 3304 基线重叠：18。
- 真实增量队列：221。
- 当前已提交 linked：72。
- 当前 pending：149。
- complete：false。
- 最近旧批次 stop reason：`item_fail_fuse`。
- risk：空。

旧批次 5 个 click failure 实际为“已抢光”disabled card。当前代码已将 `sold_out`、`delisted`、`not_promotable` 作为 terminal unavailable，不应再增加技术 failure fuse；仍需当前 HEAD 的杭州授权 smoke 证明。

## 3. 已完成工程方向

- typed settings + TOML/env 配置。
- browser contract、JD page adapter。
- application、session、tab runner。
- outcome、link service。
- repository、records、state store。
- linked/unavailable/pending accounting。
- SKU 幂等 upsert、JSON/JSONL 原子替换。
- queue/record hash、manifest、collection/validation report。
- canonical collector/validator 入口委托。
- HZ24 unit tests、static workflow、工程审计框架。
- host、port、scheme、URL、路径、timeout、sleep、batch、频道、risk、schema、service 名称配置化方向。

历史静态报告曾记录 `compile_rc=0`、`test_rc=0`、`status=PASS`、`jd_live_called=false`。该报告只证明当时 commit；后续代码已继续变更，不能替代当前 HEAD 检查。

## 4. 当前阻断项

### P0

1. 当前 HEAD compile/import/unit/Actions 尚未重新确认。
2. 当前代码未完成杭州 2–3 SKU 授权 smoke。
3. 221 SKU accounting 未完成。
4. 尚无完整 `merge_allowed=true` validation report。
5. Data Lab MySQL 实际初始化、回填、dual-write、publish view 状态未重新核验。
6. AIdeal CPS production dry-run、同步/import、landed validation、rollback 未完成。
7. 未完成至少一周稳定运行。

### P1

- validator 应使用纯 URL validator，不加载 browser/HZ21 adapter。
- linked/unavailable 必须 repository 层互斥。
- collector 必须有进程级 lock。
- STOP_REQUIRED 必须机器可读，并阻止 supervisor 无限重启。
- observer 停止/恢复必须 trap/finally 收口。
- 最终 checkpoint 必须完整保存 complete、pending、stop reason，并有测试。
- HZ21 adapter 应逐步替换为通用点击/modal 协议。

### P2

HZ11–HZ23 存在历史大文件、重复实现和硬编码。工程审计 blocker 数是动态快照，不得在长期权威文档写死。当前商用主线门禁和 legacy debt 必须分别统计；legacy 逐步退役，不得形成第二主线。

## 5. 下一步固定顺序

### Phase A：当前 HEAD 静态基线

- 查询最新 main commit 和 HZ24 Actions。
- 编译 HZ24 所有入口、配置、collector、validator。
- 运行 unit/contract tests，禁止 JD live。
- 修复第一个真实 compile/unit failure。
- 完成纯 URL validator、互斥写、lock、STOP_REQUIRED、最终 checkpoint 测试。

完成标准：当前 HEAD compile=0、tests=0、Actions green、JD live 未调用。

### Phase B：杭州最小授权 smoke

- 人工确认联盟登录有效。
- 只读 session/risk smoke。
- 1 个正常 SKU、1 个已抢光 SKU，可选 1 个下架/不可推广 SKU。
- batch limit 2–3。
- 正常 SKU 得到可信短链；终态进入 unavailable；不增加 failure fuse。
- 验证 state、report、exit code、observer 恢复。

### Phase C：完成 221 accounting

- 复用已有 72 linked。
- 小批次处理剩余 149。
- terminal 不重试。
- 完成标准：`linked + unavailable = 221`、pending=0、overlap=0、duplicate=0。

### Phase D：验证与候选冻结

- canonical validation。
- 校验 queue checksum、row count、JSON、duplicate、extra、overlap、trusted URL、required fields、record hash、source tab。
- `merge_allowed=true`。
- `commercial_enabled` 继续 false。
- 固定 commit、artifact 和 manifest。

### Phase E：Data Lab MySQL

- 现场核验数据库、账号、migration 和 feature flags。
- 未初始化则按 V1 migration 初始化。
- 回填 3304 基线及已验证 HZ24 增量。
- JSONL/MySQL 一致性。
- dual-write 完整轮次。
- 发布 `v_published_commission_products`。

### Phase F：AIdeal CPS 生产交付

- 使用固定 commit/artifact 或短生命周期 SSH Tunnel。
- dry-run 输出 insert/update/skip/reject。
- 显式批准后幂等同步/import。
- landed validation、抽样核验和 rollback 演练。

### Phase G：稳定期和商用

- 连续稳定运行至少一周。
- 链接刷新队列、过期治理、数据质量报告和告警。
- 显式批准商用。
- 逐步退役 HZ11–HZ23 legacy 路径。

## 6. 新对话第一任务

只推进 Phase A。不要直接执行 221 SKU，不要直接初始化数据库，不要宣称商用。先以当前 GitHub HEAD 的第一个真实静态阻断为单一问题进行修复。
