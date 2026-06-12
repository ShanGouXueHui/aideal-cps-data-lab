# DL2 HZ15 Runtime Summary

- ts: `2026-06-13 03:13:35`
- latest_collector_log: `logs/hz15_daytime_40_67_no_reset_v6_strict_4000_20260612_093242.log`
- latest_supervisor_log: `logs/hz15_daytime_autostart_40_67_supervisor_20260611_211739.log`
- dedup_sku: `1931` / 4000 (`48.27%`)
- ok: `1931`, rows: `1931`, page_range: `1-49`, page_count: `49`
- duplicate_ok_rows: `0`, bad_rows: `0`
- missing: `{"sku": 0, "title": 55, "price": 0, "commission_rate": 0, "estimated_income": 0, "short_url": 0, "long_url": 0, "item_url": 0, "jd_command": 0, "qr_url": 2, "image_url": 1, "refresh_due_at": 0}`
- process_alive: `True`, supervisor_alive: `True`, stop_exists: `False`

## last_start
```json
{
  "event": "HZ15_NO_RESET_V6_STRICT_4000_START",
  "item_sleep": [
    18.0,
    45.0
  ],
  "page_sleep": [
    1200.0,
    2400.0
  ],
  "pages": [
    40,
    41,
    42,
    43,
    44,
    45,
    46,
    47,
    48,
    49,
    50,
    51,
    52,
    53,
    54,
    55,
    56,
    57,
    58,
    59,
    60,
    61,
    62,
    63,
    64,
    65,
    66,
    67
  ],
  "run_once": true,
  "target_total": 4000,
  "ts": "2026-06-12 09:32:44",
  "worker": "hz15_jump_pages"
}
```

## last_ready
```json
{
  "event": "PRODUCT_ALL_4000_READY",
  "result": {
    "info": {
      "activePageText": "1",
      "has4000": true,
      "hasEmpty": false,
      "jumpInputValue": "1",
      "oneKeyCount": 60,
      "pagerText": "共 4000 条 12345667 前往页",
      "risk": [],
      "skuCount": 60,
      "skus": [
        "100002715968",
        "100110649419",
        "100004750638",
        "10215045227908",
        "10205686736888",
        "10211400759003",
        "10045264429068",
        "10094985581639",
        "100223000548",
        "10056926300399",
        "100142118394",
        "100247387940",
        "10054936018699",
        "10222910433917",
        "1179700",
        "100202743593",
        "10111979115290",
        "100003837732",
        "100262352935",
        "100013418440",
        "100223952147",
        "100065712507",
        "10106501315392",
        "43679064489",
        "100041048934",
        "100268348098",
        "10159350656382",
        "10058707172967",
        "100135923655",
        "100018945358",
        "45620888234",
        "10048956971506",
        "10111585976573",
        "100088457721",
        "100028137700",
        "10068986689271",
        "10216083549649",
        "1032422664",
        "100100411695",
        "100114485006",
        "5285971",
        "100019418532",
        "69734235266",
        "10086314264251",
        "100355613622",
        "15342474",
        "100304944868",
        "10213684459613",
        "100166680177",
        "10191151504455",
        "100167474479",
        "100160556958",
        "100078726632",
        "100041959401",
        "100128361432",
        "100285924082",
        "100010318085",
        "100114383045",
        "100115693093",
        "100108850087"
      ],
      "title": "京东联盟 - 网络赚钱，流量变现，专业电商CPS联盟平台！",
      "url": "https://union.jd.com/proManager/index?pageNo=1"
    },
    "mode": "current_all_product_4000",
    "ok": true
  },
  "ts": "2026-06-12 09:32:45",
  "worker": "hz15_jump_pages"
}
```

## last_page_jump_sleep
```json
{
  "event": "PAGE_JUMP_SLEEP",
  "seconds": 1408.42,
  "target_page": 49,
  "ts": "2026-06-12 20:33:22",
  "worker": "hz15_jump_pages"
}
```

