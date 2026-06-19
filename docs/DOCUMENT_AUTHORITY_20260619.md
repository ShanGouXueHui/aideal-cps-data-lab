# DL2 文档权威顺序 — 2026-06-19

## 1. 当前权威顺序

新对话和商用决策按以下顺序读取：

1. `docs/COMMERCIALIZATION_HANDOFF_20260619.md`
2. `docs/PROJECT_MEMORY.md`
3. `docs/CURRENT_PROGRESS_20260619_FINAL.md`
4. `docs/ENGINEERING_COMMERCIAL_RULES_20260619.md`
5. `docs/ENVIRONMENT_OPERATIONS_20260619.md`
6. `docs/DL2_COMMERCIAL_ARCHITECTURE.md`
7. `docs/NEXT_DIALOG_PROMPT_20260619.md`
8. `reports/project_status_20260619_final.json`
9. 最新运行报告、manifest、CI 和代码。

## 2. 冲突处理

- 最新可验证运行报告、manifest、CI 和代码优先于计划文档；
- 本文列出的 2026-06-19 最终文档优先于旧 `CURRENT_PROGRESS*`、旧 handoff 和旧 status；
- HZ23 已完成完整轮次和 3304 候选完整性门禁；旧文档中“H​Z23 尚未完成”的描述只代表当时历史状态；
- 工程审计 blocker 数是动态快照，不得把 390、605 或其他历史数字当长期事实；
- Data Lab MySQL V1 是目标架构，但实际是否初始化、回填、dual-write、publish 必须现场核验；
- JSONL/artifact 和 published MySQL view 都可作为受控交付通道，生产终端请求始终读取 AIdeal CPS 本地 MySQL；
- HZ24 历史 static PASS 不能证明后续重构后的当前 HEAD；
- Secret、密码、Cookie、session、私钥永远以服务器 Secret 为准，不以 GitHub 文档为准。

## 3. 历史文档处理

以下文档保留为历史审计记录，不应单独作为当前商用判断：

- `docs/CURRENT_PROGRESS.md`
- `docs/CURRENT_PROGRESS_V2.md`
- `docs/CONVERSATION_ARCHIVE_2026-06-19.md`
- `docs/SESSION_ARCHIVE_2026-06-19.md`
- `reports/project_status_latest.json`
- `docs/status/MYSQL_PREPARATION_STATUS_20260614.md`
- HZ22/HZ23 各时间点状态报告。

它们记录当时事实，不能覆盖当前最终交接。

## 4. 事实等级

- **已验证事实**：GitHub 代码、commit、报告、manifest、CI 或现场脱敏日志证明；
- **代码已实现但未现场验证**：不得宣称运行成功；
- **设计目标**：不得宣称已部署；
- **风险/假设**：必须附验证方法；
- **商用完成**：必须通过 static、smoke、accounting、validation、dry-run、import、landed validation、rollback 和稳定期全部门禁。
