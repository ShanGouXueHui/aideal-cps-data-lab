# AIdeal CPS Data Lab 当前项目上下文

更新日期：2026-06-27

## 1. 项目边界

Data Lab 负责京东联盟授权浏览器采集、商品与推广资格解析、可信短链、终态维护、质量门禁、版本化发布和未来 Data Lab MySQL。

AIdeal CPS 负责微信/H5、搜索推荐、点击归因、订单和返佣。终端请求只访问 AIdeal CPS 本地 MySQL，不实时依赖 Data Lab 浏览器、远程 MySQL 或 SSH Tunnel。

## 2. 环境角色

```text
杭州 Data Lab：121.41.111.36 / cpsdata
目录：/home/cpsdata/projects/aideal-cps-data-lab

新加坡 CI Bridge：43.106.55.255 / datalab
目录：/home/datalab/projects/aideal-cps-data-lab
SSH 别名：sg-aideal-datalab

杭州 AIdeal CPS：8.136.28.6 / deploy
目录：/home/deploy/projects/aideal-cps
```

杭州是唯一允许真实 JD、HZ23/HZ24 和 Data Lab MySQL 的环境。新加坡只运行离线编译、测试和审计。AIdeal CPS 只消费已发布版本。

杭州到新加坡无密码 SSH 已验证。正确用户是 `datalab`，不是 `cpsdev`；`datalab` 不在 sudoers。

## 3. 报告分支

```text
main              唯一代码、配置、合同、测试、文档主线
quality-reports   工程审计与 Offline Quality
runtime-evidence  HZ23/HZ24/MySQL readiness 脱敏证据
```

运行报告不得写入 main。HZ23 formal supervisor 的状态、rolling progress 和 compact summary 均写入 `runtime-evidence`。

## 4. HZ23 当前状态

当前 observation round：

```text
ROUND_ID=hz23_obs_20260624_093503
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

当前阻断原因：京东验证/风控。页面解析和扫描已可稳定完成到 page 42。

当前正式控制器：

```text
scripts/ops/hz23_formal_supervisor.sh
```

用户查看状态入口：

```text
scripts/ops/hz23_formal_summary.sh
```

生产入口自检：

```text
scripts/ops/check_hz23_formal_entrypoints.sh
```

## 5. 已删除旧入口

以下旧生产入口已经删除，不得恢复、不得兼容、不得建旧分支：

```text
scripts/hz23_observation_daemon.sh
scripts/ops/schedule_hz23_observation_daytime.sh
scripts/ops/schedule_hz23_observation_resume_daytime.sh
scripts/ops/run_hz23_smoke_now.sh
scripts/ops/run_hz23_smoke_now_with_deps.sh
```

旧代码只允许在 `archive/legacy/README.md` 通过历史 commit/blob sha 追溯。

## 6. HZ23 LKG 3304 状态

旧 3304 LKG 恢复路线已关闭。当前磁盘未找到：

```text
round=20260615_100135
candidate_rows=3304
data_sha256=509d5b09bc9843d2e083ecd29fa2cfc83569c4cf877ced7a13d37a1e820d457a
```

不得用 seen/import 文件拼凑旧 3304。下一路线是完成当前 HZ23 observation 1-67，然后重新生成新候选并重跑质量门禁。

## 7. HZ21 / HZ24 / MySQL / 同步

- HZ21 collector 仍是受控 fail-closed：`reason=hz21_collector_not_mainlined`。
- HZ23 observation 完成不等于商用短链采集完成。
- HZ24 队列仍暂停。
- Data Lab MySQL 初始化、两次幂等回填、dual-write 7 天、publish version 和 AIdeal CPS dry-run/灰度/正式同步均未执行。

所有开关保持 false：

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

## 8. 当前严格下一步

1. 观察 formal supervisor 是否从 `paused_for_manual_verification` 进入 `running`。
2. 若仍卡 page 43，人工完成京东验证后等 hourly probe 或执行 formal supervisor restart。
3. 完成 page 1-67 后，只进入 HZ23 candidate quality gate 设计。
4. 在 HZ23 新候选和质量门禁完成前，不启动 HZ24/MySQL/publish/AIdeal CPS sync。

## 9. 新对话入口

下一对话必须先读：

```text
docs/project/PROJECT_MEMORY_20260620.md
docs/handoff/HANDOFF_2026-06-27_HZ23_FORMAL_SUPERVISOR.md
docs/project/HZ23_FORMAL_SUPERVISOR_DESIGN_20260627.md
docs/status/CURRENT_PROGRESS_2026-06-27_HZ23_FORMAL.md
docs/handoff/STARTUP_PROMPT_NEXT_CHAT_2026-06-27_HZ23_FORMAL.md
archive/legacy/README.md
```
