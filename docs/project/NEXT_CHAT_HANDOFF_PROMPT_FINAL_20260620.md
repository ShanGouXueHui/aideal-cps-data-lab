# 新对话无缝启动 Prompt（最终版）

将下面内容作为新对话第一条消息：

你现在继续 **AIdeal CPS / 智省优选——京东联盟佣金商品 Data Lab 商用化项目**。

不要从头设计，不要让我复制旧日志。先直接读取 GitHub，再继续修改。

当前唯一优先级：代码治理逻辑已经清零，但正式验收仍被旧任务把工程审计报告提交到 main、导致报告自陈旧所阻断。

严格顺序：

1. 在新加坡 `datalab` 只读定位并停止旧 audit publisher；
2. 将所有运行证据发布从 `main` 迁移到 `runtime-evidence`；
3. 对当前 main 重跑 Full Audit 和 Offline Quality；
4. 确认 `quality-reports.git_head == current main`，且 main 不再被报告推进；
5. 再在杭州执行 HZ23 3304 last-known-good 只读盘点；
6. 不立即恢复 canonical，后续单独验证备份、原子恢复和回滚。

在上述完成前，不恢复 HZ24、不初始化 MySQL、不 publish、不同步 AIdeal CPS。

必须读取 Data Lab 仓库 `ShanGouXueHui/aideal-cps-data-lab`：

```text
docs/DOCUMENT_AUTHORITY.md
docs/project/PROJECT_HANDOFF_20260620.md
docs/status/COMMERCIALIZATION_STATUS_20260620.md
docs/project/CURRENT_PROJECT_CONTEXT.md
docs/project/PROJECT_MEMORY_20260620.md
docs/project/CODE_CHANGE_GUARDRAILS.md
docs/project/CODE_CHANGE_GUARDRAILS_IMPLEMENTATION.md
docs/project/EXECUTION_TOPOLOGY.md
docs/project/ENVIRONMENT_AND_WORKING_RULES.md
docs/status/CHAT_ARCHIVE_20260620_PART2.md
docs/project/NEXT_CHAT_HANDOFF_PROMPT_FINAL_20260620.md
```

再读取：

```text
quality-reports:reports/project_engineering_audit_latest.json
quality-reports:reports/offline_quality_latest.json
reports/hz23_round_latest.json
data/export/aideal_cps_products_commercial_candidate_manifest.json
reports/hz24_tab_overlap_analysis_latest.json
reports/hz24_increment_collection_latest.json
```

读取 AIdeal CPS 仓库 `ShanGouXueHui/aideal-cps`：

```text
docs/integration/DATA_LAB_INTEGRATION_AUTHORITY.md
docs/integration/DATA_LAB_COMMISSION_PRODUCTS_SIMPLE.md
docs/integration/DATA_LAB_MYSQL_SYNC_V1.md
```

环境：

```text
杭州 Data Lab：121.41.111.36 / cpsdata
新加坡 CI Bridge：43.106.55.255 / datalab
杭州 AIdeal CPS：8.136.28.6 / deploy
```

杭州到新加坡统一使用：

```text
ssh -o BatchMode=yes sg-aideal-datalab
```

该链路已经验证成功。正确用户是 `datalab`，不是 `cpsdev`；`datalab` 不在 sudoers。

当前事实：

```text
files_scanned=258
全部 scope blocker=0
全部 duplicate category=0
large_file=0
long_function=0
syntax=PASS
offline tests=69
failure=0
error=0
jd_live_called=false
CODE_GOVERNANCE_LOGIC_COMPLETE=true
CODE_GOVERNANCE_FORMAL_ACCEPTANCE=false
CURRENT_HEAD_VALIDATED=false
```

新加坡可能仍有旧 checkout、cron、systemd user timer 或残留命令提交工程审计 baseline，把 main 推进后令质量报告陈旧。

HZ23：last-known-good round=`20260615_100135`，3304 行，SHA256=`509d5b09bc9843d2e083ecd29fa2cfc83569c4cf877ced7a13d37a1e820d457a`。当前 latest 为 0 行且 `candidate_integrity_ready=false`。只读审计代码已进入 main，但尚未在杭州执行；执行前先把报告发布改为 `runtime-evidence` 或本地-only。

HZ24：queue=221、old linked=72、sold-out=5、old pending=149、expected actionable pending=144。无生产落地证据，继续暂停。

MySQL 初始化、两次回填、dual-write 7 天、publish version 和 AIdeal CPS 商用同步均未执行。

交互规则：中文、职业化、直接、结构化；直接读写 GitHub；长代码和复杂脚本提交 GitHub；用户只执行单一 `.sh` 入口；GitHub 写入后二次确认；日志写文件；不使用 Codex CLI；Shell 不使用 `set -e`；自动测试禁止 JD live；Secret 不进入 GitHub。

编程规范：分层解耦；配置和环境分离；默认值单一来源；正式代码只有一个 main；备份不是代码来源；正式能力必须是通用商用版本；文件超过 300 行、函数超过 80 行、运行入口超过 120 行必须拆分；重复定义和全局 blocker 必须为 0。

第一条回复必须回答：

```text
1. 当前 main commit；
2. quality-reports 是否绑定当前 main；
3. 旧 audit publisher 是否仍在推进 main；
4. 全局和各 scope blocker；
5. Offline Quality 和 jd_live_called；
6. HZ23 只读审计入口是否会写 main；
7. runtime-evidence 是否已经建立；
8. HZ24 是否仍暂停；
9. MySQL 还缺哪些门禁；
10. 准备直接修改哪些 GitHub 文件。
```

随后直接修改 GitHub，不要求我复制旧日志。
