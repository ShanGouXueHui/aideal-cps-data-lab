# 文档权威顺序

更新日期：2026-06-20

## 当前主线

```text
1. 最新可验证代码与运行报告
2. docs/project/CODE_CHANGE_GUARDRAILS_IMPLEMENTATION.md
3. docs/project/CODE_CHANGE_GUARDRAILS.md
4. docs/project/CURRENT_PROJECT_CONTEXT.md
5. docs/status/COMMERCIALIZATION_STATUS_20260619.md
6. docs/project/EXECUTION_TOPOLOGY.md
7. docs/project/ENVIRONMENT_AND_WORKING_RULES.md
8. docs/architecture/COMMISSION_DATA_MYSQL_SYNC_V1.md
9. docs/architecture/commission_data_mysql_v1.sql
10. docs/ops/DL2_HZ23_COMMERCIAL_OBSERVATION_PLAN.md
11. docs/project/NEXT_CHAT_HANDOFF_PROMPT.md
```

最新运行报告至少包括：

```text
reports/hz23_round_latest.json
data/export/aideal_cps_products_commercial_candidate_manifest.json
reports/hz24_tab_overlap_analysis_latest.json
reports/hz24_increment_collection_latest.json
reports/project_engineering_audit_latest.json
```

## 当前事实优先级

```text
代码和本轮报告
> 当前项目上下文
> 2026-06-19 商用状态快照
> 执行拓扑
> 工程门禁
> MySQL V1 架构
> HZ23 旧观察计划
> HZ11-HZ22 历史实验文档
```

运行报告必须检查 `generated_at`、round_id、结构 checksum 和本轮返回码，禁止失败后复用旧报告。

## 过渡/兼容文档

以下文件继续保留，用于 JSONL 快照、审计、灾备和兼容，但其中“rsync 文件是唯一商用在线通道”的旧设计已经被 MySQL V1 取代：

```text
docs/contracts/AIDEAL_CPS_PRODUCT_FEED_V1.md
docs/contracts/aideal-cps-product-feed-v1.schema.json
docs/contracts/aideal-cps-product-feed-manifest-v1.schema.json
```

JSONL 的长期角色：

```text
观察期候选数据
MySQL 回填输入
不可变快照
审计和灾备
跨系统兜底出口
```

当前简明访问说明：

```text
docs/contracts/AIDEAL_CPS_COMMISSION_PRODUCTS_SIMPLE_ACCESS.md
```

## 工程门禁

代码修改必须遵守：

```text
docs/project/CODE_CHANGE_GUARDRAILS.md
docs/project/CODE_CHANGE_GUARDRAILS_IMPLEMENTATION.md
reports/project_engineering_audit_latest.json
```

当前全仓审计基线以 `reports/project_engineering_audit_latest.json` 的最新 `git_head` 为准，不再复用旧的固定计数。

大量问题位于历史实验脚本。必须先区分活跃主线与只读历史归档，再治理活跃 HZ23/HZ24/MySQL 路径。不得继续向已超阈值的大文件叠加业务逻辑。

## 冲突处理

- 运行事实优先于文档假设；
- `CURRENT_PROJECT_CONTEXT.md` 是当前项目事实总入口；
- `COMMERCIALIZATION_STATUS_20260619.md` 是当前任务进展快照；
- `EXECUTION_TOPOLOGY.md` 定义杭州 Data Lab 生产、新加坡 CI Bridge 和杭州 AIdeal CPS 生产的唯一角色边界；
- `CODE_CHANGE_GUARDRAILS_IMPLEMENTATION.md` 定义有效扫描入口、报告和 CI；
- `CODE_CHANGE_GUARDRAILS.md` 对修改前扫描、重复定义、硬编码和大文件拆分具有强制约束；
- MySQL V1 优先于旧 rsync-only 设计；
- Secret、账号和真实密码永远只以服务器 Secret/.env 为准；
- breaking change 必须新建版本，不静默改变 V1 字段语义；
- HZ24 在完整校验前保持隔离，不直接改变 3304 条 HZ23 商用基线。