## last_page_jump
```json
{
  "event": "PAGE_JUMP",
  "result": {
    "after": {
      "activePageText": "49",
      "has4000": true,
      "hasEmpty": false,
      "jumpInputValue": "49",
      "oneKeyCount": 60,
      "pagerText": "共 4000 条 1474849505167 前往页",
      "risk": [],
      "skuCount": 60,
      "skus": [
        "100080280557",
        "100000722446",
        "10060517713860",
        "7376526",
        "1833238",
        "100054076591",
        "100016158743",
        "100107904502",
        "10102102829956",
        "10067878397475",
        "100308653594",
        "100071827459",
        "100012242106",
        "100011423974",
        "100059350371",
        "100018945358",
        "15384502",
        "10936662570",
        "11253398",
        "10169890370866",
        "10045008588925",
        "10034460389274",
        "100059215420",
        "10030016419501",
        "100126351251",
        "100047612518",
        "10214459873449",
        "10186490206197",
        "100264554364",
        "100243888579",
        "100075758806",
        "22678115139",
        "100313405078",
        "100199424442",
        "100157665218",
        "100112657824",
        "100274451578",
        "100250562290",
        "100125466079",
        "14514469",
        "12592414",
        "100260191682",
        "100038114392",
        "100158581410",
        "100011058466",
        "4423690",
        "27323144893",
        "10072510173578",
        "100222370007",
        "13813691",
        "10164676595942",
        "10096186573927",
        "100060830286",
        "72498907239",
        "347360",
        "10218674194570",
        "100356892204",
        "10106477912138",
        "100148986268",
        "100081808988"
      ],
      "title": "京东联盟 - 网络赚钱，流量变现，专业电商CPS联盟平台！",
      "url": "https://union.jd.com/proManager/index?pageNo=49"
    },
    "attempt": 1,
    "before": {
      "activePageText": "48",
      "skuCount": 60,
      "skus": [
        "100080280557",
        "100000722446",
        "10060517713860",
        "7376526",
        "1833238",
        "100054076591",
        "100016158743",
        "100107904502"
      ],
      "url": "https://union.jd.com/proManager/index?pageNo=48"
    },
    "changed": true,
    "click": {
      "attempt": 1,
      "method": "locator_fill_enter",
      "ok": true
    },
    "ok": true,
    "target_page": 49
  },
  "target_page": 49,
  "ts": "2026-06-12 20:56:53",
  "worker": "hz15_jump_pages"
}
```

## last_page_candidates
```json
{
  "event": "PAGE_CANDIDATES",
  "fresh": 38,
  "page_no": 49,
  "sample": [
    {
      "sku": "10220513705613",
      "title": "邦派奇防晒面罩女夏季冰丝薄款披肩户外开车防紫外线护颈可喝水透气口罩 云雾灰【无痕冰感防晒 掀开可喝水】"
    },
    {
      "sku": "100191839766",
      "title": "罗莱家纺蚕丝被夏凉被子 全棉A类抗菌可机洗空调被芯夏季3.2斤200*230"
    },
    {
      "sku": "10113473063835",
      "title": "金沙河全麦面粉 含麦麸无添加 新疆面粉 馒头包子饺子煎饼通用 金沙河全麦面粉5斤"
    },
    {
      "sku": "100330349470",
      "title": "得力扫码枪 二维无线扫描枪快递物流查询超市收银医保支付商品条码扫描备件库扫码器药品追溯高速款"
    },
    {
      "sku": "100279475524",
      "title": "小米(MI) 小米平板8 Pro【国家补贴】11.2英寸 3.2K护眼屏 骁龙8 至尊 澎湃OS3 12+256G 黑色"
    },
    {
      "sku": "100115256159",
      "title": "威克士20V锂电暴力涡轮风扇WU093.9(裸机)鼓风机吹风机工业吹尘枪强风"
    }
  ],
  "skipped_sku_count": 300,
  "total": 42,
  "ts": "2026-06-12 20:57:06",
  "worker": "hz15_jump_pages"
}
```

## last_item_ok
```json
{
  "event": "ITEM_OK",
  "known_sku_count": 1931,
  "page_no": 49,
  "short_url": "https://u.jd.com/7ghd2Vk",
  "sku": "10220513705613",
  "ts": "2026-06-12 20:57:11",
  "worker": "hz15_jump_pages"
}
```

## last_item_skip
```json
{
  "event": "ITEM_SKIP",
  "page_no": 49,
  "reason": "RuntimeError('short_url_not_found')",
  "skipped_sku_count": 327,
  "sku": "100141104656",
  "ts": "2026-06-12 21:32:28",
  "worker": "hz15_jump_pages"
}
```

