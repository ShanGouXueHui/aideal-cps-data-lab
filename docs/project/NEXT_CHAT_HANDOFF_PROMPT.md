# 新对话无缝启动 Prompt

将下面内容作为新对话第一条消息。不要依赖旧聊天记录，先从 GitHub 恢复上下文。

---

你现在继续 **AIdeal CPS / 智省优选——京东联盟佣金商品 Data Lab 商用化项目**。

不要从头重新设计，不要让我重新复制旧日志。先直接读取 GitHub 中的权威文档、当前代码和最新报告，再继续推进。

## 一、当前唯一优先级

**先把代码问题 100% 治理完成，再推进任何功能。**

特别要求：

- 重复定义函数、类、方法和 Shell 函数必须为 0；
- 重复定义或静默覆盖变量、模块常量、配置键和默认值必须为 0；
- 跨文件重复实现必须为 0；
- 全局 blocker 必须为 0，不只看 active scope；
- 大文件和长函数必须清零；
- 代码报告必须绑定当前 main；
- 代码治理完成前，不恢复 HZ24、不初始化 MySQL、不推进商用同步。

## 二、交互与执行规则

1. 使用中文，职业化、直接、结构化。
2. 优先直接读取和修改 GitHub，不依赖聊天短期上下文。
3. 代码、长脚本和复杂命令不要打印在对话中，直接提交 GitHub。
4. 用户只执行仓库内经过审核的单一 `.sh` 入口，避免零散命令和粘贴截断。
5. 每次写 GitHub 后必须通过 `fetch_file`、`fetch_commit` 或服务器 `git log` 二次确认。
6. 详细日志写入 `logs/`、`reports/` 或 `docs/debug/`；用户只返回紧凑 Summary。
7. 助手直接从 GitHub读取报告，不要求用户重复复制旧日志。
8. Linux 脚本不使用 `set -e`，也不使用会退出登录 Shell 的 `|| exit 1`。
9. 自动化测试不得调用 JD live API。
10. 不使用 Codex CLI。
11. 账号、密码、Cookie、Profile、Token、私钥和数据库密码不得进入 GitHub。
12. 不用话术掩盖工程问题；价格、佣金、推广链接和一致性必须由代码、约束和报告验证。

## 三、第一步必须读取

Data Lab：

```text
ShanGouXueHui/aideal-cps-data-lab
```

按顺序读取：

```text
docs/DOCUMENT_AUTHORITY.md
docs/status/COMMERCIALIZATION_STATUS_20260620.md
docs/project/CURRENT_PROJECT_CONTEXT.md
docs/project/PROJECT_MEMORY_20260620.md
docs/project/CODE_CHANGE_GUARDRAILS.md
docs/project/CODE_CHANGE_GUARDRAILS_IMPLEMENTATION.md
docs/project/EXECUTION_TOPOLOGY.md
docs/project/ENVIRONMENT_AND_WORKING_RULES.md
docs/architecture/COMMISSION_DATA_MYSQL_SYNC_V1.md
docs/architecture/commission_data_mysql_v1.sql
```

再读取当前报告和产物：

```text
reports/project_engineering_audit_latest.json
reports/offline_quality_latest.json
reports/hz23_round_latest.json
data/export/aideal_cps_products_commercial_candidate_manifest.json
reports/hz24_tab_overlap_analysis_latest.json
reports/hz24_increment_collection_latest.json
```

如果存在，再读取：

```text
reports/hz24_sold_out_migration_latest.json
reports/hz24_terminal_repair_latest.json
reports/hz24_resume_gate_latest.json
reports/hz24_collection_authorization_latest.json
reports/hz24_collection_guard_latest.json
```

AIdeal CPS 消费端：

```text
ShanGouXueHui/aideal-cps
```

至少读取：

```text
docs/integration/DATA_LAB_INTEGRATION_AUTHORITY.md
docs/integration/DATA_LAB_COMMISSION_PRODUCTS_SIMPLE.md
docs/integration/DATA_LAB_MYSQL_SYNC_V1.md
```

## 四、环境拓扑

### 杭州 Data Lab 生产

```text
121.41.111.36 / cpsdata
/home/cpsdata/projects/aideal-cps-data-lab
```

唯一允许真实 JD 登录、浏览器 Profile、HZ23/HZ24、生产状态和 Data Lab MySQL 的环境。

### 新加坡 CI Bridge

```text
43.106.55.255 / datalab
/home/datalab/projects/aideal-cps-data-lab
```

只运行离线编译、测试、工程审计和脱敏报告回写。不得运行真实 JD、生产采集或生产 MySQL。

### 杭州 AIdeal CPS 生产

```text
8.136.28.6 / deploy
/home/deploy/projects/aideal-cps
```

只消费 Data Lab 已发布版本。

### 操作方式

运维人员只登录杭州 `cpsdata`，再 SSH 进入新加坡 `datalab`。离线验证执行在新加坡。

统一入口：

```text
scripts/ops/run_ci_bridge_from_hangzhou.sh
scripts/ops/run_data_lab_ci_bridge.sh
```

不要再给大量零散命令。需要执行的新流程先写成 GitHub 脚本。

## 五、当前准确进展

### 1. HZ23 last-known-good

2026-06-15 最后一次已验证：

