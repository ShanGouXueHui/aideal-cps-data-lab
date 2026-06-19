# 新对话无缝启动 Prompt

你现在继续 **AIdeal CPS / 智省优选——京东联盟佣金商品 Data Lab 商用化项目**。不要从头重新设计。请优先读取 GitHub 中已经沉淀的权威文档、代码和最新运行报告，再继续推进。

## 一、交互与执行规则

1. 使用中文，职业化、直接、结构化。
2. 优先直接读取和修改 GitHub，不依赖聊天短期上下文。
3. 用户明确要求：代码、长脚本和大段命令不要打印在对话中；工程修改直接通过 GitHub 增删改查。
4. 每次写 GitHub 后，必须通过 `fetch_file`、`fetch_commit` 或服务器 `git log` 二次确认真正落库。
5. GitHub 连接器确实无法完成时，才改用服务器本地 `git add / commit / push`。
6. 日志写入 `logs/`、`reports/` 或 `docs/debug/`；关键摘要提交 GitHub，用户不复制大段日志。
7. 用户通常只返回最终 `SUMMARY`；详细运行结果直接从 GitHub读取。
8. Linux 命令不使用 `set -e`，也不要使用会退出当前登录 Shell 的 `|| exit 1`。
9. 自动化测试不得调用 JD live API；JD live 只用于真实浏览器流量或明确手工 smoke。
10. 不使用 Codex CLI，除非用户重新明确要求。
11. 不用话术掩盖工程问题；价格、佣金、推广链接和数据一致性必须由代码、数据约束和报告验证。
12. 京东登录或验证可以由用户手工完成；账号密码、Cookie、Profile、Token、私钥和数据库密码不得进入 GitHub。

## 二、第一步必须读取

Data Lab 仓库：

```text
ShanGouXueHui/aideal-cps-data-lab
```

按顺序读取：

```text
docs/DOCUMENT_AUTHORITY.md
docs/project/CURRENT_PROJECT_CONTEXT.md
docs/status/COMMERCIALIZATION_STATUS_20260619.md
docs/project/ENVIRONMENT_AND_WORKING_RULES.md
docs/project/CODE_CHANGE_GUARDRAILS.md
docs/project/CODE_CHANGE_GUARDRAILS_IMPLEMENTATION.md
docs/architecture/COMMISSION_DATA_MYSQL_SYNC_V1.md
docs/architecture/commission_data_mysql_v1.sql
```

再读取最新运行事实：

```text
reports/hz23_round_latest.json
data/export/aideal_cps_products_commercial_candidate_manifest.json
reports/hz24_tab_overlap_analysis_latest.json
reports/hz24_increment_collection_latest.json
reports/project_engineering_audit_latest.json
```

AIdeal CPS 消费端仓库：

```text
ShanGouXueHui/aideal-cps
```

至少读取：

```text
docs/integration/DATA_LAB_INTEGRATION_AUTHORITY.md
docs/integration/DATA_LAB_COMMISSION_PRODUCTS_SIMPLE.md
docs/integration/DATA_LAB_MYSQL_SYNC_V1.md
app/models/product.py
app/services/product_service.py
app/services/promotion_service.py
app/core/db.py
app/core/config.py
```

发生冲突时：

```text
最新可验证代码和运行报告
> CURRENT_PROJECT_CONTEXT
> COMMERCIALIZATION_STATUS_20260619
> CODE_CHANGE_GUARDRAILS
> MySQL V1 架构
> 旧实验文档
```

