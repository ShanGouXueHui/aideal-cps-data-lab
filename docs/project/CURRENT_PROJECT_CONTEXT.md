# AIdeal CPS Data Lab 当前项目上下文

更新日期：2026-06-19

状态：当前主线权威上下文。新对话必须先读本文，再读本文引用的专项文档和最新 GitHub 报告。

## 1. 项目目标与边界

AIdeal CPS Data Lab 负责从京东联盟授权页面采集可推广商品，解析 SKU、标题、图片、价格、佣金和商品状态，生成并验证 `https://u.jd.com/...` 推广短链，持续维护可信佣金商品主数据，并向 AIdeal CPS 商用微信导购系统提供版本化、可审计的数据。

Data Lab 不面向终端用户。终端用户访问、搜索、推荐、H5 展示、点击归因、订单和返佣由 `ShanGouXueHui/aideal-cps` 负责。

用户请求链路不得实时依赖 Data Lab 浏览器、SSH Tunnel 或远程数据库。AIdeal CPS 只读取自己的本地 MySQL；Data Lab 通过短生命周期 SSH Tunnel 定时同步已发布版本。

## 2. HZ23“全部商品”商用观察已通过

### 2.1 已验证主链路

已经解决并稳定验证：

1. 自动进入京东联盟商品推广页面；
2. 精确选择“全部商品”；
3. 确认展示池为“共 4000 条”；
4. 使用正确分页器跳转 1-67 页；
5. 按 SKU 精确定位真实商品卡片；
6. 使用真实 mouse/pointer 事件点击“一键领链”；
7. 获取并验证 `https://u.jd.com/...` 推广短链；
8. SKU 去重、逐页断点、原子落盘；
9. 遇到真实京东验证页安全停止，不绕过验证；
10. 手工验证后可从同一 round 断点继续，不重扫已完成页。

### 2.2 完整轮次事实

权威报告：

```text
reports/hz23_round_latest.json
round_id=20260615_100135
commercial_segment_complete=true
completed_pages=1..67
unfinished_pages=[]
stop_page=null
stop_reason=null
scanned_total=4020
last_known_sku_count=3357
```

`scanned_total=4020` 是 67 页卡片位扫描总和，不是 4020 个唯一 SKU。完整轮次实际可见唯一 SKU 为 3665，catalog index 为 3698。

### 2.3 商用候选事实

权威 manifest：

```text
data/export/aideal_cps_products_commercial_candidate_manifest.json
row_count=3304
eligible_sku_count=3304
duplicate_sku_count=0
candidate_integrity_ready=true
successful_probes=2
observation_hours=68.88
observation_ready=true
gate_failures=[]
commercial_enabled=false
```

准确口径：

```text
京东“全部商品”展示池：4000 条
完整轮次可见唯一 SKU：3665
catalog index SKU：3698
已有可信推广链接 SKU：3357
当前通过全部商用候选门禁：3304
```

不得把 4000 条展示池、4020 个扫描卡片位、3698 个 catalog SKU 或 3357 个可信链接 SKU 混写成 3304 条可发布候选。

### 2.4 HZ20 历史污染处理

源 JSONL 中曾发现 10 条 HZ20 历史记录。已完成备份、隔离和原子清理：

```text
unsafe_hz20=0
candidate_validation_ok=true
candidate_integrity_ready=true
```

HZ20 记录不得重新进入可信池或 MySQL 回填。

## 3. HZ24 专题 Tab 扩展

页面已确认 6 个并列 Tab：

```text
超补爆品
限量高佣
秒杀专区
定向高佣
粉丝爱买
全部商品
```

5 个专题 Tab 均为滚动稳定后的单页精选池，每个 50 个 SKU，无分页组件。

权威测重报告：

```text
reports/hz24_tab_overlap_analysis_latest.json
analysis_ready=true
special_tab_membership_count=250
special_tab_union_sku_count=239
cross_tab_duplicate_membership_count=11
overlap_with_candidate_count=18
increment_vs_candidate_count=221
promotion_link_required_count=221
```

去重口径：

1. 先对 5 个专题 Tab 按 SKU 全局去重：250 个成员 -> 239 个唯一 SKU；
2. 再排除当前 3304 条候选及已有可信推广链接：排除 18 个；
3. 最终冻结待领链队列：221 个 SKU。

