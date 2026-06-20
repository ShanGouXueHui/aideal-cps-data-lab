# 文档权威顺序（最终版）

更新日期：2026-06-20

## 当前权威顺序

1. 当前 `main` 代码树。
2. 与当前 `main` 精确绑定的权威运行报告。
3. `docs/project/PROJECT_HANDOFF_20260620.md`。
4. `docs/status/COMMERCIALIZATION_STATUS_20260620.md`。
5. `docs/project/CURRENT_PROJECT_CONTEXT.md`。
6. `docs/project/PROJECT_MEMORY_20260620.md`。
7. `docs/project/CODE_CHANGE_GUARDRAILS.md`。
8. `docs/project/CODE_CHANGE_GUARDRAILS_IMPLEMENTATION.md`。
9. `docs/project/EXECUTION_TOPOLOGY.md`。
10. `docs/project/ENVIRONMENT_AND_WORKING_RULES.md`。
11. `docs/status/CHAT_ARCHIVE_20260620_PART2.md`。
12. `docs/project/NEXT_CHAT_HANDOFF_PROMPT_FINAL_20260620.md`。

旧状态文件只作为历史快照。

## 分支职责

- `main`：唯一正式代码主线，只保存代码、配置、合同、测试、文档和非权威指针。
- `quality-reports`：保存 Engineering Audit 与 Offline Quality 权威报告。
- `runtime-evidence`：保存 HZ23、HZ24、MySQL readiness 等脱敏运行证据。

证据分支不是代码主线。运行报告不得提交到 `main`，否则报告提交本身会推进 main 并使原报告立即陈旧。

`runtime-evidence` 的代码迁移尚未完成，不得假定该分支已经可用。

## 报告读取规则

工程质量报告从 `quality-reports` 读取：

```text
reports/project_engineering_audit_latest.json
reports/offline_quality_latest.json
```

运行证据后续统一从 `runtime-evidence` 读取。

放行前必须检查：

- `git_head` 或 `code_git_head` 精确等于当前 main；
- `generated_at`、round_id、schema、checksum 和返回码；
- Offline Quality 为 PASS；
- `jd_live_called=false`；
- global/full 及全部 scope blocker 为 0；
- main 中同名 pointer 不能当作运行结果；
- 陈旧或缺失报告不得放行下一阶段。

## 当前工程状态

已验证代码树：258 个文件，全部 blocker scope 为 0，全部 duplicate category 为 0，大文件和长函数为 0，语法 PASS；Offline Quality 69 项、0 failure、0 error、`jd_live_called=false`。

```text
CODE_GOVERNANCE_LOGIC_COMPLETE=true
CODE_GOVERNANCE_FORMAL_ACCEPTANCE=false
CURRENT_HEAD_VALIDATED=false
```

当前 main 是已验证代码树的后继，只增加了工程审计报告提交，代码没有回退；但严格报告绑定失效。

## 当前最先处理的阻断

1. 在新加坡定位并停止旧 audit publisher。
2. 将运行证据发布迁移到 `runtime-evidence`。
3. 对当前 main 重跑 Full Audit 与 Offline Quality。
4. 确认权威报告绑定 current main，且 main 不再被报告推进。
5. 然后执行杭州 HZ23 3304 只读盘点。
