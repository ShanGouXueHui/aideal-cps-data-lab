# AIdeal CPS Data Lab 项目记忆与长期约束

更新日期：2026-06-27

## 项目与仓库

- Data Lab：`ShanGouXueHui/aideal-cps-data-lab`。
- AIdeal CPS：`ShanGouXueHui/aideal-cps`。
- 正式代码只有一个 `main`。
- 历史实验只保留在 Git 历史或 archive 说明，不得保留为生产可执行入口。
- 证据分支不是第二代码主线。

Data Lab 负责京东联盟授权采集、商品和推广资格、可信短链、终态、质量门禁、源数据和版本化发布。AIdeal CPS 负责终端用户、搜索推荐、归因、订单和返佣。

## 环境角色

- 杭州 `cpsdata`：唯一 Data Lab 生产环境，允许真实 JD、HZ23/HZ24、生产状态和未来 Data Lab MySQL。
- 新加坡 `datalab`：离线验证节点，只运行编译、Offline Quality、Engineering Audit 和无 JD live 测试。
- 杭州 `deploy`：AIdeal CPS 生产，只消费已发布数据。

杭州到新加坡统一使用 SSH 别名 `sg-aideal-datalab`。正确用户是 `datalab`，不是 `cpsdev`。`datalab` 不在 sudoers。

## 数据与模型边界

- Data Lab 是佣金商品源数据权威；SKU 是唯一业务键。
- 金额使用 Decimal/DECIMAL，写入幂等、事务化并保留 lineage。
- unavailable 不进入 published。
- 用户请求只读取 AIdeal CPS 本地 MySQL。
- JSONL 永久保留为回填、快照、审计和灾备格式。
- 价格、佣金、推广链接和状态判断不得依赖大模型。
- AI 推荐字段与 Data Lab 源字段分离。

## 固定分层

```text
browser/collector       DOM、selector、点击、风险检测
application/service     用例编排、批次、断点、状态机
domain                  SKU、商品、链接、终态规则
persistence/repository  JSONL/MySQL、事务、原子写入
contracts/schema         schema、枚举、跨系统合同
configuration            typed settings、配置加载
ops                       supervisor、systemd、部署、备份、验证入口
tests                     fixture、单元测试、禁止 JD live
```

- selector 只能位于浏览器适配层或集中配置。
- 数据库层不得依赖浏览器对象。
- Shell/Python 入口必须是薄入口。
- 默认值只能有一个 typed settings/config 来源。
- 正式能力必须适用于通用商品、批次和页面，不能为单 SKU 或临时 DOM 写死。
- 当前只实现京东，不提前堆叠无业务价值的多平台抽象。

## 工程硬门禁

```text
global/full 及全部 scope blocker=0
duplicate definition/assignment/constant/config/default/implementation=0
large file=0
long function=0
python/shell/config syntax=PASS
offline quality=PASS
jd_live_called=false
report git_head=current main
```

阈值：Python/Shell 单文件 300 行、函数 80 行、运行入口 120 行。超过阈值必须先拆分。

## 报告架构

- `main`：代码、配置、合同、测试、文档和非权威指针。
- `quality-reports`：Engineering Audit 与 Offline Quality。
- `runtime-evidence`：HZ23、HZ24 和 MySQL readiness 脱敏证据。

运行报告不得提交到 main。CI Bridge 只验证，不承担质量报告发布。

## 配置与 Secret

非敏感共享参数进入版本化配置；环境差异进入环境变量；Secret 进入服务器 Secret。密码、Token、Cookie、Profile、私钥和数据库密码不得进入 GitHub。

## 2026-06-27 HZ23 formal supervisor 记忆

### 当前权威状态

- 当前 HZ23 observation round：`hz23_obs_20260624_093503`。
- 当前已完成：page 1-42。
- 当前第一未完成页：page 43。
- 当前 scanned_total：2520。
- 当前状态：`MODE=paused_for_manual_verification`，`EXTRA=next_page=43 probe=failed`。
- 当前正式控制器：`scripts/ops/hz23_formal_supervisor.sh`。
- 当前 PID 文件：`run/hz23_formal_supervisor.pid`。
- 当前 compact summary：`runtime-evidence:reports/hz23_formal_summary_latest.json`。
- 当前 supervisor status：`runtime-evidence:reports/hz23_formal_supervisor_status_latest.json`。
- 当前 rolling progress：`runtime-evidence:reports/hz23_formal_progress_latest.json`。
- 当前 resume report：`runtime-evidence:reports/hz23_observation_resume_auto_latest.json`。

