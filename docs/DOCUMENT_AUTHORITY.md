# 文档权威顺序

更新日期：2026-06-20

## 1. 当前主线权威顺序

```text
1. 当前 main 代码
2. 绑定当前 main HEAD 的运行报告
3. docs/project/PROJECT_HANDOFF_20260620.md
4. docs/status/COMMERCIALIZATION_STATUS_20260620.md
5. docs/project/CURRENT_PROJECT_CONTEXT.md
6. docs/project/PROJECT_MEMORY_20260620.md
7. docs/project/CODE_CHANGE_GUARDRAILS.md
8. docs/project/CODE_CHANGE_GUARDRAILS_IMPLEMENTATION.md
9. docs/project/EXECUTION_TOPOLOGY.md
10. docs/project/ENVIRONMENT_AND_WORKING_RULES.md
11. docs/status/CHAT_ARCHIVE_20260620.md
12. docs/architecture/COMMISSION_DATA_MYSQL_SYNC_V1.md
13. docs/architecture/commission_data_mysql_v1.sql
14. docs/project/NEXT_CHAT_HANDOFF_PROMPT.md
```

`PROJECT_HANDOFF_20260620.md` 是本轮长对话的高密度交接入口，包含环境、设计、工程规范、当前状态、未完成任务和严格下一步。

`COMMERCIALIZATION_STATUS_20260619.md` 及更早状态文件只作为历史快照，不再作为当前默认状态入口。

## 2. 当前必须读取的报告和产物

```text
reports/project_engineering_audit_latest.json
reports/offline_quality_latest.json
reports/hz23_round_latest.json
data/export/aideal_cps_products_commercial_candidate_manifest.json
reports/hz24_tab_overlap_analysis_latest.json
reports/hz24_increment_collection_latest.json
```

若存在，还应读取：

```text
reports/hz24_sold_out_migration_latest.json
reports/hz24_terminal_repair_latest.json
reports/hz24_resume_gate_latest.json
reports/hz24_collection_authorization_latest.json
reports/hz24_collection_guard_latest.json
```

报告使用规则：

- 检查 `generated_at`；
- 检查 `git_head` 是否等于当前 main；
- 检查 round_id、schema、checksum 和返回码；
- 报告不存在时不能根据测试代码推断生产动作已执行；
- 陈旧报告不能放行下一阶段；
- 失败后禁止复用上一轮 latest 报告伪装当前成功。

## 3. 当前关键事实

### HZ23

- 2026-06-15 的 3304 条是最后一次已验证 last-known-good；
- 当前 latest manifest 为 0 行且 `candidate_integrity_ready=false`；
- 当前 latest 不能用于 MySQL、publish 或商用；
- 必须在杭州生产机只读恢复并核验 last-known-good 候选。

### HZ24

- 队列 221；
- 旧 linked 72；
- 明确 sold-out 5；
- 旧 pending 149，预计可行动 144；
- v2 代码和离线测试已存在；
- 没有杭州生产报告证明 5 条迁移和 72/5/144 已落地；
- 继续暂停。

### 工程治理

- 最新已提交审计扫描 306 个文件，global/full gate blocker=210；
- active/compatibility blocker=0，但全局门禁失败；
- 最新已提交 Offline Quality 为 66 项 PASS、0 failure、0 error、`jd_live_called=false`；
- 两份报告均只对各自 `git_head` 有效，必须在当前 main 上重跑；
- 审计器尚未完整覆盖重复变量、模块常量、配置键和默认值多源；
- 完成该能力并取得全局零 blocker 前，不得宣称代码问题 100% 解决。

## 4. 环境角色

```text
杭州 Data Lab 生产：121.41.111.36 / cpsdata
新加坡 CI Bridge：43.106.55.255 / datalab
杭州 AIdeal CPS 生产：8.136.28.6 / deploy
```

用户可从杭州 `cpsdata` SSH 进入新加坡 `datalab`，但执行角色不变：

- 杭州运行真实采集和未来 Data Lab MySQL；
- 新加坡只运行离线编译、测试、审计和脱敏报告回写；
- AIdeal CPS 生产只消费已发布版本。

统一脚本：

```text
scripts/ops/run_ci_bridge_from_hangzhou.sh
scripts/ops/run_data_lab_ci_bridge.sh
scripts/ops/ci_bridge_runner.py
scripts/ops/ci_bridge_report_gate.py
scripts/ops/ci_bridge_summary.py
```

## 5. 工程门禁

正式验收必须同时满足：

```text
global_blocker_count=0
full_gate_blocker_count=0
active_blocker_count=0
compatibility_blocker_count=0
historical_blocker_count=0
support_blocker_count=0
duplicate_definition=0
duplicate_assignment=0
duplicate_constant_assignment=0
duplicate_config_key=0
duplicate_default_source=0
duplicate_implementation=0
large_file=0
long_function=0
python_shell_syntax=PASS
offline_quality=PASS
jd_live_called=false
audit git_head=current main
offline git_head=current main
```

历史实验代码保留在 Git 历史或只读快照分支，从 main 移除；不得通过降低严重度、扩大排除范围或只看 active scope 伪造通过。

## 6. 冲突处理

- 当前 main 和绑定当前 HEAD 的报告优先于文档；
- `PROJECT_HANDOFF_20260620.md` 是本轮高密度交接入口；
- `COMMERCIALIZATION_STATUS_20260620.md` 是当前任务状态；
- `CURRENT_PROJECT_CONTEXT.md` 是当前事实入口；
- `PROJECT_MEMORY_20260620.md` 是长期设计、环境和交互记忆；
- `CHAT_ARCHIVE_20260620.md` 记录本轮归档和被否决方案；
- `EXECUTION_TOPOLOGY.md` 定义服务器角色和 SSH 方向；
- `CODE_CHANGE_GUARDRAILS*` 定义强制工程门禁；
- MySQL V1 优先于旧 rsync-only 设计；
- Secret、账号和真实密码永远只以服务器 Secret/`.env` 为准；
- breaking change 必须新建合同版本；
- 当前无效 0 行 manifest 不得覆盖或代表 3304 last-known-good。