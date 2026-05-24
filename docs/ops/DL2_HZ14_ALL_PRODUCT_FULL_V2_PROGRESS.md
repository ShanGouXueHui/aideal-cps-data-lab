# HZ14 V2 Official All-Product Full Progress

- Generated at: 2026-05-25 02:39:46
- process_alive: False
- stop_exists: True
- counts: {'rows': 14, 'ok': 14, 'dedup_sku': 14, 'non_numeric': 0, 'duplicate_ok_rows': 0, 'page_count': 2, 'first_page': 1, 'last_page': 14, 'target_total': 4000, 'progress_pct': 0.35}
- missing: {'title': 0, 'image_url': 0, 'item_url': 0, 'price': 0, 'commission_rate': 0, 'estimated_income': 0, 'short_url': 0, 'long_url': 0, 'qr_url': 0, 'jd_command': 0, 'refresh_due_at': 0}
- pagination: {'page_next_events_tail': 4, 'page_next_changed_tail': 4, 'last_page_next': {'event': 'PAGE_NEXT', 'page_no': 5, 'result': {'active_page_no': '6', 'after_skus': ['100011482251', '100048898827', '10182702260121', '100012498665', '6572088', '990362', '100054616046', '100069276014'], 'after_url': 'https://union.jd.com/proManager/index?pageNo=6', 'before_skus': ['100034991103', '10193693046672', '100066484116', '100127030318', '14670577', '100188633188', '100063959209', '100197810859'], 'before_url': 'https://union.jd.com/proManager/index?pageNo=5', 'changed': True, 'from_page_no': 5, 'ok': True}, 'ts': '2026-05-23 15:47:48', 'worker': 'hz14_all_product_full'}}
- failures: {'item_fail_events_tail': 3, 'stop_events_tail': 1, 'last_fail': {'err': "RuntimeError('short_url_not_found')", 'event': 'ITEM_FAIL', 'fail_streak': 3, 'page_no': 6, 'sku': '6572088', 'ts': '2026-05-23 15:52:18', 'worker': 'hz14_all_product_full'}}
- throughput: {'first_ts': '2026-05-23T23:56:05', 'last_ts': '2026-05-24T08:00:40', 'runtime_hours_est': 8.076, 'estimated_ok_per_hour': 1.73, 'eta_hours_to_4000': 2299.46}
