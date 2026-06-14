# 佣金商品 MySQL 同步架构 V1

更新日期：2026-06-14

状态：观察期后的目标商用架构。观察期内可以完成准备，但不得在 HZ23 商用验收前切换正式数据源。

## 1. 决策摘要

### 当前阶段

Data Lab 当前以 JSONL、state、history 和 report 保存数据，尚未建设正式 MySQL 主库。

### 目标阶段

HZ23 观察通过后：

1. 在 Data Lab 服务器安装/启用本地 MySQL；
2. 建立 `aideal_cps_data_lab` 数据库；
3. 把可信佣金商品回填到 `commission_products`；
4. HZ23 事务性更新 MySQL；
5. JSONL 继续作为快照、审计和灾备；
6. AIdeal CPS 定时通过短生命周期 SSH Tunnel 读取只读视图；
7. AIdeal CPS 将数据 upsert 到自己的本地 MySQL `aideal_cps.products`；
8. 用户请求只访问 AIdeal CPS 本地库。

不开放公网 MySQL 3306，不使用长期常驻 Tunnel，不允许用户请求实时查询 Data Lab。

## 2. 为什么选择短生命周期 SSH Tunnel

两台机器均在杭州，但当前没有确认可用的同 VPC 私网地址和安全组互通信息。直接暴露 3306 风险较高。

V1 采用定时同步任务临时建立 Tunnel：

```text
AIdeal CPS deploy@8.136.28.6
127.0.0.1:13306
        |
        | ssh -L，任务开始时建立
        v
cpsdata@121.41.111.36
127.0.0.1:3306
```

同步结束立即关闭 Tunnel。

优点：

- MySQL 只监听 Data Lab localhost；
- 无公网数据库端口；
- 只读 MySQL 用户；
- SSH Key 可限制来源 IP、禁止 PTY/转发扩展；
- 同步失败不影响 AIdeal CPS 现有本地数据；
- 后续确认同 VPC 私网后，可替换 Transport，不改变 Repository 和数据合同。

## 3. 连接信息约定

### SSH

```text
SSH_HOST=121.41.111.36
SSH_USER=cpsdata
SSH_KEY=/home/deploy/.ssh/aideal_data_lab_ro_ed25519
SSH_SOURCE_SERVER=8.136.28.6
```

### Tunnel 后 MySQL

```text
DATA_LAB_DB_HOST=127.0.0.1
DATA_LAB_DB_PORT=13306
DATA_LAB_DB_NAME=aideal_cps_data_lab
DATA_LAB_DB_USER=aideal_cps_ro
DATA_LAB_DB_PASSWORD=<仅保存在 AIdeal CPS 服务器 Secret/.env>
```

Data Lab 本机：

```text
MYSQL_BIND_ADDRESS=127.0.0.1
MYSQL_PORT=3306
```

密码、私钥、真实 DSN 不进入 GitHub。

## 4. 数据库表

## 4.1 `commission_products`

当前发布商品主表。

| 字段 | 类型 | 约束/说明 |
|---|---|---|
| `id` | BIGINT | PK, auto increment |
| `jd_sku_id` | VARCHAR(64) | UNIQUE, NOT NULL |
| `title` | VARCHAR(512) | NOT NULL |
| `description` | TEXT | NULL |
| `item_url` | VARCHAR(500) | 京东详情页 |
| `promotion_url` | VARCHAR(500) | 京东联盟推广链接，NOT NULL |
| `short_url` | VARCHAR(500) | 兼容字段 |
| `long_url` | TEXT | NULL |
| `qr_url` | TEXT | NULL |
| `jd_command` | TEXT | NULL |
| `image_url` | VARCHAR(1000) | NOT NULL |
| `category_name` | VARCHAR(128) | NULL |
| `shop_name` | VARCHAR(255) | NULL |
| `price` | DECIMAL(12,2) | NOT NULL |
| `coupon_price` | DECIMAL(12,2) | NULL |
| `commission_rate` | DECIMAL(8,4) | 百分比数值，例如 12.5000 表示 12.5% |
| `estimated_commission` | DECIMAL(12,2) | NULL |
| `sales_volume` | BIGINT | NULL |
| `coupon_info` | VARCHAR(512) | NULL |
| `status` | VARCHAR(32) | active/inactive/quarantined |
| `is_published` | TINYINT(1) | 商用发布门禁 |
| `source_page_no` | SMALLINT | 1-67 |
| `source_round_id` | VARCHAR(64) | 最近完整/增量轮次 |
| `source_run_id` | VARCHAR(64) | 最近采集 run |
| `source_payload_hash` | CHAR(64) | 业务字段 hash |
| `catalog_change_count` | INT | 字段变化次数 |
| `link_created_at` | DATETIME(6) | NULL |
| `link_expire_at` | DATETIME(6) | NULL |
| `refresh_due_at` | DATETIME(6) | NULL |
| `first_seen_at` | DATETIME(6) | NOT NULL |
| `last_checked_at` | DATETIME(6) | NOT NULL |
| `last_seen_at` | DATETIME(6) | NOT NULL |
| `published_at` | DATETIME(6) | NULL |
| `created_at` | DATETIME(6) | NOT NULL |
| `updated_at` | DATETIME(6) | NOT NULL |

