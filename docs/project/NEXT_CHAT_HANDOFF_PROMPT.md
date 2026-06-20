# 新对话无缝启动 Prompt

将下面内容作为新对话第一条消息：

---

你现在继续 **AIdeal CPS / 智省优选——京东联盟佣金商品 Data Lab 商用化项目**。

不要从头设计，不要让我复制旧日志。先直接读取 GitHub，再继续修改。

## 当前唯一优先级

先把代码问题 100% 治理完成，再推进功能：

- 重复函数、类、方法、Shell 函数为 0；
- 重复变量、模块常量、配置键、默认值多源为 0；
- 跨文件重复实现为 0；
- global/full gate blocker 为 0，不只看 active；
- 大文件和长函数为 0；
- 审计和离线报告绑定当前 main。

代码治理完成前，不恢复 HZ24、不初始化 MySQL、不推进 publish 或 AIdeal CPS 同步。

## 交互规则

- 使用中文，职业化、直接、结构化；
- 直接读取和修改 GitHub；
- 代码和复杂命令提交为仓库文件，不在对话打印长脚本；
- 用户只执行仓库内单一 `.sh` 入口；
- 每次写 GitHub 后必须 `fetch_file`、`fetch_commit` 或服务器 `git log` 二次确认；
- 日志写入 `logs/`、`reports/` 或 `docs/debug/`，用户只返回 Summary；
- 不使用 Codex CLI；
- Shell 不使用 `set -e` 或 `|| exit 1`；
- 自动测试不得调用 JD live；
- 账号、密码、Cookie、Profile、Token、私钥和数据库密码不得进入 GitHub。

## 必须读取

Data Lab：`ShanGouXueHui/aideal-cps-data-lab`

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
docs/status/CHAT_ARCHIVE_20260620.md
reports/project_engineering_audit_latest.json
reports/offline_quality_latest.json
reports/hz23_round_latest.json
data/export/aideal_cps_products_commercial_candidate_manifest.json
reports/hz24_tab_overlap_analysis_latest.json
reports/hz24_increment_collection_latest.json
```

AIdeal CPS：`ShanGouXueHui/aideal-cps`

```text
docs/integration/DATA_LAB_INTEGRATION_AUTHORITY.md
docs/integration/DATA_LAB_COMMISSION_PRODUCTS_SIMPLE.md
docs/integration/DATA_LAB_MYSQL_SYNC_V1.md
```

## 环境

```text
杭州 Data Lab 生产：121.41.111.36 / cpsdata
新加坡 CI Bridge：43.106.55.255 / datalab
杭州 AIdeal CPS 生产：8.136.28.6 / deploy
```

杭州是唯一真实 JD、HZ23/HZ24 和 Data Lab MySQL 环境。新加坡只做离线编译、测试、审计和脱敏报告回写。

运维人员从杭州 `cpsdata` SSH 进入新加坡 `datalab`。复杂流程必须先写入 GitHub 脚本。

## 当前事实

HZ23 last-known-good：3304 条，重复 0，hash mismatch 0，successful_probes=2，observation_ready=true。

当前 HZ23 latest 回归为 0 行 candidate，`candidate_integrity_ready=false`，不能用于 MySQL 或商用。

HZ24：队列 221，旧 linked 72，明确 sold-out 5，旧 pending 149，预计可行动 144。没有杭州生产报告证明 5 条迁移和 72/5/144 已落地，因此继续暂停。

最新已提交工程审计：扫描 306 文件，global/full gate blocker=210，active=0，compatibility=0，historical=195，support=15。审计器尚未完整覆盖重复变量、模块常量、配置键和默认值多源。

最新已提交 Offline Quality：66 项 PASS，0 failure，0 error，`jd_live_called=false`，但必须确认是否绑定当前 main。

MySQL 初始化、回填、dual-write、7 天稳定运行、publish version 和 AIdeal CPS 正式同步均未执行，所有开关保持 false。

## 新对话执行顺序

1. 确认当前 main 和报告 HEAD；
2. 补齐重复变量、常量、配置键和默认值多源审计及测试；
3. 清理剩余历史 Shell 和 support blocker；
4. 在新加坡运行 CI Bridge并回写当前 HEAD 报告；
5. 全局代码门禁清零；
6. 杭州只读恢复并核验 HZ23 3304 last-known-good；
7. 验证 HZ23 canonical promotion；
8. 杭州迁移 HZ24 5 条 sold-out 并确认 72/5/144；
9. 221 队列全终态后恢复剩余采集；
10. 冻结候选后初始化 MySQL、回填、dual-write 7 天；
11. publish version；
12. AIdeal CPS dry-run、灰度和正式商用。

## 第一条回复必须回答

```text
最新 main commit；
报告是否绑定 main；
全局和各 scope blocker；
重复函数检测结果；
重复变量/常量/配置键检测是否完整；
0 行 candidate 回归状态；
HZ24 72/5 是否有生产证据；
是否允许恢复 HZ24；
MySQL 还缺哪些门禁；
准备直接修改哪些 GitHub 文件。
```

随后直接修改 GitHub推进代码治理。

---