### 3.1 当前增量采集进展

权威报告：

```text
reports/hz24_increment_collection_latest.json
queue_count=221
success_count=72
pending_count=149
stop_reason=item_fail_fuse
risk=[]
```

本次停止不是京东验证，也不是重复抓取。连续 5 个商品卡片显示“已抢光”，存在 `card-disabled` 遮罩，旧采集器将其错误计为普通点击失败并触发熔断。

当前必须保留的事实：

```text
已成功生成并落盘：72
明确已抢光样本：5
旧报告 pending_count：149
```

正确的目标状态模型应拆分为：

```text
linked
unavailable_sold_out / unavailable_off_shelf / unavailable_not_promotable
pending
```

已抢光商品不得继续反复点击，不得伪装为成功推广商品，也不得进入商用候选。下一步需要完成并验证 HZ24 v2 分类、迁移这 5 条失败记录为 unavailable 终态、保留 72 条成功结果，再继续处理约 144 条可行动 pending。

HZ24 数据在完整校验前保持隔离，不直接修改 HZ23 的 3304 条商用基线。

## 4. 工程审计与代码治理

用户新增强制规则：

1. 修改任何文件前必须扫描重复定义、相邻模块已有实现和硬编码；
2. 环境地址、路径、端口、URL、Tab、selector、阈值、等待时间、服务名和数据库名不得散落硬编码；
3. 大文件必须先分层拆分，禁止继续叠加；
4. Python/Shell 单文件超过 300 行、单函数超过 80 行时必须治理；
5. 正式代码只维护 `main` 一个主流分支。

权威规则：

```text
docs/project/CODE_CHANGE_GUARDRAILS.md
docs/project/CODE_CHANGE_GUARDRAILS_IMPLEMENTATION.md
```

全仓基线审计已生成：

```text
reports/project_engineering_audit_latest.json
files_scanned=255
blocker_count=390
```

审计发现包括重复定义/重复实现、硬编码、大文件和长函数。大量问题位于 HZ11-HZ22 历史实验脚本，但在完成“当前活跃主线 / 只读历史归档”分类前，不得简单忽略或删除。

当前工程优先级：

```text
冻结新增业务逻辑
-> 标记活跃运行路径和历史归档路径
-> 修复活跃 HZ23/HZ24/MySQL 路径 blocker
-> 公共能力抽取到共享模块
-> 配置统一收口
-> 大文件拆分
-> 全量复扫
-> blocker 清零或形成经批准的历史归档排除清单
```

`project_directory_missing` 已确认来自旧命令依赖固定服务器目录。后续工程扫描使用仓库根目录自动解析或 GitHub Actions，不再依赖用户当前 Shell 路径。

## 5. Data Lab MySQL 商用架构

目标数据库：

```text
aideal_cps_data_lab
```

固定对象：

```text
commission_products
commission_refresh_runs
commission_product_history
commission_publish_versions
v_published_commission_products
```

网络边界：

- MySQL 仅监听 Data Lab `127.0.0.1:3306`；
- 不开放公网 3306；
- AIdeal CPS 同步任务临时建立 SSH Tunnel：本地 `127.0.0.1:13306` -> Data Lab `127.0.0.1:3306`；
- 使用只读数据库用户；
- 同步完成立即关闭 Tunnel；
- Secret、密码和私钥不进入 GitHub。

已完成代码准备：DDL/migration、Repository、事务安全 staging V2、幂等回填、候选校验、落库后结构和逐行 hash 验证、AIdeal CPS 预检设计。实际 Data Lab MySQL 尚未初始化，3304 条候选尚未正式回填。

所有开关继续保持：

```text
DATA_LAB_DB_WRITE_ENABLED=false
DATA_LAB_DB_DUAL_WRITE_ENABLED=false
DATA_LAB_PUBLISH_ENABLED=false
DATA_LAB_SYNC_ENABLED=false
```

## 6. 一周稳定运行与商用切换原则

目标顺序：

