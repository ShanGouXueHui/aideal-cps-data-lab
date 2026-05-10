# DL2 数据采集阶段 Memory

更新时间：2026-05-03  
仓库：`ShanGouXueHui/aideal-cps-data-lab`  
用途：供后续新对话恢复 AIdeal CPS / 智省优选京东联盟数据采集上下文。

## 1. 项目定位

AIdeal CPS / 智省优选是微信服务号 + 京东联盟 CPS 导购系统。Data Lab 仓库只用于采集、验证、归一化京东联盟商品数据与推广链路，不直接跑杭州生产服务。

生产边界：

- 杭州生产机 `8.136.28.6` 不跑浏览器自动化。
- 采集机只输出 JSONL / JSON 中间产物。
- 生产库导入必须经过 dry-run、去重、商业安全过滤、图片和链接校验。
- `.secrets/`、Cookie、账号页面、二维码、HAR、原始登录态不提交 GitHub。

## 2. 用户交互习惯

后续对话必须遵守：

1. 中文、专业、直接、结构化。
2. 不使用 Codex CLI；直接在 ChatGPT 对话里给可复制命令。
3. Linux 命令不要使用 `set -e`。
4. 命令分小步，避免巨型聚合脚本。
5. 每一步尽量包含：路径确认、git 状态、最小改动、静态检查、smoke/E2E、日志路径。
6. 输出不要刷屏，日志写入 `logs/` 或 `run/`，屏幕只 tail 关键 80-180 行。
7. 定位问题时一问一答，节约上下文。
8. 不用“话术”掩盖工程问题；价格和推广链路必须通过机制提高准确性。
9. 登录京东联盟时可以手工操作，但账号密码不要写入脚本、配置或 GitHub。
10. 出现风控/验证码/登录失效时，脚本停止并写 STOP 文件，等待用户协助，不自动反复登录。

## 3. 机器环境

### 3.1 杭州生产机

- IP：`8.136.28.6`
- 用户：`deploy`
- 用途：生产 FastAPI / 微信回调 / MySQL / H5。
- 约束：禁止浏览器自动化和京东账号采集。

### 3.2 新加坡旧采集机

- IP：`43.106.55.255`
- 用户：`cpsdev`
- Data Lab 路径：`/home/cpsdev/projects/aideal-cps-data-lab`
- 状态：已跑通 DL2C-DL2Z，但后来 SSH 卡死，已迁移主采集到杭州。
- 建议：新加坡采集暂停，不要与杭州同时用同一京东账号采集。

### 3.3 杭州新采集机

- IP：`121.41.111.36`
- 用户：`cpsdata`
- 项目路径：`/home/cpsdata/projects/aideal-cps-data-lab`
- OS：Ubuntu 22.04
- 规格：2 vCPU / 4 GiB / 50 GiB
- 快捷切换命令：`tocpsdata`
- Google Chrome：`/usr/bin/google-chrome`
- Chrome profile：`.secrets/jd_union_public_manual_profile`
- CDP：`127.0.0.1:19228`
- X display：`:79`
- noVNC：`18772`
- x11vnc：`59072`

系统问题与修复记录：

- `pip` 官方源太慢，改为清华源。
- `playwright install chromium` 在 npmmirror 对 Playwright 1.59 的 CFT 路径返回 404。
- Snap Chromium 不可用，报 `not a snap cgroup`。
- 最终采用 Google Chrome 官方 deb，`HZ5C_GOOGLE_CHROME_SMOKE_OK`。
- 缺 `Xvfb/x11vnc/fluxbox/websockify` 后执行 HZ4-FIX 修复，`HZ4_FIX_OK`。

## 4. 已完成关键阶段

### 4.1 公共页商品采集

入口：

- `https://union.jd.com/index`
- 点击“跳过登录，先逛逛”后进入：`https://union.jd.com/proManager/index?pageNo=1`

关键结论：

