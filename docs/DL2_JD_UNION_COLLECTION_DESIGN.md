# DL2 京东联盟商品池与推广链路采集设计

更新时间：2026-05-02  
适用仓库：`ShanGouXueHui/aideal-cps-data-lab`  
定位：开发数据实验仓库，不是杭州生产环境。

## 1. 目标

本设计用于在京东联盟开放 API 配额或能力不足时，基于已授权的京东联盟站长后台页面，采集可用于 AIdeal CPS / 智省优选导购系统的商品候选池、商品图片、价格、佣金比例、预计收益、商品链接与推广短链。

核心目标：

1. 构建可持续扩充的商品候选池。
2. 生成适合微信公众号 / 服务号推荐流使用的安全商品数据。
3. 在登录态存在时，为可推广商品补齐京东联盟推广短链、长链、京口令等字段。
4. 所有自动化行为低频、可暂停、可追踪，避免反复登录和风控风险。
5. 原始浏览器会话、Cookie、HAR、截图、账号页面与密钥不得进入 GitHub。

## 2. 总体架构

链路分为五层：

```text
JD Union 页面
  -> 公共商品页采集
  -> DOM / frame-aware 抽取
  -> 归一化与商业安全过滤
  -> 微信推荐池 / 海报池生成
  -> 登录态一键领链补齐推广链接
  -> guarded daemon + watchdog 低频持续运行
```

### 2.1 公共商品页采集

入口：

- 首页：`https://union.jd.com/index`
- 跳过登录后：`https://union.jd.com/proManager/index?pageNo=1`

关键结论：

- 公共页不登录即可浏览商品卡片。
- 点击商品详情会要求登录，公共采集阶段不进入商品详情。
- 首页 HTML 是 SPA 壳，`view-source` 只能看到 `#app` 和静态脚本，商品数据需要浏览器渲染后从 DOM / 网络响应中获取。
- 单纯读取 `body.innerText` 不稳定，后续采用 frame-aware DOM 抽取更可靠。

### 2.2 Playwright / Chrome 会话

当前使用远程调试端口连接已登录或已打开的 Chromium：

- CDP 端口：`127.0.0.1:19228`
- 浏览器 profile：`.secrets/jd_union_public_manual_profile`
- 原则：保留登录态，脚本只接管页面，不反复登录。

重要约束：

- 不提交 `.secrets/`。
- 不提交 Cookie、localStorage、sessionStorage、登录截图、二维码、HAR、原始账号页面。
- 自动化失败时停止并记录 `STOP_REQUIRED`，由人工判断是否继续。
- 不做高频点击，不做并发登录，不做重复刷新式暴力采集。

## 3. 已验证阶段与产物

### 3.1 DL2P：公共页手动进入后 DOM 抽取

关键结论：人工点击“跳过登录，先逛逛”后，DOM 抽取成功。

产物示例：

- `run/dl2p_public_manual_dom_extract_*/public_manual_dom_product_cards.jsonl`
- `data/import/jd_union_public_manual_products_dl2p_public_manual_dom_extract_*.jsonl`

结果摘要：

- 抽取卡片：50 条。
- 可得到字段：标题、到手价、预计收益、佣金比例、店铺、图片 URL、来源 URL。
- 部分图片为 base64 占位或懒加载，需要后续二次清洗。

### 3.2 DL2R3：frame-aware 多页抽取

原因：直接 DOM eval 时 `card_count=0`，后确认页面元素在 frame / 动态区域中，需要 frame-aware 逻辑。

结果摘要：

- 第 1 页：39 卡片。
- 第 2 页：49 卡片。
- 第 3 页：49 卡片。
- 原始采集：137 条。

产物：

- `run/dl2r3_frame_aware_public_extract_*/public_frame_raw_products.jsonl`
- `run/dl2r3_frame_aware_public_extract_*/public_frame_extract_report.json`

经验：

- “下一页”按钮可点击，但 URL 可能不变化，不能依赖 URL 判断页码。
- 应以卡片内容、图片、SKU 链接、文本指纹判断翻页结果。
- 同一商品可能因为卡片中同时出现“我要推广”和“一键领链”等按钮而被重复抽取，需要按 SKU / item URL 去重。

### 3.3 DL2S：修复归一化与候选池合并

输入：

- DL2R3 原始商品。
- DL2Q 早期公共页归一化商品。

结果摘要：

- 原始新增：137。
- 历史归一化：46。
- 合并：183。
- 保留：176。
- pass：44。
- warn：132。
- reject：7。

分类分布：

- 食品饮料：42。
- 数码家电：34。
- 纸品清洁：24。
- 其他：35。
- 家居日用：14。
- 个护健康：7。
- 母婴：9。
- 宠物：11。

产物：

- `data/import/jd_union_public_products_latest.jsonl`
- `data/import/jd_union_public_products_repaired_*.jsonl`
- `data/import/jd_union_public_products_top_*.jsonl`
- `run/dl2s_public_products_repair_report_*.json`

### 3.4 DL2T：微信可用池 / 海报可用池