索引：

```text
UNIQUE(jd_sku_id)
INDEX(is_published, status)
INDEX(updated_at, id)
INDEX(refresh_due_at)
INDEX(source_round_id)
INDEX(last_seen_at)
```

## 4.2 `commission_refresh_runs`

记录探针、分页采集、全量刷新和发布。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BIGINT | PK |
| `round_id` | VARCHAR(64) | UNIQUE |
| `run_type` | VARCHAR(32) | probe/full/backfill/retry/publish |
| `status` | VARCHAR(32) | running/completed/stopped/failed |
| `page_start` | SMALLINT | NULL |
| `page_end` | SMALLINT | NULL |
| `completed_pages` | JSON/TEXT | 已完成页 |
| `unfinished_pages` | JSON/TEXT | 未完成页 |
| `scanned_count` | INT | 扫描卡片数 |
| `new_count` | INT | 新商品数 |
| `changed_count` | INT | 变化商品数 |
| `unchanged_count` | INT | 未变化数 |
| `link_ok_count` | INT | 成功领链数 |
| `link_fail_count` | INT | 失败数 |
| `risk_signals` | JSON/TEXT | 强风控信号 |
| `stop_reason` | VARCHAR(255) | NULL |
| `started_at` | DATETIME(6) | NOT NULL |
| `finished_at` | DATETIME(6) | NULL |
| `report_path` | VARCHAR(500) | GitHub/本地报告路径 |
| `created_at` | DATETIME(6) | NOT NULL |

## 4.3 `commission_product_history`

只保存业务字段变化，不为纯时间戳刷新写历史。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BIGINT | PK |
| `jd_sku_id` | VARCHAR(64) | indexed |
| `round_id` | VARCHAR(64) | indexed |
| `change_type` | VARCHAR(32) | insert/update/status/link |
| `before_payload` | JSON/TEXT | NULL |
| `after_payload` | JSON/TEXT | NOT NULL |
| `before_hash` | CHAR(64) | NULL |
| `after_hash` | CHAR(64) | NOT NULL |
| `changed_at` | DATETIME(6) | NOT NULL |

## 4.4 `commission_publish_versions`

每次对外发布的不可变版本。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | BIGINT | PK |
| `publish_version` | BIGINT | UNIQUE，单调递增 |
| `round_id` | VARCHAR(64) | UNIQUE |
| `status` | VARCHAR(32) | candidate/published/revoked |
| `row_count` | INT | NOT NULL |
| `data_sha256` | CHAR(64) | 对应 JSONL 快照 hash |
| `schema_version` | VARCHAR(64) | NOT NULL |
| `published_at` | DATETIME(6) | NULL |
| `created_at` | DATETIME(6) | NOT NULL |

## 5. 对外只读视图

AIdeal CPS 只查询：

```sql
CREATE VIEW v_published_commission_products AS
SELECT
    jd_sku_id,
    title,
    description,
    item_url,
    promotion_url,
    short_url,
    image_url,
    category_name,
    shop_name,
    price,
    coupon_price,
    commission_rate,
    estimated_commission,
    sales_volume,
    coupon_info,
    status,
    source_page_no,
    source_round_id,
    source_payload_hash,
    catalog_change_count,
    link_created_at,
    link_expire_at,
    refresh_due_at,
    last_checked_at,
    last_seen_at,
    published_at,
    updated_at
FROM commission_products
WHERE is_published = 1
  AND status = 'active';
```

只读用户授权原则：

```text
SELECT on aivist? no
SELECT only on aideal_cps_data_lab.v_published_commission_products
SELECT on aideal_cps_data_lab.commission_publish_versions
禁止 INSERT/UPDATE/DELETE/DDL
```

注意：实际 GRANT 必须只针对上述数据库和视图，不授予 `*.*`。

## 6. 写入语义

### 新商品

- 按 `jd_sku_id` insert；
- 必填字段缺失进入 quarantined，不发布；
- promotion_url 未验证不得 `is_published=1`。

### 业务字段变化

- 比较规范化 payload hash；
- hash 改变才更新业务字段并写 history；
- 更新 `catalog_change_count`；
- 重新评估发布资格。

### 未变化

只更新：

```text
last_checked_at
last_seen_at
source_round_id
source_run_id
updated_at
```

不写 history。

### 商品消失

