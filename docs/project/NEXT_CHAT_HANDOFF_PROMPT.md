# 新对话无缝启动 Prompt

你现在继续 AIdeal CPS / 智省优选 - 京东联盟佣金商品 Data Lab 商用化项目。请完整阅读本 Prompt，并优先读取 GitHub 文档和最新运行报告，不要从头重新设计。

## 一、交互规则

1. 使用中文，职业化、直接、结构化。
2. 优先直接读取和修改 GitHub；不要依赖聊天短期上下文。
3. 每次写 GitHub 后，必须使用 `fetch_file`、`fetch_commit` 或服务器 `git log` 二次确认真正落库。
4. GitHub 连接器写入不稳定时，改用服务器本地 `git add / commit / push`。
5. Linux 命令必须 copy-paste 可执行，不使用 `set -e`。
6. 命令分小步，不塞巨大脚本。
7. 日志写入 `logs/`、`reports/` 或 `docs/debug/` 并提交关键摘要；不要让用户复制大段日志。
8. 用户通常只贴最终 `SUMMARY`；你直接从 GitHub读取详细日志和报告。
9. 自动化测试不能调用 JD live API；JD live 只用于真实浏览器流量或显式手工 smoke。
10. 不使用 Codex CLI，除非用户重新明确要求。
11. 不用话术掩盖工程问题；价格、佣金、推广链接和数据一致性必须通过机制验证。

## 二、必须先读取的 GitHub 文档

仓库：

```text
https://github.com/ShanGouXueHui/aideal-cps-data-lab
```

按顺序读取：

```text
docs/project/CURRENT_PROJECT_CONTEXT.md
docs/project/ENVIRONMENT_AND_WORKING_RULES.md
docs/ops/DL2_HZ23_COMMERCIAL_OBSERVATION_PLAN.md
docs/architecture/COMMISSION_DATA_MYSQL_SYNC_V1.md
docs/architecture/commission_data_mysql_v1.sql
docs/contracts/AIDEAL_CPS_COMMISSION_PRODUCTS_SIMPLE_ACCESS.md
scripts/hz23_observation_daemon.sh
scripts/hz23_mainline_refresh.sh
scripts/hz23_status.sh
run/hz23_scan_current_page.py
run/hz23_finalize_round.py
```

AIdeal CPS 消费端仓库：

```text
https://github.com/ShanGouXueHui/aideal-cps
```

至少读取：

```text
docs/integration/DATA_LAB_COMMISSION_PRODUCTS_SIMPLE.md
app/models/product.py
app/services/product_service.py
app/services/promotion_service.py
app/core/db.py
app/core/config.py
```

发生冲突时优先级：最新可验证运行报告 > CURRENT_PROJECT_CONTEXT > MySQL V1 架构 > HZ23 观察计划 > 旧 JSONL/rsync 文档。

## 三、环境

### Data Lab

```text
服务器：121.41.111.36
用户：cpsdata
目录：/home/cpsdata/projects/aideal-cps-data-lab
GitHub：ShanGouXueHui/aideal-cps-data-lab
Chrome CDP：127.0.0.1:19228
noVNC：http://121.41.111.36:18772/vnc.html?autoconnect=true&resize=scale
systemd：aideal-hz23-observer.service
```

### AIdeal CPS 生产

```text
服务器：8.136.28.6
用户：deploy
目录：/home/deploy/projects/aideal-cps
GitHub：ShanGouXueHui/aideal-cps
本地 MySQL：aideal_cps
```

### 开发环境

```text
服务器：43.106.55.255
用户：cpsdev
角色：新加坡开发环境
```

杭州 `8.136.28.6` 是 AIdeal CPS 生产环境，不要混淆。

## 四、已完成的核心设计与进展

1. 京东联盟“商品推广 -> 全部商品”4000 池自动选择已解决。
2. 严格分页跳转、SKU 卡片定位、真实 mouse/pointer 点击“一键领链”已解决。
3. 错误风控词“购物无忧”已移除；只检测强验证信号。
4. HZ22 page 61-67 全部完成：

```text
commercial_segment_complete=true
completed_pages=[61,62,63,64,65,66,67]
unfinished_pages=[]
stop_reason=null
新增成功=162
失败=5
可信推广短链 SKU=2385
```

5. 当前准确口径：京东展示池 4000 条，已验证推广链接 2385 条，不是 4000 条全部入库。
6. HZ23 已安装为 `aideal-hz23-observer.service`：
   - 09:30-21:30 执行；
   - 夜间休息；
   - 每日随机探针；
   - 完整轮次成功后随机 3-5 天再刷新；
   - 商品等待 3-7 秒；
   - 页面等待 90-210 秒；
   - 强风控安全停止。
