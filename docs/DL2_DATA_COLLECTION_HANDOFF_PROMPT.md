# DL2 数据采集新对话 Handoff Prompt

把下面内容复制到新 ChatGPT 对话中使用。新对话应先读取 GitHub 文档，再继续杭州采集机后续工作。

---

你现在继续 **AIdeal CPS / 智省优选 - 京东联盟 DL2 数据采集** 项目。请完整阅读本 Prompt，并优先读取 GitHub 文档，不要从头重新设计。

## 一、交互规则

1. 使用中文，职业化、直接、结构化。
2. 不使用 Codex CLI；直接在 ChatGPT 对话中给 copy-paste 可执行命令。
3. Linux 命令不要使用 `set -e`。
4. 命令分小步，不要把太多改动塞到一个巨大脚本。
5. 每一步尽量包含：路径确认、git 状态、最小改动、静态检查、smoke/E2E、日志路径。
6. 输出不要刷屏，日志写入 `logs/` 或 `run/`，屏幕只 tail 关键 80-180 行。
7. 定位问题时一问一答，节约上下文长度。
8. 不用“话术”掩盖工程问题；价格、佣金、推广链路必须通过代码/数据机制提高准确性。
9. 用户可手工登录京东联盟，但账号密码不要写进脚本、配置、日志或 GitHub。
10. 出现验证码、登录失效、风控、安全验证时，停止采集并写 STOP 文件，等待用户协助，不要自动反复登录。

## 二、必须先读的 GitHub 文档

Data Lab 仓库：

```text
https://github.com/ShanGouXueHui/aideal-cps-data-lab
```

新对话开始后先读取：

```text
docs/DL2_JD_UNION_COLLECTION_DESIGN.md
memory/DL2_DATA_COLLECTION_MEMORY.md
docs/DL2_DATA_COLLECTION_HANDOFF_PROMPT.md
README.md
```

这些文件记录了完整设计、运行边界、当前状态和后续待办。

## 三、项目背景

项目：AIdeal CPS / 智省优选  
目标：微信服务号 + 京东联盟 CPS 导购系统。  
当前 DL2 阶段目标：建设京东联盟商品候选池和推广链接数据源。

Data Lab 只做数据实验和导出：

- 商品卡片采集。
- 商品归一化。
- 商业安全过滤。
- 微信推荐 feed 生成。
- 登录态一键领链补充推广短链。
- 守护线程低频 7x24 采集。

生产导入必须另行 dry-run，不直接写生产库。

## 四、机器环境

### 1. 杭州生产机

```text
IP: 8.136.28.6
用户: deploy
用途: 生产 FastAPI / 微信回调 / MySQL / H5
限制: 禁止跑浏览器自动化，禁止登录京东账号
```

### 2. 新加坡旧采集机

```text
IP: 43.106.55.255
用户: cpsdev
Data Lab: /home/cpsdev/projects/aideal-cps-data-lab
状态: 已验证 DL2C-DL2Z，但 SSH 卡死过；主采集已迁移杭州
建议: 暂停，不要与杭州同时用同一账号采集
```

### 3. 杭州新采集机

```text
IP: 121.41.111.36
用户: cpsdata
项目路径: /home/cpsdata/projects/aideal-cps-data-lab
OS: Ubuntu 22.04
配置: 2C4G / 50G
Chrome: /usr/bin/google-chrome
Chrome profile: .secrets/jd_union_public_manual_profile
CDP: 127.0.0.1:19228
X display: :79
noVNC: 18772
x11vnc: 59072
```

admin/root 下已创建快捷命令：

```bash
tocpsdata
```

用于切换到 `cpsdata`。

## 五、杭州采集机已完成状态

### 1. 系统环境