## last_stop_required
```json
null
```

## last_cycle_done
```json
null
```

## process tail
```text
30073 /usr/bin/google-chrome --no-sandbox --disable-dev-shm-usage --disable-gpu --window-size=1536,1100 --lang=zh-CN --user-data-dir=/home/cpsdata/projects/aideal-cps-data-lab/.secrets/jd_union_public_manual_profile --remote-debugging-address=127.0.0.1 --remote-debugging-port=19228 --disable-blink-features=AutomationControlled https://union.jd.com/index
30813 /opt/google/chrome/chrome --type=renderer --crashpad-handler-pid=30082 --enable-crash-reporter=, --user-data-dir=/home/cpsdata/projects/aideal-cps-data-lab/.secrets/jd_union_public_manual_profile --change-stack-guard-on-fork=enable --no-sandbox --disable-dev-shm-usage --remote-debugging-port=19228 --ozone-platform=x11 --disable-gpu-compositing --disable-blink-features=AutomationControlled --lang=en-US --num-raster-threads=1 --renderer-client-id=18 --time-ticks-at-unix-epoch=-1777809706075787 --launch-time-ticks=2689596256 --shared-files=v8_context_snapshot_data:100 --metrics-shmem-handle=4,i,9707303555383192621,944854569504904531,2097152 --field-trial-handle=3,i,10709816608756102670,17480246403413794853,262144 --variations-seed-version --pseudonymization-salt-handle=7,i,16255656096572889656,1981783894352167861,4 --trace-process-track-uuid=3190709003178624776
214026 /opt/google/chrome/chrome --type=renderer --crashpad-handler-pid=30082 --enable-crash-reporter=, --user-data-dir=/home/cpsdata/projects/aideal-cps-data-lab/.secrets/jd_union_public_manual_profile --change-stack-guard-on-fork=enable --no-sandbox --disable-dev-shm-usage --remote-debugging-port=19228 --ozone-platform=x11 --disable-gpu-compositing --disable-blink-features=AutomationControlled --lang=en-US --num-raster-threads=1 --renderer-client-id=184 --time-ticks-at-unix-epoch=-1777809706075787 --launch-time-ticks=2358252781658 --shared-files=v8_context_snapshot_data:100 --metrics-shmem-handle=4,i,10610223639501184078,14170108843624828814,2097152 --field-trial-handle=3,i,10709816608756102670,17480246403413794853,262144 --variations-seed-version --pseudonymization-salt-handle=7,i,16255656096572889656,1981783894352167861,4 --trace-process-track-uuid=3190709158727571710
276340 bash run/hz15_daytime_autostart_supervisor_40_67.sh
285153 bash -lc pgrep -af "hz15_daytime_autostart_supervisor_40_67|hz15_jump_pages_collector|chrome.*19228" | head -n 100
```

## supervisor tail
```text
SUPERVISOR_COLLECTOR_RUNNING ts=2026-06-12 21:07:45 seconds_until_stop=1380
SUPERVISOR_COLLECTOR_RUNNING ts=2026-06-12 21:12:45 seconds_until_stop=1080
SUPERVISOR_COLLECTOR_RUNNING ts=2026-06-12 21:17:45 seconds_until_stop=780
SUPERVISOR_COLLECTOR_RUNNING ts=2026-06-12 21:22:45 seconds_until_stop=480
SUPERVISOR_COLLECTOR_RUNNING ts=2026-06-12 21:27:45 seconds_until_stop=180
SUPERVISOR_OUTSIDE_DAYTIME_STOPPING_COLLECTOR ts=2026-06-12 21:32:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-12 21:42:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-12 21:52:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-12 22:02:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-12 22:12:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-12 22:22:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-12 22:32:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-12 22:42:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-12 22:52:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-12 23:02:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-12 23:12:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-12 23:22:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-12 23:32:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-12 23:42:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-12 23:52:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 00:02:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 00:12:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 00:22:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 00:32:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 00:42:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 00:52:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 01:02:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 01:12:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 01:22:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 01:32:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 01:42:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 01:52:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 02:02:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 02:12:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 02:22:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 02:32:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 02:42:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 02:52:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 03:02:45
SUPERVISOR_WAITING_DAYTIME ts=2026-06-13 03:12:45
```