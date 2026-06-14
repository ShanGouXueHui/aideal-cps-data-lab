# DL2 HZ23 Commercial Observation Plan

更新日期：2026-06-14

## Status

HZ22 已完成 page 61-67，`commercial_segment_complete=true`，可信推广链接池达到 2385 个 SKU。

HZ23 是生产观察层，不自动启用 AIdeal CPS 商用消费。

### 已完成

2026-06-14 10:05 首次日常探针已提交 GitHub：

```text
commit=7aeb147
page=50
prepare_ok=true
scan_ok=true
scanned=59
risk=[]
```

探针中的 `new=59` 代表 HZ23 本地目录索引首次初始化，不代表重新生成 59 条推广链接。

### 尚未完成

首次完整 1-67 页观察轮次计划于：

```text
2026-06-15 09:56 server-local
```

截至 2026-06-14 本文更新时，GitHub 尚无完整轮次完成报告，因此商用观察尚未最终通过。

## Runtime policy

- Browser automation window: server-local 09:30-21:30 only.
- Night mode: heartbeat only; no JD page operation.
- Daily probe: one randomly selected page from 1, 17, 34, 50, 67.
- Probe selects 商品推广/全部商品, verifies the 4000-row pool, scans cards, and does not request links for known SKUs.
- Full refresh: random interval of 3-5 days after a completed round.
- Observation bootstrap may schedule the first full round in the next daytime window.
- Item wait: random 3-7 seconds for new-link operations.
- Page wait: random 90-210 seconds.
- Strong verification signals only: risk_handler, 京东验证, 快速验证, 安全验证, 验证码, 滑块.
- “购物无忧”等普通页面文案不是风险信号。
- Any strong verification signal stops the round and preserves a checkpoint. No bypass is attempted.

## Data semantics

- Every visible card updates `last_checked_at` and `last_seen_at`.
- Unchanged cards only update timestamps.
- Changed title, price, commission rate, estimated income, image, or item URL increments `change_count` and writes history.
- New SKUs use the validated HZ21 exact-SKU card click to obtain a promotion link.
- Missing SKUs increment `missing_rounds` only after a complete 1-67 round.
- Two complete missing rounds mark an item inactive.
- Candidate JSONL + manifest remain available for snapshot, audit and MySQL migration input.
- `commercial_enabled` remains false during observation.

## Observation acceptance criteria

Observe for at least 48-72 hours and require all of the following:

1. `aideal-hz23-observer.service` remains active with automatic restart available.
2. At least two daily probes complete without strong-risk stop or page-selection error.
3. At least one complete HZ23 1-67 round reports:
   - `commercial_segment_complete=true`
   - `unfinished_pages=[]`
   - `stop_reason=null`
4. Catalog scan coverage is at least 3900 unique SKUs in the completed round.
5. Candidate manifest reports:
   - `duplicate_sku_count=0`
   - `round_complete=true`
   - `observation_ready=true`
6. No unsafe HZ20 rows re-enter the trusted data set.
7. The candidate remains read-only and is not yet consumed by AIdeal CPS user traffic.

## MySQL migration gate

Observation期间可以提前完成：

- MySQL schema/DDL；
- Repository 分层；
- JSONL 回填器；
- 数据一致性校验；
- SSH Tunnel 和只读同步代码；
- migration upgrade/downgrade 测试。

但以下开关必须保持 false：

```text
DATA_LAB_DB_WRITE_ENABLED=false
DATA_LAB_DB_DUAL_WRITE_ENABLED=false
DATA_LAB_PUBLISH_ENABLED=false
DATA_LAB_SYNC_ENABLED=false
```

只有 Observation acceptance criteria 全部通过后，才执行：

1. Data Lab MySQL 正式回填；
2. dual-write 观察；
3. 发布只读视图；
4. AIdeal CPS dry-run 同步；
5. 灰度和正式商用。

MySQL 目标架构：

```text
docs/architecture/COMMISSION_DATA_MYSQL_SYNC_V1.md
docs/architecture/commission_data_mysql_v1.sql
```