- `cpsdata` 用户已创建，具备 sudo 权限。
- Data Lab 已 clone 到：`/home/cpsdata/projects/aideal-cps-data-lab`。
- Python venv 已创建：`.venv-browser`。
- pip 已切清华源。
- Playwright Python 包已安装。
- Playwright 自带 Chromium 下载失败，已改用 Google Chrome deb。
- Google Chrome 已安装：`/usr/bin/google-chrome`。
- `Xvfb / x11vnc / fluxbox / novnc / websockify` 已安装。
- HZ5C smoke 成功。
- HZ6 noVNC + Chrome + CDP 成功。

### 2. 京东联盟登录与页面

- 用户已在 noVNC 中手工登录京东联盟。
- 当前能进入：`https://union.jd.com/proManager/index?pageNo=1`
- HZ7 当前页检查成功：
  - `product_hit=true`
  - `login_hit=true`
  - `one_key_count=100`

### 3. 一键领链验证

HZ8B 已验证成功：

- 点击第一个“一键领链”按钮成功。
- 读取到短链、长链、二维码、京口令。
- 示例短链：`https://u.jd.com/frEXTDm`
- 示例 SKU：`10074067617066`

### 4. 守护采集

HZ9/HZ10 已部署并启动：

```text
run/hz9_union_guarded_daemon.py
run/hz10_guard_watchdog.sh
```

日志显示：

```text
HZ9_GUARDED_DAEMON_START
ATTACHED
CANDIDATES fresh=120 total=120
ITEM_OK
short_url=https://u.jd.com/frJu6d5
```

状态文件：

```text
run/hz9_union_guarded_state.json
run/hz9_union_guarded_report_latest.json
run/hz9_STOP_REQUIRED.json
```

最新采集文件：

```text
data/import/hz_jd_union_guarded_promotion_links_latest.jsonl
```

## 六、已完成的数据产物

公共商品池和安全 feed：

```text
data/import/jd_union_public_products_latest.jsonl
data/import/jd_union_public_wechat_ready_latest.jsonl
data/import/jd_union_public_commercial_safe_latest.jsonl
data/import/jd_union_public_commercial_safe_top_latest.jsonl
data/import/jd_union_public_commercial_safe_poster_latest.jsonl
data/import/jd_union_public_commercial_safe_wechat_feed_latest.jsonl
```

旧新加坡推广链接验证产物：

```text
data/import/jd_union_visible_promotion_links_latest.jsonl
data/import/jd_union_visible_promotion_links_dedup_latest.jsonl
```

杭州 guarded daemon 产物：

```text
data/import/hz_jd_union_guarded_promotion_links_latest.jsonl
```

## 七、当前后续任务

### 任务 1：观察杭州 HZ9/HZ10 运行状态

每天检查：

- HZ9/HZ10 是否运行。
- `run/hz9_STOP_REQUIRED.json` 是否出现。
- `run/hz9_union_guarded_state.json` 中 `day_ok_count` 是否增长。
- `data/import/hz_jd_union_guarded_promotion_links_latest.jsonl` 行数是否增长。
- `fail_streak` 是否为 0 或低值。

状态检查命令：

```bash
cd ~/projects/aideal-cps-data-lab || exit 1

pgrep -af "hz9_union_guarded_daemon|hz10_guard_watchdog|chrome.*19228" || echo "NO_RELATED_PROCESS"

if [ -f run/hz9_STOP_REQUIRED.json ]; then
  cat run/hz9_STOP_REQUIRED.json | python3 -m json.tool
else
  echo "NO_STOP_REQUIRED"
fi

if [ -f run/hz9_union_guarded_state.json ]; then
  cat run/hz9_union_guarded_state.json | python3 -m json.tool
else
  echo "NO_STATE"
fi

if [ -f run/hz9_union_guarded_report_latest.json ]; then
  cat run/hz9_union_guarded_report_latest.json | python3 -m json.tool | head -n 160
else
  echo "NO_REPORT"
fi

python3 - <<'PY'
import json
from pathlib import Path
p = Path('data/import/hz_jd_union_guarded_promotion_links_latest.jsonl')
if not p.exists():
    print('NO_LINKS')
else:
    rows=[]
    for line in p.read_text(encoding='utf-8', errors='ignore').splitlines():
        if line.strip():
            try: rows.append(json.loads(line))
            except Exception: pass
    ok=[x for x in rows if x.get('status')=='ok' and x.get('short_url')]
    skus=[]
    for x in ok:
        if x.get('sku') and x.get('sku') not in skus:
            skus.append(x.get('sku'))
    print('rows=', len(rows), 'ok=', len(ok), 'dedup_sku=', len(skus))
    for i,x in enumerate(ok[-20:], max(1, len(ok)-19)):
        print(i, x.get('sku'), x.get('short_url'), (x.get('title') or '')[:70])
PY
```

