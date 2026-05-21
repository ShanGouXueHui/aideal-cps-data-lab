# HZ12 Product All Full Check

- Generated at: 2026-05-21 16:00:15
- STOP exists: False
- rows=52, ok=52, dedup_sku=52, non_numeric=0
- pages=3, first_page=1, last_page=3
- missing={'title': 33, 'image_url': 1, 'item_url': 0, 'price': 0, 'commission_rate': 0, 'estimated_income': 0, 'short_url': 0, 'long_url': 0, 'qr_url': 0, 'jd_command': 0, 'link_created_at': 0, 'link_expire_at': 0, 'refresh_due_at': 0}
- throughput={'first_ts': '2026-05-18T04:02:00', 'last_ts': '2026-05-18T04:16:07', 'runtime_hours_est': 0.235, 'estimated_ok_per_hour': 221.02, 'estimated_ok_per_day': 5304.37, 'estimated_days_to_4000': 0.75}
- ready_for_dry_run_import=False

## Next decision

If no STOP and quality is good, continue collection until roughly 4000 SKU. If STOP exists, inspect stop reason before restart.