- 公共页不用登录即可看商品卡片。
- 商品详情页和“一键领链”需要登录。
- `view-source` 只能看到 Vue SPA 壳，商品数据不在 HTML 源码里，必须从运行时 DOM / JS state / 接口响应提取。

已跑通：

- DL2P：人工进入公共商品页后 DOM 抽取成功，50 个商品卡片。
- DL2R3：frame-aware 多页抽取成功，3 页共 137 个原始商品卡片。
- DL2S：修复归一化，合并旧 46 条与新 137 条，保留 176 条。
- DL2T：生成微信可用商品池，ready 129、poster_ready 69、top 60、reject 56。
- DL2U：商业安全过滤后，ready 80、poster_ready 22、feed 40、reject 49。

主要产物：

- `data/import/jd_union_public_products_latest.jsonl`
- `data/import/jd_union_public_wechat_ready_latest.jsonl`
- `data/import/jd_union_public_commercial_safe_latest.jsonl`
- `data/import/jd_union_public_commercial_safe_top_latest.jsonl`
- `data/import/jd_union_public_commercial_safe_poster_latest.jsonl`
- `data/import/jd_union_public_commercial_safe_wechat_feed_latest.jsonl`

### 4.2 推广链路读取

登录后路径：

- 登录入口：`https://union.jd.com/index`
- 我的联盟：`https://union.jd.com/overview`
- 商品推广页：`https://union.jd.com/proManager/index?pageNo=1`

人工验证：

- 用户已用个人账号登录成功。
- 商品推广页可见 `aidealfy`、`我的推广`、`商品推广`、大量商品卡片与 `一键领链`。
- 点击一键领链后弹窗显示短链接、长链接、二维码、京口令。

新加坡验证：

- DL2V2：当前弹窗短链读取成功，例如 `https://u.jd.com/fap00c6`。
- DL2X：可见页前 10 个按钮生成推广链成功，原始 10 条，SKU 去重 5 条。

杭州验证：

- HZ7 当前页检查成功：`product_hit=true`，`one_key_count=100`。
- HZ8B 第一个一键领链验证成功：
  - SKU：`10074067617066`
  - short_url：`https://u.jd.com/frEXTDm`
  - long_url：`union-click.jd.com/jdc...`
  - qr_url：`storage.jd.com/..._rq.png`
  - jd_command：已从弹窗 input/textarea 读取。

### 4.3 杭州守护采集

已部署：

- `run/hz9_union_guarded_daemon.py`
- `run/hz10_guard_watchdog.sh`

启动后状态：

- HZ9 daemon 已启动。
- HZ10 watchdog 已启动。
- 第一次运行日志显示：
  - `HZ9_GUARDED_DAEMON_START`
  - `ATTACHED`
  - `CANDIDATES fresh=120 total=120`
  - `ITEM_OK`
  - 短链：`https://u.jd.com/frJu6d5`
  - `fail_streak=0`

关键状态文件：

- `run/hz9_union_guarded_state.json`
- `run/hz9_union_guarded_report_latest.json`
- `run/hz9_STOP_REQUIRED.json`

最新链接文件：

- `data/import/hz_jd_union_guarded_promotion_links_latest.jsonl`

守护策略：

- 不自动登录。
- 不反复刷新撞风控。
- 每轮最多 12 个，单日最多 120 个。
- 商品之间随机等待 12-28 秒。
- 每轮间隔 900 秒。
- 连续失败 3 次或出现验证码/风控/登录失效，写 `run/hz9_STOP_REQUIRED.json` 并停止。
- HZ10 watchdog 只在无 STOP 文件且 Chrome/CDP 正常时低频重启 HZ9。

## 5. 当前状态

截至 2026-05-03：

1. 新加坡旧采集机可以暂停。
2. 杭州新采集机已部署 Data Lab、Google Chrome、noVNC、Xvfb、CDP。
3. 杭州机器已登录京东联盟，并进入商品推广页。
4. 杭州一键领链读取已验证通过。
5. HZ9/HZ10 守护采集已部署并产生第一条成功短链。
6. 当前进入 24 小时观察期。