### 正式 HZ23 生产入口

只允许以下入口存在并被使用：

```text
scripts/ops/start_hz23_formal_supervisor.sh
scripts/ops/restart_hz23_formal_supervisor.sh
scripts/ops/hz23_formal_supervisor.sh
scripts/ops/hz23_formal_progress_publisher.sh
scripts/ops/hz23_formal_summary.sh
scripts/ops/check_hz23_formal_entrypoints.sh
```

### 已删除的旧生产入口

以下文件已从生产路径删除，不得恢复到 `scripts/` 或 `scripts/ops/`：

```text
scripts/hz23_observation_daemon.sh
scripts/ops/schedule_hz23_observation_daytime.sh
scripts/ops/schedule_hz23_observation_resume_daytime.sh
scripts/ops/run_hz23_smoke_now.sh
scripts/ops/run_hz23_smoke_now_with_deps.sh
```

旧代码只允许通过 `archive/legacy/README.md` 的历史 commit/blob sha 追溯，不得作为兼容分支或备用入口保留。

### Formal supervisor 行为

- 单实例：`flock` + PID 文件。
- 启动/重启时强制清理旧 daemon、旧 scheduler、旧 smoke、前台 HZ23 mainline/prepare/scan/hz21_run。
- 只从 runtime-evidence 的 current summary 计算 first unfinished page。
- 若探测通过，则自动从 first unfinished page resume。
- 若检测到 JD 验证/风控，则暂停；白天每 1 小时轻量探测一次，夜间每 3 小时心跳但不碰 JD 页面。
- 不做自动验证码破解、不做多账号/多浏览器规避验证。
- 运行中滚动上传 latest-only progress，不无限增长。
- 完整运行结果上传 runtime-evidence，不写 main。

### 用户交互规则

- 中文、职业化、直接、结构化。
- 不使用 Codex CLI。
- Linux 命令不要使用 `set -e`。
- 聊天里不要打印长命令、长日志、长 JSON；长脚本和长文档直接写 GitHub。
- 用户只执行短入口命令并贴 summary。
- 日志和证据从 GitHub/runtime-evidence 查；用户可只发 `RUNTIME_EVIDENCE_HEAD` 或 compact summary。
- 不要让用户贴 120 行以上日志。
- 不要重复问已经给出的仓库、分支、路径和 round_id。

### 当前硬门禁仍然关闭

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

未完成 page 1-67 前，禁止 HZ24、MySQL 初始化、dual-write、publish、AIdeal CPS 同步。

### 下次续接时优先检查

1. 先读取 `runtime-evidence:reports/hz23_formal_summary_latest.json`，不要先让用户重跑。
2. 若 summary 不够，再读 `runtime-evidence:reports/hz23_formal_supervisor_status_latest.json` 和 `runtime-evidence:reports/hz23_formal_progress_latest.json`。
3. 若 `MODE=paused_for_manual_verification` 且 `UNFINISHED_FIRST=43`，说明仍等人工验证或下一次定时探测。
4. 若 `MODE=running`，说明正在自动续跑；不要启动第二个任务。
5. 若 `COMPLETE=True` 或 `commercial_segment_complete=true` 且 `unfinished_pages=[]`，才进入下一阶段候选质量门禁。
6. 若 `risk_after_jump` / `risk_handler` / `京东验证` 出现，不要规避验证；人工验证后由 supervisor 自动续跑或重启 supervisor 触发立即探测。
7. 若入口自检需要确认，运行 `bash scripts/ops/check_hz23_formal_entrypoints.sh`，目标 `CHECK_RC=0`。
8. HZ21 collector 仍未主线化，`collect_unavailable_pages` 大量存在是预期；observation scan 仍不等于短链采集成功。

### 严禁事项

- 不得把 runtime evidence 提交到 `main`。
- 不得恢复已删除旧入口。
- 不得保留兼容旧路径、旧分支、旧 scheduler。
- 不得多账号/多浏览器并发规避 JD 验证。
- 不得做验证码自动破解。
- 不得用 seen/import 文件拼凑旧 3304。
- 不得因 smoke 或 observation 部分成功就启用 HZ24/MySQL/publish/AIdeal CPS。
- 不得忽略 `collect_unavailable_pages`；短链采集未主线化前，observation 只能证明页面扫描能力。
