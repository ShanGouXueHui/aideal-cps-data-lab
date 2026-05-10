# DL2 HZ11L Product_all STOP Diagnosis

- Generated at: 2026-05-11 02:35:46
- product_all log: logs/hz11k_product_all_30min_20260511_015230.log
- high_commission log: logs/hz11k_high_commission_30min_20260511_015230.log

## STOP

- product_all: {'empty_streak': 40, 'mode': 'product_all', 'page_no': 41, 'reason': 'empty_streak_limit', 'ts': '2026-05-11 02:09:28', 'worker': 'product_all'}
- high_commission: None

## Output counts

- product_all: rows=3, ok=3, dedup_sku=3
- high_commission: rows=21, ok=21, dedup_sku=21
- multi_menu: rows=84, ok=84, dedup_sku=84

## Next rule

Do not restart product_all until STOP reason is reviewed. high_commission can be tuned for pagination after product_all STOP is understood.
