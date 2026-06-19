# 文档权威顺序

更新日期：2026-06-18

## 当前主线

```text
1. 最新可验证代码与运行报告
2. docs/project/CODE_CHANGE_GUARDRAILS_IMPLEMENTATION.md
3. docs/project/CODE_CHANGE_GUARDRAILS.md
4. docs/project/CURRENT_PROJECT_CONTEXT.md
5. docs/status/COMMERCIALIZATION_STATUS_20260614.md
6. docs/architecture/COMMISSION_DATA_MYSQL_SYNC_V1.md
7. docs/architecture/commission_data_mysql_v1.sql
8. docs/ops/DL2_HZ23_COMMERCIAL_OBSERVATION_PLAN.md
9. docs/project/ENVIRONMENT_AND_WORKING_RULES.md
10. docs/project/NEXT_CHAT_HANDOFF_PROMPT.md
```

## 过渡/兼容文档

以下文件继续保留，用于观察期 JSONL、快照、审计、灾备和兼容，但其中“正式商用使用 rsync 文件作为唯一主通道”的设计已经被 MySQL V1 目标架构取代：

```text
docs/contracts/AIDEAL_CPS_PRODUCT_FEED_V1.md
docs/contracts/aideal-cps-product-feed-v1.schema.json
docs/contracts/aideal-cps-product-feed-manifest-v1.schema.json
```

JSONL 不会废弃；它从“未来唯一在线数据源”调整为：

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

## 冲突处理

- 运行事实优先于文档假设；
- `CODE_CHANGE_GUARDRAILS_IMPLEMENTATION.md` 定义当前有效扫描入口和报告路径；
- `CODE_CHANGE_GUARDRAILS.md` 对代码修改流程、重复定义、硬编码和大文件拆分具有强制约束；
- MySQL V1 优先于旧 rsync-only 设计；
- Secret、账号和真实密码永远不以文档为准，只以服务器 Secret/.env 为准；
- 任何 breaking change 必须新建版本，不静默改变 V1 字段语义。
