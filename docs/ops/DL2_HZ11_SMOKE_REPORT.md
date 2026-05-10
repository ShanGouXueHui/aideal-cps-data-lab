# DL2 HZ11 Multi-menu Collector Smoke Report

- Generated at: 2026-05-10 18:47:06
- Menus: 商品推广/全部商品 + 实时榜单/高佣榜
- Browsers: CDP 19228 + CDP 19229
- Link expiry: 60 days; refresh after 40 days; refresh 20 days before expiry

## Status

- product_all: smoke_ok_but_duplicate_bug_patched
- high_commission: dom_probe_required_custom_parser

## Output Counts

- product_all: `{'exists': False}`
- high_commission: `{'exists': False}`
- multi_menu: `{'exists': True, 'rows': 60, 'json_bad': 0, 'ok': 60, 'dedup_sku': 60}`

## High Commission Probe Diagnosis

```json
{
  "has_card_text": true,
  "has_links": true,
  "has_visible_buttons": true,
  "one_key_count": 1,
  "promote_count": 3
}
```

## Next Fix

- high_commission needs custom DOM card parser; hz9.get_candidates returns 0 on realTimeRankings
- high_commission should click card-level visible 一键领链 after hover
- extract sku from card link/data attrs or from long_url parameters after modal opens

## Security

- no account/password/cookie/token uploaded
- raw logs not committed
- data/import jsonl not committed
- .secrets not committed
