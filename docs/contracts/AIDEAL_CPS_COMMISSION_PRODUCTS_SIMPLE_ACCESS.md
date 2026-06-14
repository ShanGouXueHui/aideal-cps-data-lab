# AIdeal CPS 佣金产品数据：简明访问约定

## 当前事实

Data Lab 当前不对外提供 MySQL/PostgreSQL 数据库，也没有对外数据库账号、密码或远程表。

佣金产品权威数据以 JSONL 快照方式发布。AIdeal CPS 从 Data Lab 服务器通过只读 SSH/rsync 拉取文件，再导入自己的本地 MySQL。

## Data Lab 信息

```text
服务器：121.41.111.36
SSH 用户：cpsdata
项目目录：/home/cpsdata/projects/aideal-cps-data-lab
```

观察期出口：

```text
data/export/aideal_cps_products_commercial_candidate_latest.jsonl
data/export/aideal_cps_products_commercial_candidate_manifest.json
```

正式商用出口：

```text
data/export/aideal_cps_products_commercial_latest.jsonl
data/export/aideal_cps_products_commercial_manifest.json
```

AIdeal CPS 服务器：

```text
服务器：8.136.28.6
SSH 用户：deploy
本地数据库：MySQL / aideal_cps
目标表：products
```

## 当前数据状态

截至 2026-06-14：

```text
京东全部商品展示池：4000 条
可信推广短链 SKU：2385 条
HZ23 首次日常探针：成功
探针页：50
扫描商品：59 条
风险验证：无
状态：48-72 小时观察中，尚未正式启用商用导入
```

## JSONL 主要字段

```text
sku
title
item_url
promotion_url
short_url
image_url
price
commission_rate
estimated_commission
status
link_created_at
link_expire_at
refresh_due_at
last_checked_at
last_seen_at
source_round_id
source_updated_at
source_payload_hash
```

## 固定规则

1. 不提供远程数据库连接。
2. 不建立长期 SSH tunnel。
3. AIdeal CPS 使用专用只读 SSH key 拉取文件。
4. 观察期 candidate 只做 dry-run。
5. `commercial_enabled=true` 后才能正式导入。
6. AIdeal CPS 用户请求始终读取本地 MySQL，不实时访问 Data Lab。
7. 密码、私钥、Cookie、浏览器 Profile 不写入 GitHub。
