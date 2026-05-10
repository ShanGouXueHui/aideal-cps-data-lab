---

## HZ12 正式采集口径：商品推广 / 全部商品

MARKER: DL2_HZ12_PRODUCT_ALL_OFFICIAL_20260511

### 决策

高佣榜不再作为正式主采集源。原因：

- 高佣榜页面总页数较少，约 2 到 5 页，不能支撑完整商品池。
- 高佣榜分页在自动化环境中存在视口和按钮定位不稳定问题。
- 高佣榜更适合作为后续补充榜单，而不是基础商品池。

正式主采集源改为：

- 菜单：商品推广 / 全部商品
- 页面显示总量：约 4000 条
- 目标：读取页面实际显示的全部商品，不再设置 100000 条目标。

### HZ12 任务目标

1. 后台任务读取完整“商品推广 / 全部商品”数据。
2. 每个商品补充京东联盟一键领链数据：
   - short_url
   - long_url
   - qr_url
   - jd_command
3. 每条记录必须保留：
   - sku
   - title
   - image_url
   - item_url
   - price
   - commission_rate
   - estimated_income
   - link_created_at
   - link_expire_at
   - refresh_due_at
4. 短链有效期按 60 天处理。
5. 刷新策略：
   - refresh_after_days = 40
   - 即提前 20 天刷新。
6. 全量刷新完成后，如果没有到下一轮刷新周期，任务自动休眠。
7. 到刷新周期后，从第一页重新刷新已有库中数据。

### 安全和风控规则

- 不提交 .secrets。
- 不提交账号、密码、Cookie、token、HAR、二维码。
- 遇到验证码、登录失效、安全验证、风控提示，立即写 STOP 文件并停止。
- 不自动反复登录。
- 不直接写生产库。
- Data Lab 仅生成 JSONL 和报告，生产导入单独 dry-run。

### HZ12 文件

- config/hz12_product_all_full.env
- run/hz12_product_all_full_collector.py
- data/import/hz_jd_union_product_all_full_links_latest.jsonl
- run/hz12_product_all_full_state.json
- run/hz12_product_all_full_report_latest.json
- run/hz12_product_all_STOP_REQUIRED.json

### 当前执行计划

- 2026-05-11 夜间启动 HZ12 后台采集。
- 跑一晚，目标接近或完成全部约 4000 条。
- 第二天检查：
  - 总行数
  - 去重 SKU
  - 非数字 SKU
  - short_url 完整率
  - title/image/price/commission 完整率
  - STOP 文件
  - 抽样短链有效性
- 检查通过后再固化为长期守护任务。
