# DL2 HZ11D Parser Smoke Summary

- Generated at: 2026-05-10 19:06:17
- Scope: product_all dedupe/latest patch; high_commission custom card parser and hover click.

## Output Counts

- product_all: rows=3, ok=3, dedup_sku=3, sku_sources={'unknown': 3}
- high_commission: rows=0, ok=0, dedup_sku=0, sku_sources={}
- multi_menu: rows=63, ok=63, dedup_sku=63, sku_sources={'unknown': 63}

## Next Decision

If high_commission ok > 0 and no STOP, run both workers for 15-30 minutes to measure throughput.