## 6. 后续待完成任务

### 6.1 日常观察

每天用状态命令检查：

- HZ9/HZ10 进程是否存在。
- `run/hz9_STOP_REQUIRED.json` 是否出现。
- `run/hz9_union_guarded_state.json` 中 `day_ok_count` 是否增长。
- `data/import/hz_jd_union_guarded_promotion_links_latest.jsonl` 行数是否增长。
- `fail_streak` 是否保持 0 或低值。

### 6.2 收敛采集逻辑

当前 HZ9 已能领链，但仍需要后续固化为正式脚本并提交：

- 把临时 `run/hz9_union_guarded_daemon.py` 整理到 `scripts/collect_jd_union_visible_links.py`。
- 把 `run/hz10_guard_watchdog.sh` 整理到 `scripts/run_jd_union_guard_watchdog.sh`。
- 把配置项抽到 `config/collector.example.yaml` 或新的 `config/jd_union_visible_collector.example.yaml`。
- 增加 dry-run 模式、只读状态检查模式、停止命令说明。

### 6.3 产物合并

需要把推广链接与微信 feed 合并，形成生产可消费文件：

- 输入：`data/import/jd_union_public_commercial_safe_wechat_feed_latest.jsonl`
- 链接：`data/import/hz_jd_union_guarded_promotion_links_latest.jsonl`
- 输出建议：`data/import/jd_union_commercial_safe_wechat_feed_with_links_latest.jsonl`

合并规则：

- 按 SKU / item URL 对齐。
- `jd_url` 优先替换为 `short_url`。
- 原普通商品链接保留为 `jd_url_original`。
- 保留 `long_url`、`qr_url`、`jd_command`。
- 标记 `needs_union_link=false`、`promotion_mode=jd_union_logged_in_onekey`。

### 6.4 生产导入

不可直接写生产库。需要先做：

1. JSONL 格式校验。
2. SKU 去重。
3. 图片 URL 可访问性校验。
4. 商业安全过滤复核。
5. dry-run importer。
6. 小批量导入杭州生产 MySQL。
7. 微信“今日推荐”链路 smoke。

## 7. 重要风险与边界

必须继续遵守：

- 不把 `.secrets/`、cookies、二维码、账号页面、HAR、登录截图提交 GitHub。
- 不在杭州生产机跑浏览器采集。
- 不自动反复登录。
- 不触发验证码后继续重试。
- 不高频点击一键领链。
- 不推成人、医疗、强功效、杀虫、除甲醛、除螨等风险商品。
- 不把“预计收益”展示给终端用户；终端用户只展示节省、到手价、热销、推荐理由。

## 8. 资源与配置判断

杭州新采集机规格 2C4G 当前足够。

升级判断：

- 若 Chrome/CDP 经常断开。
- 若 `dmesg` 出现 OOM/killed process。
- 若 `available memory` 长期低于 300MB。
- 若 HZ9/HZ10 频繁重启或日志变 0 字节。

短期不需要再开新机器，不需要升 4C8G。

## 9. 关联设计文档

后续新对话必须先读：

- `docs/DL2_JD_UNION_COLLECTION_DESIGN.md`
- `memory/DL2_DATA_COLLECTION_MEMORY.md`
- `docs/DL2_DATA_COLLECTION_HANDOFF_PROMPT.md`

这三个文件合起来构成 DL2 数据采集阶段的设计、状态与新对话启动上下文。
---

## HZ11 多浏览器双菜单采集状态更新

MARKER: DL2_HZ11_MULTI_BROWSER_MENU_UPDATE_20260510

### 时间

2026-05-10

### 当前机器

- 采集机：杭州 121.41.111.36
- 用户：cpsdata
- 项目路径：/home/cpsdata/projects/aideal-cps-data-lab
- Chrome A：
  - 用途：商品推广 / 全部商品
  - CDP：127.0.0.1:19228
  - profile：.secrets/jd_union_public_manual_profile
  - noVNC：18772