1. 工程活跃主线 blocker 处理完成；
2. HZ24 增量采集完成并通过 linked/unavailable/pending 完整性校验；
3. 冻结可回填候选版本；
4. 初始化 Data Lab MySQL；
5. 回填候选并执行二次幂等回填；
6. 校验行数、SKU、推广链接、价格、佣金、hash 和 round lineage；
7. 开启 JSONL/MySQL dual-write，但 publish/sync 继续关闭；
8. 连续稳定运行 7 天；
9. 任意未解释差异、重复、丢失、风控误写或回滚失败，稳定期重新计时；
10. 第 8 天生成正式 publish version；
11. AIdeal CPS dry-run 同步到本地 MySQL；
12. 灰度后正式商用。

AIdeal CPS 不直接在用户请求中查询 Data Lab MySQL。商用数据从 `v_published_commission_products` 版本化同步到 AIdeal CPS 本地数据库。

## 7. 环境事实

### Data Lab

```text
服务器：121.41.111.36
用户：cpsdata
目录：/home/cpsdata/projects/aideal-cps-data-lab
GitHub：ShanGouXueHui/aideal-cps-data-lab
分支：main
Chrome CDP：127.0.0.1:19228
systemd：aideal-hz23-observer.service
noVNC：http://121.41.111.36:18772/vnc.html?autoconnect=true&resize=scale
```

### AIdeal CPS 生产

```text
服务器：8.136.28.6
用户：deploy
目录：/home/deploy/projects/aideal-cps
GitHub：ShanGouXueHui/aideal-cps
分支：main
MySQL：aideal_cps
systemd：aideal.service
```

### 新加坡开发环境

```text
服务器：43.106.55.255
用户：cpsdev
角色：开发环境
```

杭州 `8.136.28.6` 是 AIdeal CPS 生产环境；新加坡机器不能与生产角色混淆。

## 8. 工作与交互规则

- 使用中文，职业化、直接、结构化；
- 优先直接读取和修改 GitHub，不依赖聊天短期上下文；
- 用户要求代码和长命令不要打印在对话中，工程修改直接通过 GitHub 完成；
- 每次 GitHub 写入后必须 `fetch_file`、`fetch_commit` 或服务器 `git log` 二次确认；
- 日志和详细结果写入 `logs/`、`reports/`、`docs/debug/`，用户只返回紧凑 Summary；
- 不使用 Codex CLI，除非用户重新明确要求；
- Linux 命令不使用 `set -e`，也不要用会退出登录 Shell 的 `|| exit 1`；
- 自动化测试禁止调用 JD live；
- 允许必要时手工完成京东登录/验证，但账号密码、Cookie、Profile 和 Secret 不进入 GitHub；
- 不用话术掩盖工程问题，价格、佣金、推广链接和一致性必须由代码、约束和报告验证。

## 9. 当前下一步

严格按顺序：

1. 保持 HZ24 增量采集暂停，保留 72 条成功结果；
2. 从全仓工程审计报告中区分活跃主线与历史实验脚本；
3. 修复活跃主线重复定义、硬编码、大文件和长函数；
4. 完成 HZ24 v2 unavailable 分类及迁移测试；
5. 恢复单账号串行增量采集，只处理未完成且仍可推广的 SKU；
6. 完成 HZ24 全队列终态校验并生成独立候选版本；
7. 初始化 Data Lab MySQL，回填最终候选；
8. 开启 dual-write 并执行 7 天稳定运行；
9. 生成 publish version；
10. AIdeal CPS dry-run、灰度和正式商用。

## 10. 权威文档和报告

```text
docs/DOCUMENT_AUTHORITY.md
docs/project/CURRENT_PROJECT_CONTEXT.md
docs/project/ENVIRONMENT_AND_WORKING_RULES.md
docs/project/CODE_CHANGE_GUARDRAILS.md
docs/project/CODE_CHANGE_GUARDRAILS_IMPLEMENTATION.md
docs/status/COMMERCIALIZATION_STATUS_20260619.md
docs/architecture/COMMISSION_DATA_MYSQL_SYNC_V1.md
docs/project/NEXT_CHAT_HANDOFF_PROMPT.md
reports/hz23_round_latest.json
data/export/aideal_cps_products_commercial_candidate_manifest.json
reports/hz24_tab_overlap_analysis_latest.json
reports/hz24_increment_collection_latest.json
reports/project_engineering_audit_latest.json
```

发生冲突时：最新可验证代码与运行报告 > 本文 > 专项架构/计划文档 > 旧实验文档。