## 三、环境

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
systemd：aideal.service
MySQL：aideal_cps
```

### 新加坡开发环境

```text
服务器：43.106.55.255
用户：cpsdev
角色：开发环境
```

杭州 `8.136.28.6` 是 AIdeal CPS 生产环境，不得与新加坡开发环境混淆。

## 四、当前准确进展

### HZ23“全部商品”已通过

权威轮次：

```text
round_id=20260615_100135
commercial_segment_complete=true
completed_pages=1..67
unfinished_pages=[]
stop_reason=null
scanned_total=4020
last_known_sku_count=3357
```

注意口径：

```text
4000 = 京东展示池
4020 = 67 页扫描卡片位总数
3665 = 完整轮次可见唯一 SKU
3698 = catalog index SKU
3357 = 已有可信推广链接 SKU
3304 = 通过全部候选门禁的商用候选
```

候选 manifest：

```text
row_count=3304
duplicate_sku_count=0
candidate_integrity_ready=true
successful_probes=2
observation_hours=68.88
observation_ready=true
gate_failures=[]
commercial_enabled=false
```

HZ20 历史污染已隔离，当前 `unsafe_hz20=0`。

### HZ24 专题 Tab 测重已通过

页面 Tab：

```text
超补爆品
限量高佣
秒杀专区
定向高佣
粉丝爱买
全部商品
```

5 个专题 Tab 均为滚动稳定的单页池，每个 50 个 SKU。

测重结果：

```text
membership_count=250
union_sku_count=239
cross_tab_duplicate_membership_count=11
overlap_with_3304_candidate=18
increment_queue=221
```

已完成跨 Tab、当前候选、可信推广链接和断点结果四层 SKU 去重。

### HZ24 增量采集当前停止

权威报告：

```text
queue_count=221
success_count=72
pending_count=149
stop_reason=item_fail_fuse
risk=[]
```

5 个连续失败样本均显示：

```text
已抢光
card-disabled
```

因此不是验证、风控或重复抓取，而是旧状态模型没有区分 unavailable 商品。

当前正确处理原则：

```text
linked=72，必须保留，不重复抓取
unavailable_sold_out=5，需要迁移为终态
可行动 pending 预计约 144
```

在 HZ24 v2 分类和工程审计治理完成前，**不要启动、重启或继续 HZ24 增量采集**。

## 五、当前最高优先级：工程治理

用户新增强制规则：

1. 修改文件前必须扫描重复定义、相邻模块已有实现和硬编码；
2. 一律不允许散落硬编码环境地址、路径、端口、URL、Tab、selector、等待时间和阈值；
3. 大文件必须分层解耦；
4. Python/Shell 单文件超过 300 行、单函数超过 80 行，必须先拆分再修改；
5. 正式代码只维护 main 一个主流分支。

全仓审计：

```text
reports/project_engineering_audit_latest.json
files_scanned=255
blocker_count=390
```

审计包含大量 HZ11-HZ22 历史实验脚本问题。新对话第一项工程任务不是盲目修 390 个文件，而是：

```text
识别当前活跃运行路径
-> 将历史实验代码标记为只读归档
-> 修复活跃 HZ23/HZ24/MySQL 路径 blocker
-> 抽取公共模块
-> 收口配置
-> 拆分大文件/长函数
-> 全量复扫
```

严禁在旧大文件上继续叠加新逻辑。

## 六、MySQL 商用架构

Data Lab 目标数据库：

```text
aideal_cps_data_lab
```

对象：

```text
commission_products
commission_refresh_runs
commission_product_history
commission_publish_versions
v_published_commission_products
```

网络与消费架构：

```text
AIdeal CPS 本地 127.0.0.1:13306
  -> 短生命周期 SSH Tunnel
Data Lab 127.0.0.1:3306
```

要求：

- Data Lab MySQL 不开放公网；
- 使用只读同步用户；
- Tunnel 只在同步任务期间存在；
- AIdeal CPS 用户请求只读本地 MySQL；
- 不允许用户请求实时访问 Data Lab；
- JSONL 永久保留为快照、回填、审计和灾备。

代码准备已完成较多，但数据库尚未实际初始化。

所有开关保持：

```text
DATA_LAB_DB_WRITE_ENABLED=false
DATA_LAB_DB_DUAL_WRITE_ENABLED=false
DATA_LAB_PUBLISH_ENABLED=false
DATA_LAB_SYNC_ENABLED=false
```

## 七、下一步执行顺序

严格顺序：

1. 直接从 GitHub读取工程审计详细结果；
2. 建立活跃主线文件清单和历史归档清单；
3. 修复活跃路径重复定义、重复实现和硬编码；
4. 拆分 HZ23/HZ24/MySQL 活跃大文件和长函数；
5. 全量复扫，活跃主线 blocker 清零；
6. 完成 HZ24 v2 `linked/unavailable/pending` 状态模型；
7. 保留 72 条 linked，将 5 条 sold-out 迁移为 unavailable；
8. 恢复单账号串行增量采集，只处理尚未完成且仍可推广的 SKU；
9. 对 221 条队列完成全终态校验；
10. 生成 HZ24 独立候选版本并与 3304 基线原子合并；
11. 初始化 Data Lab MySQL；
12. 幂等回填并执行二次回填验证；
13. 开启 dual-write，但 publish/sync 仍关闭；
14. 连续稳定运行 7 天；
15. 第 8 天生成 publish version；
16. AIdeal CPS dry-run 同步、灰度、正式商用。

## 八、一周稳定运行标准

稳定期开始条件：

```text
活跃主线工程 blocker 处理完成
HZ24 队列终态完整
最终候选 checksum/schema/hash 通过
MySQL 初始化和回填通过
JSONL/MySQL dual-write 已启用
publish/sync 仍为 false
```

稳定期要求：

- 连续 7 天无未解释差异；
- SKU 无重复；
- JSONL/MySQL 行数和 hash 一致；
- unavailable 不进入 published；
- 推广链接均为可信 `u.jd.com`；
- 价格和佣金使用 Decimal；
- 回滚测试通过；
- 任意未解释差异导致 7 天重新计时。

## 九、新对话第一条回复要求

不要要求用户重新复制旧日志，也不要立即运行 JD live。

先直接读取 GitHub并明确回答：

```text
1. 最新 main commits；
2. 工程审计中活跃主线 blocker；
3. HZ24 72 条 linked 数据是否完整；
4. HZ24 v2 unavailable 分类代码是否已落库并通过测试；
5. 当前是否允许恢复增量采集；
6. MySQL 初始化还缺哪些硬门禁；
7. 本轮准备直接修改哪些 GitHub 文件。
```

然后直接推进 GitHub 修改，并在每次写入后进行二次确认。