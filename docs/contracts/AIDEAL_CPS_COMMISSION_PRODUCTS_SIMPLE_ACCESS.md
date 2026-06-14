# AIdeal CPS 佣金产品数据：简明访问约定

更新日期：2026-06-14

## 当前阶段

Data Lab 当前尚未建设正式 MySQL 主库，权威运行数据仍是 JSONL、state、history 和 report。

观察期内 AIdeal CPS 不直接消费数据，只允许验证候选 JSONL。

```text
Data Lab：cpsdata@121.41.111.36
项目：/home/cpsdata/projects/aideal-cps-data-lab
候选文件：data/export/aideal_cps_products_commercial_candidate_latest.jsonl
候选 manifest：data/export/aideal_cps_products_commercial_candidate_manifest.json
```

## 当前数据状态

```text
京东全部商品展示池：4000 条
可信推广短链 SKU：2385 条
HZ23 首次日常探针：成功
探针页：50
扫描商品：59 条
风险验证：无
首次 1-67 页全量观察轮次：截至本文更新尚无 GitHub 完成报告
当前状态：48-72 小时观察中
```

## 观察通过后的正式方式

观察通过后，Data Lab 将建立：

```text
MySQL 数据库：aideal_cps_data_lab
主表：commission_products
轮次表：commission_refresh_runs
历史表：commission_product_history
发布版本表：commission_publish_versions
只读视图：v_published_commission_products
```

AIdeal CPS 固定访问方式：

```text
AIdeal CPS：deploy@8.136.28.6
本地 Tunnel：127.0.0.1:13306
SSH 目标：cpsdata@121.41.111.36
Data Lab MySQL：127.0.0.1:3306
数据库：aideal_cps_data_lab
只读用户：aideal_cps_ro
```

使用定时任务建立短生命周期 SSH Tunnel，同步结束立即关闭。不开放公网 3306，不使用长期常驻 Tunnel。

AIdeal CPS 将只读视图数据 upsert 到自己的本地：

```text
MySQL：aideal_cps
表：products
唯一键：jd_sku_id
```

用户请求始终只访问 AIdeal CPS 本地 MySQL，不实时访问 Data Lab。

## 核心字段

```text
jd_sku_id / sku
标题 title
详情页 item_url
推广链接 promotion_url
图片 image_url
价格 price
佣金率 commission_rate
预估佣金 estimated_commission
商品状态 status
推广链接生成/过期/刷新时间
最近检查/出现时间
轮次 source_round_id
数据 hash source_payload_hash
```

## 安全规则

1. MySQL 只监听 Data Lab `127.0.0.1`。
2. AIdeal CPS 使用专用 SSH Key 和只读 MySQL 用户。
3. 密码、私钥、Cookie、浏览器 Profile 不进入 GitHub。
4. 观察验收通过前不启用 Data Lab MySQL 正式写入和 AIdeal CPS 正式同步。
5. JSONL 永久保留为快照、审计和灾备出口。

详细设计：

```text
docs/architecture/COMMISSION_DATA_MYSQL_SYNC_V1.md
docs/architecture/commission_data_mysql_v1.sql
```
