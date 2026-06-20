# 文档权威顺序

更新日期：2026-06-20

## 1. 当前主线

```text
1. 当前 main 代码与绑定当前 HEAD 的运行报告
2. docs/status/COMMERCIALIZATION_STATUS_20260620.md
3. docs/project/CURRENT_PROJECT_CONTEXT.md
4. docs/project/PROJECT_MEMORY_20260620.md
5. docs/project/CODE_CHANGE_GUARDRAILS.md
6. docs/project/CODE_CHANGE_GUARDRAILS_IMPLEMENTATION.md
7. docs/project/EXECUTION_TOPOLOGY.md
8. docs/project/ENVIRONMENT_AND_WORKING_RULES.md
9. docs/architecture/COMMISSION_DATA_MYSQL_SYNC_V1.md
10. docs/architecture/commission_data_mysql_v1.sql
11. docs/project/NEXT_CHAT_HANDOFF_PROMPT.md
```

`COMMERCIALIZATION_STATUS_20260619.md` 及更早状态文件只作为历史快照，不再作为当前默认状态入口。

## 2. 当前运行报告

至少读取：

```text
reports/project_engineering_audit_latest.json
reports/offline_quality_latest.json
reports/hz23_round_latest.json
data/export/aideal_cps_products_commercial_candidate_manifest.json
reports/hz24_tab_overlap_analysis_latest.json
reports/hz24_increment_collection_latest.json
```

若存在，还应读取：

```text
reports/hz24_sold_out_migration_latest.json
reports/hz24_terminal_repair_latest.json
reports/hz24_resume_gate_latest.json
reports/hz24_collection_authorization_latest.json
reports/hz24_collection_guard_latest.json
```

报告使用规则：

- 检查 `generated_at`；
- 检查 `git_head` 是否等于当前 main；
- 检查 round_id、schema、checksum 和返回码；
- 报告不存在时不能根据测试代码推断生产动作已执行；
- 陈旧报告不能放行下一阶段；
- 失败后禁止复用上一轮 latest 报告伪装当前成功。

## 3. 当前关键事实

### HZ23

- 2026-06-15 的 3304 条是最后一次已验证 last-known-good 基线；
- 当前 latest manifest 为 0 行且 `candidate_integrity_ready=false`；
- 当前 latest 不能用于 MySQL 或商用；
- 必须在杭州生产机只读恢复并核验 last-known-good 候选。

### HZ24

- 队列 221；
- 旧采集 linked 72；
- 明确 sold-out 5；
- 旧 pending 149，预计可行动 144；
- v2 代码和离线测试已存在；
- 没有生产报告证明 5 条迁移和 72/5/144 已在杭州落地；
- 继续暂停。

### 工程治理

- 最新已发布审计报告为 210 个全局 blocker；
- active/compatibility blocker 为 0，但 global gate 仍失败；
- 审计器尚未完整覆盖重复变量、常量和配置键；
- 完成该能力并取得全局零 blocker 前，不得宣称代码问题 100% 解决。

## 4. 环境角色

```text
杭州 Data Lab 生产：121.41.111.36 / cpsdata
新加坡 CI Bridge：43.106.55.255 / datalab
杭州 AIdeal CPS 生产：8.136.28.6 / deploy
```

用户可从杭州 `cpsdata` SSH 进入新加坡 `datalab`，但执行角色不变：

- 杭州运行真实采集和未来 Data Lab MySQL；
- 新加坡只运行离线编译、测试、审计和脱敏报告回写；
- AIdeal CPS 生产只消费发布版本。

## 5. 过渡与兼容文档

以下文件保留用于 JSONL 快照、审计、灾备和兼容，但旧的 rsync-only 设计已被 MySQL V1 取代：

```text
docs/contracts/AIDEAL_CPS_PRODUCT_FEED_V1.md
docs/contracts/aideal-cps-product-feed-v1.schema.json
docs/contracts/aideal-cps-product-feed-manifest-v1.schema.json
```

JSONL 的长期角色：

```text
回填输入
不可变快照
审计与灾备
跨系统兜底出口
```

## 6. 工程门禁

代码修改必须遵守：

```text
docs/project/CODE_CHANGE_GUARDRAILS.md
docs/project/CODE_CHANGE_GUARDRAILS_IMPLEMENTATION.md
reports/project_engineering_audit_latest.json
reports/offline_quality_latest.json
```

正式验收要求全局 blocker、重复定义、重复赋值、重复实现、大文件和长函数全部为 0，且离线报告绑定当前 main。

历史实验代码保留在 Git 历史或只读快照分支，从 main 移除；不得通过降低严重度或扩大排除范围伪造通过。

## 7. 冲突处理

- 当前 main 和绑定当前 HEAD 的报告优先于文档；
- `COMMERCIALIZATION_STATUS_20260620.md` 是当前任务状态；
- `CURRENT_PROJECT_CONTEXT.md` 是当前事实总入口；
- `PROJECT_MEMORY_20260620.md` 是长期设计、环境和交互记忆；
- `EXECUTION_TOPOLOGY.md` 定义服务器角色和 SSH 操作方向；
- `CODE_CHANGE_GUARDRAILS*` 定义强制工程门禁；
- MySQL V1 优先于旧 rsync-only 设计；
- Secret、账号和真实密码永远只以服务器 Secret/.env 为准；
- breaking change 必须新建合同版本；
- 2026-06-19 及更早状态只用于历史比较；
- HZ24 完整校验前保持隔离；
- 当前无效 0 行 manifest 不得覆盖或代表 3304 last-known-good 基线。
