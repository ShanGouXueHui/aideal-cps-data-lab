# Next Chat Startup Prompt — AIdeal CPS Data Lab / HZ23 Formal Supervisor

请复制以下 Prompt 到新对话。

---

你现在继续 AIdeal CPS Data Lab / 智省优选 - 京东联盟 HZ23 数据采集项目。

必须使用中文，职业化、直接、结构化。不要从头重新设计。不要使用 Codex CLI。不要在聊天里打印长脚本、长命令、长 JSON 或长日志；长文件直接写 GitHub。用户只执行短入口命令并贴 compact summary。Linux 命令不要使用 `set -e`。

Repo：`ShanGouXueHui/aideal-cps-data-lab`
Branch：`main`
Runtime evidence branch：`runtime-evidence`
杭州生产：`cpsdata@121.41.111.36:/home/cpsdata/projects/aideal-cps-data-lab`
新加坡 CI Bridge：`datalab@43.106.55.255:/home/datalab/projects/aideal-cps-data-lab`
AIdeal CPS 生产：`deploy@8.136.28.6:/home/deploy/projects/aideal-cps`

先读取这些 GitHub 文档，不要凭记忆操作：

1. `docs/project/PROJECT_MEMORY_20260620.md`
2. `docs/handoff/HANDOFF_2026-06-27_HZ23_FORMAL_SUPERVISOR.md`
3. `docs/project/HZ23_FORMAL_SUPERVISOR_DESIGN_20260627.md`
4. `docs/status/CURRENT_PROGRESS_2026-06-27_HZ23_FORMAL.md`
5. `docs/handoff/STARTUP_PROMPT_NEXT_CHAT_2026-06-27_HZ23_FORMAL.md`
6. `archive/legacy/README.md`

当前权威状态：

```text
ROUND_ID=hz23_obs_20260624_093503
PID=465713
ALIVE=true
MODE=paused_for_manual_verification
EXTRA=next_page=43 probe=failed
LAST_COMPLETED_PAGE=42
COMPLETED_COUNT=42
UNFINISHED_FIRST=43
SCANNED_TOTAL=2520
COMPLETE=False
LATEST_RUNTIME_EVIDENCE_HEAD=4b87c74
```

正式 HZ23 生产入口只允许：

```text
scripts/ops/start_hz23_formal_supervisor.sh
scripts/ops/restart_hz23_formal_supervisor.sh
scripts/ops/hz23_formal_supervisor.sh
scripts/ops/hz23_formal_progress_publisher.sh
scripts/ops/hz23_formal_summary.sh
scripts/ops/check_hz23_formal_entrypoints.sh
```

以下旧入口已经从生产路径删除，不得恢复、不得兼容、不得建立旧分支：

```text
scripts/hz23_observation_daemon.sh
scripts/ops/schedule_hz23_observation_daytime.sh
scripts/ops/schedule_hz23_observation_resume_daytime.sh
scripts/ops/run_hz23_smoke_now.sh
scripts/ops/run_hz23_smoke_now_with_deps.sh
```

旧代码只允许通过 `archive/legacy/README.md` 的历史 commit/blob sha 追溯，不允许作为生产执行代码存在。

当前硬门禁仍然关闭：

```text
HZ23_LKG_CANDIDATE_CONFIRMED=false
HZ24_RUNTIME_MIGRATION_CONFIRMED=false
HZ24_RESUME_ALLOWED=false
MYSQL_INITIALIZATION_ALLOWED=false
DUAL_WRITE_ALLOWED=false
PUBLISH_ALLOWED=false
AIDEAL_CPS_SYNC_ALLOWED=false
COMMERCIAL_ENABLED=false
```

当前任务：继续推进 HZ23 observation page 43-67，直到 page 1-67 完整完成。不要启动 HZ24，不要初始化 MySQL，不要 dual-write，不要 publish，不要同步 AIdeal CPS。

优先从 GitHub/runtime-evidence 查看状态。用户查看 compact summary 的短命令是：

```bash
cd /home/cpsdata/projects/aideal-cps-data-lab && git fetch origin main runtime-evidence && git reset --hard origin/main && bash scripts/ops/hz23_formal_summary.sh
```

如果需要验证生产入口是否干净：

```bash
cd /home/cpsdata/projects/aideal-cps-data-lab && git fetch origin main && git reset --hard origin/main && bash scripts/ops/check_hz23_formal_entrypoints.sh
```

如果人工完成 JD 验证并希望立刻触发探测/续跑：

```bash
cd /home/cpsdata/projects/aideal-cps-data-lab && git fetch origin main runtime-evidence && git reset --hard origin/main && bash scripts/ops/restart_hz23_formal_supervisor.sh
```

判断规则：

- `MODE=paused_for_manual_verification` 且 `UNFINISHED_FIRST=43`：仍等 JD 人工验证或下一次白天 hourly probe。
- `MODE=running`：正在自动续跑，不要启动第二个任务。
- `COMPLETE=True`：先确认 runtime-evidence summary 的 `unfinished_pages=[]`，然后才进入 HZ23 candidate quality gate 设计。
- 出现 `risk_after_jump` / `risk_handler` / `京东验证`：不要绕验证，不要多账号/多浏览器规避；人工验证后由 supervisor 继续。

工程要求：分层解耦、配置分离、唯一主线、无旧代码路径、无重复函数/变量/默认值、薄入口、长逻辑后续迁移到 typed Python service。用户不希望聊天超时；任何长文档、长脚本、长日志都直接写 GitHub。

下一步优先动作：读取 compact summary 或 runtime-evidence 最新文件，判断 formal supervisor 是否仍 paused、running 或 complete，然后按上述规则推进。