目标：把商品池转换为微信推荐可用数据。

结果摘要：

- 输入：313。
- ready：129。
- poster_ready：69。
- top：60。
- reject：56。

主要过滤原因：

- 无 item URL，无法承接点击。
- 医疗、成人计生、杀虫、功效风险词等商业安全过滤。

产物：

- `data/import/jd_union_public_wechat_ready_latest.jsonl`
- `data/import/jd_union_public_poster_ready_latest.jsonl`
- `data/import/jd_union_public_wechat_top_*.jsonl`
- `run/dl2t_wechat_ready_product_pool_report_*.json`

### 3.5 DL2U：商用安全微信推荐池

目标：进一步过滤公众号正式推荐不适合推送的商品。

结果摘要：

- 输入：129。
- ready：80。
- poster_ready：22。
- top：60。
- feed：40。
- reject：49。

过滤逻辑：

1. 去除医疗、医用、除甲醛、除螨、美白、抗敏、祛痘、花露水等容易触发合规或夸大宣传风险的商品。
2. 按类目设置价格上限，避免低信任场景推高价商品。
3. 弱化或剔除“其他”类目中用户决策不明确的商品。
4. 去除重复图片，提升公众号图文体验。

产物：

- `data/import/jd_union_public_commercial_safe_latest.jsonl`
- `data/import/jd_union_public_commercial_safe_top_latest.jsonl`
- `data/import/jd_union_public_commercial_safe_poster_latest.jsonl`
- `data/import/jd_union_public_commercial_safe_wechat_feed_latest.jsonl`

微信 feed 字段包括：

- `title`
- `wechat_title`
- `wechat_subtitle`
- `recommend_reason`
- `image_url`
- `item_url`
- `jd_url`
- `price`
- `commission_rate`
- `estimated_income`
- `category`
- `recommend_score`
- `needs_union_link`

### 3.6 DL2V / DL2X：登录态一键领链

登录后页面路径：

- 登录入口：`https://union.jd.com/index`
- 我的联盟：`https://union.jd.com/overview`
- 商品推广：`https://union.jd.com/proManager/index?pageNo=1`

人工验证结论：

- 用户使用个人账号登录成功。
- 进入“我要推广 -> 商品推广”。
- 点击商品卡片的“一键领链”可以打开弹窗。
- 弹窗包含短链接、长链接、二维码、京口令。

DL2V2 已验证当前弹窗可读字段：

- `short_url`
- `long_url`
- `jd_command`
- `all_urls`
- `all_input_values`

DL2W 初版按 SKU 搜索失败较多，原因：搜索跳转慢，页面没有稳定出现一键领链按钮。

DL2X 改为“可见页面按钮顺序遍历”后成功：

- `one_key_count=100`
- 目标 10 条，全部成功。
- 原始成功 10 条，按 SKU 去重 5 条。

产物：

- `data/import/jd_union_visible_promotion_links_latest.jsonl`
- `data/import/jd_union_visible_promotion_links_dedup_latest.jsonl`
- `run/dl2x_visible_onekey_link_extract_report_*.json`

经验：

- 当前阶段“可见页面顺序采集”比“按 SKU 搜索采集”稳定。
- 链接弹窗中的短链接有效期通常显示为 60 天，应记录生成时间并后续做过期更新机制。
- 一键领链默认推广位 id 目前为 0；后续如有正式推广位，应切换为生产推广位并在配置中显式记录。

## 4. 低频守护采集设计

### 4.1 DL2Y guarded daemon

目标：在已登录 Chrome 会话存在时，低频、可控、可停止地持续采集推广链接。

启动状态：

- `run/dl2y_union_guarded_daemon.py`
- lock：`run/dl2y_union_guarded_daemon.lock`
- state：`run/dl2y_union_guarded_state.json`
- report latest：`run/dl2y_union_guarded_report_latest.json`
- stop required：`run/dl2y_STOP_REQUIRED.json`

默认策略：

- `cycle_sleep=900s`
- `daily_cap=120`
- `max_items_per_cycle=12`
- `item_sleep_min=12s`
- `item_sleep_max=28s`

关键原则：

1. 不自动重新登录。
2. 不自动扫码。
3. 检测到登录失效、页面异常、无按钮、空白页、连续失败等情况时，写入 `STOP_REQUIRED` 并停止。
4. 保持低频，模拟人工节奏，不做高并发。
5. 所有进度写入 JSONL / JSON 报告，便于日后恢复。

### 4.2 DL2Z watchdog

目标：监控 DL2Y 是否存活、日志是否新鲜，但不做激进重启。

关键状态：

- watchdog 脚本：`run/dl2z_guard_watchdog.sh`
- watchdog 日志：`logs/dl2z_guard_watchdog_*.log`
- 检查间隔：`CHECK_INTERVAL=300s`
- stale 阈值：`STALE_SECONDS=3600s`

策略：

- 如果 DL2Y 正常运行且日志新鲜，记录 `DL2Y_RUNNING`。
- 如果 DL2Y 停止但没有 `STOP_REQUIRED`，可低频恢复。
- 如果存在 `STOP_REQUIRED`，不得自动重启，等待人工确认。
- 不关闭 Chrome 登录态，除非明确人工要求。

