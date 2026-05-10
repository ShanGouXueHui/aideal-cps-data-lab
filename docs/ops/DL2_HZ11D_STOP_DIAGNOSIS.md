# DL2 HZ11D STOP Diagnosis

- Generated at: 2026-05-10 19:10:33
- High commission log: logs/hz11d_high_commission_smoke_20260510_190118.log

## STOP files

```json
{
  "high_commission": {
    "fail_streak": 3,
    "last_error": "RuntimeError('short_url_not_found')",
    "mode": "high_commission",
    "reason": "max_fail_streak_reached",
    "ts": "2026-05-10 19:06:17",
    "worker": "high_commission"
  },
  "product_all": null
}
```

## High commission key events

```json
[
  {
    "event": "HC_CARDS",
    "fresh": 18,
    "mode": "high_commission",
    "page_info": {
      "one_key_count": 1,
      "promo_hit": true,
      "risk": [],
      "tab_click": {
        "clicked": "高佣榜",
        "index": 188,
        "ok": true,
        "text": "高佣榜"
      },
      "url": "https://union.jd.com/proManager/realTimeRankings"
    },
    "processed": 0,
    "sample": [
      {
        "income": "0.44",
        "price": "1.10",
        "rank_index": "",
        "rate": "40%",
        "sku": "",
        "title": "红枣骏枣大枣煲汤煮粥零食软糯甘甜果肉饱满送礼滋补山西仓发 250g*1袋"
      },
      {
        "income": "0.45",
        "price": "1.80",
        "rank_index": "",
        "rate": "25%",
        "sku": "",
        "title": "【拍两单发货！清仓】灯饰照明7号电池适用遥控器电视风扇计算器 家庭简装【超优惠】 金昊电池7号/到手二粒【长续航】"
      },
      {
        "income": "0.45",
        "price": "4.99",
        "rank_index": "",
        "rate": "9%",
        "sku": "",
        "title": "铝箔保鲜袋食品级铝钛箔冰箱食物密封自封袋冷冻冷藏收纳袋 镀铝保鲜袋60个【小号30个+中号20个+大号10个】"
      },
      {
        "income": "0.55",
        "price": "1.10",
        "rank_index": "",
        "rate": "50%",
        "sku": "",
        "title": "云南黄冰糖老冰糖土冰糖甘蔗多晶冰糖家用煲汤泡水 100g*1袋"
      },
      {
        "income": "0.40",
        "price": "1.01",
        "rank_index": "",
        "rate": "40%",
        "sku": "",
        "title": "京喜指数【一周不重样】时尚可爱美拉德头绳小熊高马尾弹力发圈 主推混色5根 1件套"
      }
    ],
    "scroll_round": 0,
    "total": 18,
    "ts": "2026-05-10 19:02:17",
    "worker": "high_commission"
  },
  {
    "err": "RuntimeError('short_url_not_found')",
    "event": "ITEM_FAIL",
    "fail_streak": 1,
    "mode": "high_commission",
    "rank_index": "",
    "scroll_round": 0,
    "title": "红枣骏枣大枣煲汤煮粥零食软糯甘甜果肉饱满送礼滋补山西仓发 250g*1袋",
    "ts": "2026-05-10 19:03:19",
    "worker": "high_commission"
  },
  {
    "err": "RuntimeError('short_url_not_found')",
    "event": "ITEM_FAIL",
    "fail_streak": 2,
    "mode": "high_commission",
    "rank_index": "",
    "scroll_round": 0,
    "title": "【拍两单发货！清仓】灯饰照明7号电池适用遥控器电视风扇计算器 家庭简装【超优惠】 金昊电池7号/到手二粒【长续航】",
    "ts": "2026-05-10 19:04:51",
    "worker": "high_commission"
  },
  {
    "err": "RuntimeError('short_url_not_found')",
    "event": "ITEM_FAIL",
    "fail_streak": 3,
    "mode": "high_commission",
    "rank_index": "",
    "scroll_round": 0,
    "title": "铝箔保鲜袋食品级铝钛箔冰箱食物密封自封袋冷冻冷藏收纳袋 镀铝保鲜袋60个【小号30个+中号20个+大号10个】",
    "ts": "2026-05-10 19:06:16",
    "worker": "high_commission"
  },
  {
    "event": "STOP_REQUIRED",
    "fail_streak": 3,
    "last_error": "RuntimeError('short_url_not_found')",
    "mode": "high_commission",
    "reason": "max_fail_streak_reached",
    "ts": "2026-05-10 19:06:17",
    "worker": "high_commission"
  }
]
```

## Next rule

Do not restart high_commission until STOP reason is reviewed.