- 单次完整轮次未出现，只增加 missing 状态计数，不下架；
- 连续两次完整成功轮次未出现，设置 inactive 和 `is_published=0`；
- 不物理删除。

## 7. 从 JSONL 回填 MySQL

迁移必须：

1. 读取现有可信 latest JSONL；
2. 按 SKU 去重；
3. 仅接受 `status=ok` 且 promotion_url/short_url 有效；
4. 金额转换为 Decimal；
5. 佣金率去掉 `%` 后转 DECIMAL；
6. 计算 payload hash；
7. 使用 staging 表或临时表校验；
8. 单事务 upsert；
9. 输出 inserted/updated/unchanged/rejected；
10. 重复执行结果幂等；
11. 数据库失败时 JSONL 源数据不受影响；
12. 回填完成后抽样验证短链、SKU、价格和佣金。

## 8. AIdeal CPS 同步流程

建议每 30-60 分钟运行一次轻量检查；完整数据规模约 2.4k-4k，V1 可以安全做全量读取并基于 hash upsert，无需过早引入复杂 CDC。

流程：

1. 获取同步锁；
2. 建立短生命周期 SSH Tunnel；
3. 查询最新 published version；
4. 若 round/version 未变化，关闭 Tunnel 并退出；
5. 查询只读视图；
6. 本地 staging 校验唯一 SKU、必填字段和金额；
7. 单事务 upsert 到 `aideal_cps.products`；
8. promotion_url 同步到 `products.promotion_url`，兼容期同时写 `product_url`；
9. 更新同步 run；
10. 关闭 Tunnel；
11. 失败时保留上一版本本地数据。

用户请求永远只读本地 `aideal_cps.products`。

## 9. 安全要求

SSH Key：

- 只允许来源 `8.136.28.6`；
- `no-agent-forwarding`；
- `no-X11-forwarding`；
- `no-pty`；
- 仅允许建立到 `127.0.0.1:3306` 的本地转发；
- 私钥权限 600；
- known_hosts 固定主机指纹。

MySQL：

- bind 127.0.0.1；
- 单独只读用户；
- 最小权限；
- 密码使用高强度随机值；
- 密码仅存双方服务器 Secret/.env；
- 日志不得打印 DSN 密码；
- 定期备份和恢复演练。

## 10. 配置变量

Data Lab：

```text
DATA_LAB_DATABASE_URL=mysql+pymysql://<writer>@127.0.0.1:3306/aideal_cps_data_lab
DATA_LAB_DB_WRITE_ENABLED=false
DATA_LAB_DB_DUAL_WRITE_ENABLED=false
DATA_LAB_PUBLISH_ENABLED=false
```

AIdeal CPS：

```text
DATA_LAB_SSH_HOST=121.41.111.36
DATA_LAB_SSH_USER=cpsdata
DATA_LAB_SSH_KEY=/home/deploy/.ssh/aideal_data_lab_ro_ed25519
DATA_LAB_TUNNEL_LOCAL_PORT=13306
DATA_LAB_DB_HOST=127.0.0.1
DATA_LAB_DB_PORT=13306
DATA_LAB_DB_NAME=aideal_cps_data_lab
DATA_LAB_DB_USER=aideal_cps_ro
DATA_LAB_DB_PASSWORD=<secret>
DATA_LAB_SYNC_ENABLED=false
```

默认所有写入/发布/同步开关为 false。验收后逐级打开。

## 11. 实施顺序

### 观察期准备

1. 增加 MySQL 依赖和配置对象；
2. 建 migration/DDL；
3. 建 domain model 和 repository 接口；
4. 实现 MySQL Repository；
5. 实现 JSONL 回填器；
6. 实现一致性验证器；
7. 测试 migration upgrade/downgrade；
8. 建 AIdeal CPS Tunnel 和只读同步代码，但保持 disabled；
9. 不改变现有 HZ23 运行路径。

### HZ23 验收通过

1. 创建正式库和 writer/readonly 用户；
2. 执行回填；
3. 通过一致性检查；
4. 开启 Data Lab dual-write；
5. 观察一个完整刷新轮次；
6. 将 MySQL 升为主写，JSONL 保留快照；
7. 建只读视图；
8. AIdeal CPS dry-run 同步；
9. 灰度启用；
10. 正式商用。

## 12. 验收标准

- migration 可升级和回滚；
- 可信 SKU 回填数量与 JSONL 去重数量一致；
- `jd_sku_id` 无重复；
- published 记录必填字段完整；
- promotion_url 均为可信京东推广域名；
- 金额与佣金字段可正确 Decimal 化；
- 重跑回填幂等；
- dual-write 一致性通过；
- AIdeal CPS 同步失败不影响旧数据服务；
- Tunnel 关闭后用户业务正常；
- 3306 未暴露公网；
- Secret 未进入 GitHub。
