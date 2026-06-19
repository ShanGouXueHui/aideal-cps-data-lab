# 活跃主线与历史实验路径分类

更新日期：2026-06-19

## 1. 目的

本文件用于把工程审计发现区分为生产活跃主线、运行支撑路径、待确认兼容路径和历史实验归档候选。未经本文件确认，不得仅凭 HZ 编号批量排除审计结果。

当前最新全仓审计基线：

```text
files_scanned=255
blocker_count=387
```

## 2. 生产活跃主线

### HZ23

```text
run/hz23_finalize_round.py
scripts/hz23_refresh_manifest_gates.py
scripts/hz23_quarantine_unsafe_source_rows.py
scripts/hz23_install_service.sh
```

### HZ24

```text
run/hz24_collect_increment_links_v2.py
scripts/hz24_audit_product_tabs.py
scripts/hz24_analyze_tab_overlap.py
scripts/hz24_build_increment_queue.py
scripts/hz24_validate_increment_outcomes.py
src/aideal_cps_data_lab/hz24/**
```

### 候选校验与商用发布

```text
src/aideal_cps_data_lab/application/candidate_validation.py
src/aideal_cps_data_lab/contracts/**
scripts/hz23_refresh_manifest_gates.py
```

### Data Lab MySQL

```text
src/aideal_cps_data_lab/domain/**
src/aideal_cps_data_lab/persistence/**
scripts/plan_commission_mysql_initialization.py
scripts/backfill_commission_products_mysql.py
scripts/verify_commission_mysql_payload_hashes.py
scripts/verify_commission_mysql_post_migration.py
docs/architecture/COMMISSION_DATA_MYSQL_SYNC_V1.md
docs/architecture/commission_data_mysql_v1.sql
```

### 工程审计与配置

```text
scripts/engineering_scan_full.py
src/aideal_cps_data_lab/engineering_audit/**
config/engineering-audit.toml
.github/workflows/engineering-audit.yml
```

## 3. 运行支撑路径

以下目录仍参与离线测试、配置、报告、迁移和灾备，不能按历史代码排除：

```text
config/**
tests/**
reports/**
data/export/**
docs/project/**
docs/status/**
```

运行态数据文件可以不提交原始内容，但必须提交不含敏感信息的 manifest、计数、checksum 和校验报告，保证 GitHub 可验证。

## 4. 待确认兼容路径

```text
run/hz21_*
run/hz22_*
scripts/hz21_*
scripts/hz22_*
```

这些文件可能仍被 HZ23/HZ24 适配器或恢复流程引用。在完成 import、subprocess、systemd 和 shell 调用关系扫描前，不得标记为归档，也不得从 blocker 门禁中静默排除。

## 5. 历史实验归档候选

```text
run/hz11_* ... run/hz20_*
scripts/hz11_* ... scripts/hz20_*
```

只有同时满足以下条件，才可转为只读归档并从活跃 blocker 统计中剥离：

1. 不被活跃 Python import；
2. 不被活跃 shell、systemd、cron 或 workflow 调用；
3. 不写入 current/latest 正式数据文件；
4. 不作为 MySQL 回填、发布或恢复入口；
5. 已迁移到明确的 archive 目录或由审计配置显式标记；
6. 归档排除规则有离线测试，且全量审计仍保留归档问题计数。

## 6. 当前活跃 blocker 组

按最新报告，优先处理：

1. HZ23：长函数、重复 JSON/URL 校验实现、systemd 路径硬编码；
2. HZ24：测重和队列脚本长函数、重复加载/可信 URL 实现、浏览器 selector 配置；
3. 候选校验：`validate_candidate` 长函数及 schema 常量收口；
4. MySQL：repository 大文件、长函数、重复 scalar/duplicate 查询、localhost 硬编码；
5. 测试夹具：区分真实生产硬编码与测试域名/样例数据，避免误报掩盖真实 blocker。

## 7. HZ24 恢复门禁

当前保持暂停。恢复前必须同时满足：

```text
72 linked 数据文件逐行可验证且数量不减少
5 sold-out 已迁移为 unavailable
linked/unavailable overlap=0
queue=linked+unavailable+pending
当前 HEAD 离线测试通过
活跃主线 blocker 门禁通过
JD live 未被自动化测试调用
```

本文件只完成路径分类，不代表上述门禁已经通过。