- Chrome B：
  - 用途：实时榜单 / 高佣榜
  - CDP：127.0.0.1:19229
  - profile：.secrets/jd_union_commission_manual_profile
  - noVNC：18773

### 设计决策

1. 不再用一个浏览器来回切榜单。
2. 一个 worker 固定绑定一个 Chrome profile、一个 CDP 端口、一个菜单。
3. 一期只开两个浏览器，避免并发过高导致风控。
4. product_all 采集“商品推广 / 全部商品”。
5. high_commission 采集“实时榜单 / 高佣榜”。
6. 不再采集“今日热销榜”，避免与全部商品池高度重复。
7. 推广短链有效期按 60 天建模：
   - link_expire_days = 60
   - refresh_after_days = 40
   - refresh_before_expiry_days = 20
8. 目标总量：一期 100000 条去重 SKU。
9. 达到 100000 后进入刷新轮，从头刷新链接，避免短链过期。
10. 出现验证码、安全验证、登录失效、风控提示，必须写 STOP 文件并停止，不允许自动反复登录。

### 已提交脚本和配置

- run/hz11_rank_worker.py
- run/hz11_merge_multi_menu_latest.py
- run/hz11_high_commission_probe.py
- config/hz11_product_all.env
- config/hz11_high_commission.env
- docs/ops/DL2_HZ11_SMOKE_REPORT.md
- reports/hz11_smoke_summary_latest.json
- reports/hz11_high_commission_dom_probe_latest.json

### Smoke 结果

#### product_all

结论：链路可用。

发现问题：

- 第一次 smoke 成功点击一键领链。
- 但同一页内出现重复 SKU 领链。
- 已补丁：
  - fresh candidates 去重。
  - collect loop 内二次检查 skip_sku。
  - 避免同一轮重复点击同一 SKU。

后续需要：

- 清理或重置 product_all state 后再跑 smoke。
- 确认 patch 后 dedup_sku 接近 ok_rows。
- 再启动长期守护。

#### high_commission

结论：页面可用，但旧 HZ9 parser 不适配。

DOM probe 发现：

- 有商品卡片文本。
- 有商品链接。
- hover 后有按钮。
- 一键领链按钮存在，但位于 expanded hover content。
- HZ9 的 get_candidates 在 realTimeRankings 页面返回 0。

后续需要：

1. 为高佣榜写专用 DOM card parser。
2. 通过商品卡片文本提取 title、price、commission_rate、estimated_income、image_url、rank_index。
3. 优先从链接或 DOM 属性提取 SKU。
4. 如果卡片阶段提取不到 SKU，则点击一键领链后，从 modal 的 long_url、jd_url 或 union-click 参数中反推 SKU。
5. 高佣榜点击逻辑应为：定位卡片，hover 卡片，找该卡片内的一键领链，点击，读取 modal，写 JSONL。

### 当前数据状态

- HZ9 旧数据：60 条，字段完整：
  - short_url
  - long_url
  - qr_url
  - jd_command
- product_all smoke：已验证能生成短链，但需要重置 state 后再做干净统计。
- high_commission：0 条，需要专用 parser。
- 合并目标文件：
  - data/import/hz_jd_union_multi_menu_promotion_links_latest.jsonl

### Git 状态

- remote 已从 HTTPS 切换到 SSH：
  - git@github.com:ShanGouXueHui/aideal-cps-data-lab.git
- cpsdata 用户已配置 GitHub SSH key。
- 已完成 rebase 并 push。
- 关键提交：
  - ae37fb7：HZ11 multi-menu collector diagnostics

### 下一步

1. 修高佣榜专用 DOM parser 和 hover click。
2. 重置 product_all smoke state，验证去重补丁。
3. 两个 worker 分别跑 15 到 30 分钟。
4. 生成吞吐率报告：
   - 每小时新增 SKU
   - 每日估算新增 SKU
   - 100000 条预计完成天数
   - 是否满足 40 天刷新周期
5. 稳定后再启动 HZ12 watchdog，24 小时不停跑。
