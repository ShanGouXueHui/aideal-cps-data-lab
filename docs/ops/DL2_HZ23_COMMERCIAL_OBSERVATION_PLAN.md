# DL2 HZ23 Commercial Observation Plan

## Status

HZ22 completed pages 61-67 with `commercial_segment_complete=true`. The trusted link pool reached 2,385 SKUs. HZ23 is the production-observation layer and does not enable Aideal CPS consumption automatically.

## Runtime policy

- Browser automation window: server-local 09:30-21:30 only.
- Night mode: heartbeat only; no JD page operation.
- Daily probe: one randomly selected page from 1, 17, 34, 50, 67. It selects 商品推广/全部商品, verifies the 4,000-row pool, scans cards, and does not request links for known SKUs.
- Full refresh: random interval of 3-5 days after a completed round.
- Observation bootstrap: the installer command may move the first HZ23 full round to the next daytime window. Later rounds retain the 3-5 day interval.
- Item wait: random 3-7 seconds for new-link operations.
- Page wait: random 90-210 seconds.
- Strong verification signals only: risk_handler, 京东验证, 快速验证, 安全验证, 验证码, 滑块.
- Any strong verification signal stops the round and preserves a checkpoint. No bypass is attempted.

## Data semantics

- Every visible card updates `last_checked_at` and `last_seen_at` in the HZ23 catalog index.
- Unchanged cards only update timestamps.
- Changed title, price, commission rate, estimated income, image, or item URL increments `change_count` and writes a history event.
- New SKUs use the validated HZ21 exact-SKU card click to obtain a promotion link.
- Missing SKUs increment `missing_rounds` only after a complete 1-67 round; two complete missing rounds mark an item inactive.
- The commercial candidate is an atomic JSONL export plus a manifest. `commercial_enabled` remains false during observation.

## Observation acceptance criteria

Observe for at least 48-72 hours and require all of the following:

1. `aideal-hz23-observer.service` remains active with automatic restart available.
2. At least two daily probes complete without strong-risk stop or page-selection error.
3. At least one complete HZ23 1-67 round reports:
   - `commercial_segment_complete=true`
   - `unfinished_pages=[]`
   - `stop_reason=null`
4. Catalog scan coverage is at least 3,900 unique SKUs in the completed round.
5. Candidate manifest reports:
   - `duplicate_sku_count=0`
   - `round_complete=true`
   - `observation_ready=true`
6. No unsafe HZ20 rows re-enter the trusted data set.
7. The candidate remains read-only and is not yet consumed by Aideal CPS.

After these criteria pass, create a separate promotion commit that changes the commercial manifest from `commercial_enabled=false` to `true` and configure Aideal CPS to consume only the promoted export.