## 5. 自校验机制

### 5.1 页面状态校验

每次采集前检查：

- CDP 端口是否可连接。
- 当前页面是否为京东联盟域名。
- 页面 `readyState` 是否可用。
- 是否能看到“我的推广 / 商品推广 / 一键领链”。
- 是否出现登录页、扫码页、验证码、空白页或风控提示。

异常处理：

- 登录页 / 扫码页：停止，写入 `STOP_REQUIRED`。
- 空白页：等待有限次数；仍失败则停止。
- 一键领链按钮为 0：停止或切换公共采集，不反复刷新。

### 5.2 商品质量校验

字段校验：

- 标题非空且不像“1.0万+好评”这类评论数误识别。
- 价格为正数。
- 佣金比例可解析。
- 图片 URL 可用且不是明显占位图。
- item URL 可用。
- SKU 可从 item URL 中提取。

去重：

- 优先按 SKU 去重。
- SKU 缺失时按 item URL 去重。
- 再按标题 + 价格 + 店铺做弱去重。

### 5.3 商业安全校验

默认过滤：

- 成人计生、医疗、药品强功效、杀虫、驱虫、除甲醛、除螨、美白、祛痘、抗敏、治疗暗示等。
- 高价且不适合公众号低信任推荐的商品。
- 类目不明确或“其他”类目中过弱的商品。

注意：过滤策略是商业推荐安全，不代表商品本身不可售。

### 5.4 推广链校验

推广链成功条件：

- `short_url` 存在且域名为 `u.jd.com`。
- `long_url` 存在且域名为 `union-click.jd.com` 或京东联盟可识别跳转域。
- `sku` 能与 item URL 对齐。
- 同一 SKU 多条短链时保留最新或首条，生成 dedup 文件。

## 6. 运行观察命令

日常检查：

```bash
cd ~/projects/aideal-cps-data-lab || exit 1

pgrep -af "dl2z_guard_watchdog|dl2y_union_guarded_daemon|chrome.*19228" || echo "NO_RELATED_PROCESS"

if [ -f run/dl2y_STOP_REQUIRED.json ]; then
  cat run/dl2y_STOP_REQUIRED.json | python3 -m json.tool
else
  echo "NO_STOP_REQUIRED"
fi

if [ -f run/dl2y_union_guarded_state.json ]; then
  cat run/dl2y_union_guarded_state.json | python3 -m json.tool
fi

if [ -f run/dl2y_union_guarded_report_latest.json ]; then
  cat run/dl2y_union_guarded_report_latest.json | python3 -m json.tool | head -n 160
fi

ls -lh data/import/*promotion*link*latest* data/import/*guarded*latest* 2>/dev/null || true
```

暂停采集但保留 Chrome 登录态：

```bash
cd ~/projects/aideal-cps-data-lab || exit 1

pkill -f "run/dl2z_guard_watchdog.sh" 2>/dev/null || true
pkill -f "python.*run/dl2y_union_guarded_daemon.py" 2>/dev/null || true

echo "PAUSED_DL2Y_DL2Z_KEEP_CHROME"
pgrep -af "dl2z_guard_watchdog|dl2y_union_guarded_daemon|chrome.*19228" || true
```

## 7. 生产导入边界

这个仓库只做数据实验与中间产物生成。生产 `aideal-cps` 只应消费经过验证的导出文件。

建议生产导入候选：

1. `data/import/jd_union_public_commercial_safe_wechat_feed_latest.jsonl`
2. 补链后：`data/import/jd_union_commercial_safe_wechat_feed_with_links_latest.jsonl` 或后续 guarded daemon 生成的等价 latest 文件。
3. 海报候选：`data/import/jd_union_public_commercial_safe_poster_latest.jsonl`

生产导入前必须做 dry-run：

- JSONL 格式校验。
- 必填字段校验。
- SKU / 链接去重。
- 图片可访问性校验。
- 商业安全过滤再检查。
- 不直接写生产 DB。

## 8. 当前结论

截至 2026-05-02：

1. 公共页商品池采集已跑通。
2. 多页 frame-aware 采集已跑通。
3. 商品归一化、商业安全过滤、微信 feed、海报池已跑通。
4. 登录态一键领链已人工验证并脚本化跑通。
5. DL2Y guarded daemon 与 DL2Z watchdog 已部署，进入 24 小时观察期。
6. 暂不建议立刻升级服务器；先观察一天的稳定性、采集量和资源压力，再决定是否从 2C2G 升级到 2C4G 或更高。

## 9. 不做事项

- 不在 GitHub 提交账号、密码、Cookie、二维码、登录截图、HAR、raw account HTML。
- 不在杭州生产机器运行浏览器自动化。
- 不在登录失效后自动反复登录。
- 不高频点击一键领链。
- 不绕过平台风控或验证码。
- 不把未经过滤的医疗、成人、强功效、风险商品直接用于公众号推荐。