```text
round_id=20260615_100135
completed_pages=1..67
candidate_rows=3304
duplicate_sku_count=0
payload_hash_mismatch=0
successful_probes=2
observation_ready=true
```

这 3304 条是历史 last-known-good，不是当前 latest manifest。

### 2. 当前 HZ23 latest 回归

当前轮次：

```text
round_id=20260620_101332
completed_pages=1..67
commercial_segment_complete=true
scanned_total=4017
last_known_sku_count=3858
successful_probes=4
```

当前 manifest：

```text
row_count=0
eligible_sku_count=0
trusted_dedup_sku_count=0
candidate_integrity_ready=false
observation_ready=false
gate_failures=[candidate_nonempty]
data_sha256=empty-file SHA-256
```

结论：当前 latest candidate 无效。不能用于 MySQL、发布或代表 3304 基线。代码治理完成后，必须在杭州只读恢复和核验 last-known-good，并修复 canonical promotion 链。

### 3. HZ24

```text
专题 membership=250
去重后 SKU=239
重叠=18
增量队列=221
旧 linked=72
明确 sold-out=5
旧 pending=149
预计可行动 pending=144
```

HZ24 v2 代码和离线测试已覆盖 linked/unavailable/pending、sold-out、原子迁移、回滚、72/5/144、恢复授权和报告白名单。

但 GitHub 没有生产报告证明杭州已实际完成 5 条迁移和 72/5/144 核验。

```text
HZ24 runtime migration confirmed=false
HZ24 resume allowed=false
```

不要启动旧采集器。

### 4. 工程审计

最新已发布报告：

```text
git_head=07b8db89274addd4d85c1308bc41a89a0352abab
files_scanned=298
status=FAIL
global/full gate blocker=210
active blocker=0
compatibility blocker=0
historical blocker=195
support blocker=15
warning=635
```

blocker 分类：

```text
hardcoded_absolute_path=3
hardcoded_ip=42
hardcoded_parameter=107
hardcoded_url=58
```

该报告没有发现重复函数/类/方法、重复实现、大文件或长函数，但扫描器尚未完整检测重复变量、模块常量、Shell 配置赋值和配置重复键。因此不能宣称重复问题已 100% 解决。

历史快照分支：

```text
history-snapshot-20260620
```

main 仍有 54 个历史 Shell blocker 文件和 6 个 support blocker 文件。

### 5. Offline Quality

```text
git_head=07b8db89274addd4d85c1308bc41a89a0352abab
status=PASS
tests_run=63
failures=0
errors=0
jd_live_called=false
```

该报告已落后于当前 main，必须重跑。

### 6. MySQL 和同步

尚未执行：

```text
Data Lab MySQL 初始化
有效候选回填
二次幂等回填
dual-write
7 天稳定运行
publish version
AIdeal CPS dry-run/灰度/正式同步
```

所有开关保持 false。

## 六、代码治理验收标准

必须同时满足：

```text
global_blocker_count=0
full_gate_blocker_count=0
active_blocker_count=0
compatibility_blocker_count=0
historical_blocker_count=0
support_blocker_count=0
duplicate_definition=0
duplicate_assignment=0
duplicate_config_key=0
duplicate_implementation=0
large_file=0
long_function=0
compile=PASS
offline_quality=PASS
jd_live_called=false
offline git_head=current main
audit git_head=current main
```

不得通过扩大排除目录、降低严重度、只检查 active scope 或 `continue-on-error` 伪造通过。

## 七、新对话严格执行顺序

1. 读取上述 GitHub 文档、报告和 current main；
2. 给审计器增加 Python/Shell 重复变量、常量和配置键检测及测试；
3. 确认重复函数、重复变量、重复实现检测口径完整；
4. 将 main 剩余 HZ12-HZ21 历史 Shell 移出，历史只保留快照分支；
5. 收口 support 测试 fixture 和配置默认值；
6. 新加坡对当前 main 运行编译、Offline Quality 和全量 Engineering Audit；
7. 全局代码门禁全部为 0 后，才处理 HZ23 last-known-good 恢复；
8. 修复并验证 HZ23 临时生成、门禁检查、原子晋级和 canonical 保护；
9. 杭州执行 HZ24 5 条 sold-out 迁移并确认 72/5/144；
10. 221 队列全终态后，才恢复剩余可行动采集；
11. 最终候选冻结后初始化 MySQL、回填和二次幂等验证；
12. dual-write 稳定运行 7 天；
13. publish version；
14. AIdeal CPS dry-run、灰度和正式商用。

## 八、新对话第一条回复要求

不要让用户复制旧日志，不要运行 JD live，不要直接恢复 HZ24。

第一条回复必须直接从 GitHub回答：

```text
1. 最新 main commit；
2. 当前审计报告是否绑定 main；
3. 全局、active、compatibility、historical、support blocker；
4. 重复函数/类/方法检测结果；
5. 重复变量/常量/配置键检测是否已实现；
6. 当前 0 行 candidate manifest 回归状态；
7. HZ24 72 linked 和 5 unavailable 是否有生产报告证明；
8. 当前是否允许恢复 HZ24；
9. MySQL 初始化缺哪些门禁；
10. 本轮准备直接修改哪些 GitHub 文件。
```

随后直接修改 GitHub推进代码治理，并在每次写入后二次确认。

---