### 任务 2：合并推广链与微信 feed

把：

```text
data/import/jd_union_public_commercial_safe_wechat_feed_latest.jsonl
```

和：

```text
data/import/hz_jd_union_guarded_promotion_links_latest.jsonl
```

按 SKU / item URL 合并，生成：

```text
data/import/jd_union_commercial_safe_wechat_feed_with_links_latest.jsonl
```

合并规则：

- `jd_url` 替换成 `short_url`。
- 原始 `item_url` 保留。
- 原普通商品链接保留为 `jd_url_original`。
- 写入 `long_url`、`qr_url`、`jd_command`。
- `needs_union_link=false`。
- `promotion_mode=hz_jd_union_logged_in_onekey`。

### 任务 3：固化脚本

当前 HZ9/HZ10 仍在 `run/` 临时脚本，应后续固化：

```text
scripts/collect_jd_union_visible_links.py
scripts/run_jd_union_guard_watchdog.sh
config/jd_union_visible_collector.example.yaml
```

固化前不提交 `.secrets/`、日志、账号文件、二维码、HAR。

### 任务 4：准备生产导入

生产导入仍未完成。需要：

1. 生成 with_links feed。
2. JSONL schema 校验。
3. 商业安全过滤复核。
4. 图片 URL 可访问性抽查。
5. 短链有效性抽查。
6. dry-run importer。
7. 小批量导入杭州生产 MySQL。
8. 微信“今日推荐” smoke。

## 八、故障处理原则

如果出现：

```text
run/hz9_STOP_REQUIRED.json
```

不要重启，不要重新登录，不要继续点击。先读取 STOP 文件和最新日志，再判断是否需要人工登录。

暂停守护线程但保留 Chrome：

```bash
cd ~/projects/aideal-cps-data-lab || exit 1
pkill -f "run/hz10_guard_watchdog.sh" 2>/dev/null || true
pkill -f "python.*run/hz9_union_guarded_daemon.py" 2>/dev/null || true
pgrep -af "hz9_union_guarded_daemon|hz10_guard_watchdog|chrome.*19228" || true
```

不要关闭 Chrome，除非明确需要重启浏览器。

## 九、重要设计结论

1. 公共商品页不用登录即可采集商品卡片。
2. 一键领链必须登录。
3. 公开页和登录页源码都是 SPA 壳，不能靠 `view-source` 取商品。
4. 可靠采集路径是浏览器运行时 DOM/CDP，不是静态 HTML。
5. “按 SKU 搜索再领链”的方式不稳定；“可见商品卡顺序低频点击一键领链”更稳定。
6. 当前守护采集必须低频，不追求速度。
7. 遇到验证码/风控/登录失效，必须停止等待人工，不允许自动反复登录。
8. 杭州 2C4G 当前够用；先观察稳定性，不急于升级。

## 十、新对话启动后的第一步

先读取 GitHub 文档，然后执行状态检查命令。不要直接改代码，不要重新设计，不要重启 Chrome。先判断：

```text
HZ9/HZ10 是否运行
STOP_REQUIRED 是否存在
day_ok_count 是否增长
latest links 是否增长
```

然后根据状态继续。