7. 首次日常探针已成功并提交：

```text
commit=7aeb147
时间=2026-06-14 10:05
page=50
scanned=59
risk=[]
prepare_ok=true
scan_ok=true
```

8. 首次 HZ23 1-67 页完整观察轮次原计划：

```text
2026-06-15 09:56 server-local
```

截至上一对话归档时，GitHub 尚未出现完整轮次完成报告，不能宣称商用观察已通过。

## 五、当前需要先做的状态确认

新对话第一步不要启动新任务，先从 GitHub确认最新状态：

1. 查 `main` 最新 commits；
2. 查是否出现：

```text
reports/hz23_round_latest.json
reports/hz23_round_<round_id>_latest.json
data/export/aideal_cps_products_commercial_candidate_manifest.json
docs/ops/DL2_HZ23_ROUND_<round_id>.md
```

3. 判断：

```text
commercial_segment_complete
completed_pages
unfinished_pages
scanned_total
catalog_new
catalog_changed
catalog_unchanged
last_known_sku_count
stop_page
stop_reason
duplicate_sku_count
observation_ready
```

4. 如果 GitHub 没有完整轮次报告，说明尚未完成或尚未提交；再给一个最小状态发布命令，不让用户贴大日志。
5. 如果完整轮次成功，再判断是否满足 48-72 小时、两个探针和 >=3900 扫描覆盖；不满足则继续观察。

## 六、目标商用数据库架构

当前 Data Lab 尚无正式 MySQL，但最终方案已固定：

```text
数据库：aideal_cps_data_lab
主表：commission_products
轮次表：commission_refresh_runs
历史表：commission_product_history
发布版本表：commission_publish_versions
只读视图：v_published_commission_products
```

AIdeal CPS 使用短生命周期 SSH Tunnel 定时同步：

```text
AIdeal CPS 127.0.0.1:13306
  -> ssh -L
Data Lab 127.0.0.1:3306
```

连接约定：

```text
SSH_HOST=121.41.111.36
SSH_USER=cpsdata
SSH_KEY=/home/deploy/.ssh/aideal_data_lab_ro_ed25519
DATA_LAB_DB_NAME=aideal_cps_data_lab
DATA_LAB_DB_USER=aideal_cps_ro
```

密码仅存在服务器 Secret/.env，不进入 GitHub。

不开放公网 3306，不使用长期常驻 Tunnel。用户请求始终读取 AIdeal CPS 本地 `aideal_cps.products`。

## 七、编程规范

1. 分层解耦：browser/collector、application/service、domain、persistence/repository、contracts、ops、tests。
2. Playwright selector 不散落到业务层。
3. JSONL 和 MySQL 实现同一个 Repository 接口。
4. 配置与 Secret 分离；所有写入/发布/sync feature flag 默认 false。
5. 金额使用 Decimal/DECIMAL。
6. SKU 唯一，写入幂等，使用事务和唯一约束。
7. 未变化只更新时间戳；变化才写 history。
8. 连续两次完整成功轮次未出现才 inactive，不物理删除。
9. 可以本机备份，但正式代码只有 main 一个主流分支。
10. 自动化测试不调用 JD live。
11. 任何正式切换必须有备份、回滚、审计和一致性报告。

## 八、下一步执行计划

### 若 HZ23 观察尚未通过

1. 继续读取 GitHub报告；
2. 修复观察服务或补第二次探针；
3. 并行准备 MySQL，但保持：

```text
DATA_LAB_DB_WRITE_ENABLED=false
DATA_LAB_DB_DUAL_WRITE_ENABLED=false
DATA_LAB_PUBLISH_ENABLED=false
DATA_LAB_SYNC_ENABLED=false
```

4. 创建 Data Lab MySQL migration、model、Repository、JSONL 回填器和一致性测试；
5. 创建 AIdeal CPS Tunnel 和同步器代码，但不正式启用。

### 若 HZ23 观察全部通过

1. 备份当前 JSONL/state/history；
2. 初始化 Data Lab MySQL；
3. 回填 2385+ 可信商品；
4. 验证行数、SKU 去重、短链、价格和佣金；
5. 开启 dual-write；
6. 运行一个完整刷新轮次并做 JSONL/MySQL 一致性校验；
7. 发布只读视图；
8. AIdeal CPS dry-run 同步；
9. 灰度接入；
10. 正式商用。

现在先直接读取 GitHub最新 commits 和 HZ23 报告，给出“已完成/未完成/风险/下一步”的明确结论，然后继续推进。不要让我重新复制历史日志。
