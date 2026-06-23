# AIdeal CPS Data Lab 项目记忆与长期约束

更新日期：2026-06-20

## 项目与仓库

- Data Lab：`ShanGouXueHui/aideal-cps-data-lab`。
- AIdeal CPS：`ShanGouXueHui/aideal-cps`。
- 正式代码只有一个 `main`。
- 历史实验只保留在 Git 历史或只读快照。
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
ops                       systemd、部署、备份、验证入口
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

当前扫描器已经完整覆盖重复函数、变量、常量、配置键、默认值多源和跨文件实现。

阈值：Python/Shell 单文件 300 行、函数 80 行、运行入口 120 行。超过阈值必须先拆分。

## 报告架构

- `main`：代码、配置、合同、测试、文档和非权威指针。
- `quality-reports`：Engineering Audit 与 Offline Quality。
- `runtime-evidence`：HZ23、HZ24 和 MySQL readiness 脱敏证据。

运行报告不得提交到 main。CI Bridge 只验证，不承担质量报告发布。

## 配置与 Secret

非敏感共享参数进入版本化配置；环境差异进入环境变量；Secret 进入服务器 Secret。密码、Token、Cookie、Profile、私钥和数据库密码不得进入 GitHub。

## 2026-06-24 HZ23 observation 检查点记忆

### 已确认状态

- HZ23 smoke-now 已通过：`RUN_RC=0`、`PUBLISH_RC=0`、`DEPENDENCY_INSTALL_RC=0`、`DEPENDENCY_VERIFY_RC=0`。
- 已解除的低级问题：`PYTHONPATH` 缺失、`.venv-browser` 缺 `tomli`、旧 PREP/SCAN/COLLECT 报告误读、JSON-only runtime evidence 发布路径。
- 京东风控曾出现 `risk_before` / `risk_after_jump`，人工验证后 page 1 smoke 已恢复正常：`risk=[]`、`has4000=true`、`oneKeyCount=60`、`skuCount=60`。
- HZ21 collector 仍是受控 fail-closed：`reason=hz21_collector_not_mainlined`，因此 HZ23 现阶段只允许 observation scan，不得声明短链采集成功。
- 旧后台进程已清理，仅保留当前有效 observation scheduler。

### 当前有效后台任务

- 服务器：杭州 `cpsdata`，路径 `/home/cpsdata/projects/aideal-cps-data-lab`。
- 当前有效任务：`scripts/ops/schedule_hz23_observation_daytime.sh`。
- PID 文件：`run/hz23_observation_daytime_scheduler.pid`。
- 记录过的有效 PID：`424144`；其子进程 sleep：`424147`。
- 目标时间：`2026-06-24T09:35:00` 杭州服务器本地时间。
- 范围：`PAGE_START=1`、`PAGE_END=67`。
- 自动结果报告：`runtime-evidence:reports/hz23_observation_auto_latest.json`。
- 自动运行摘要：`runtime-evidence:reports/hz23_round_<ROUND_ID>_latest.json` 与 `runtime-evidence:reports/hz23_round_latest.json`。

### 明天/下次续接时优先检查

1. 先读取 `runtime-evidence:reports/hz23_observation_auto_latest.json`，不要先让用户重跑。
2. 判断 `status` 是否仍为 `SCHEDULED`；若仍是 scheduled，再让用户只读检查 PID 和 scheduler log。
3. 若已完成，检查：`run_rc`、`summary.stop_reason`、`summary.stop_page`、`summary.completed_pages`、`summary.unfinished_pages`、`summary.scanned_total`、`summary.collect_unavailable_pages`。
4. 若 `run_rc=0` 且 `unfinished_pages=[]`，说明 HZ23 observation 1-67 完成；下一步只允许做数据质量验证和候选/manifest 检查。
5. 若 `stop_reason=outside_daytime`，用同一 `ROUND_ID`、`HZ23_RESUME=1` 续跑；不要从头覆盖。
6. 若 `stop_reason` 为 `risk_*`、`risk_before`、`risk_after_jump`，先处理京东人工验证/风控冷却，不要继续自动重试。
7. 若 `stop_reason=prep_entry_failed`、`scan_entry_failed`、`collector_report_error`，先读取对应 log_tail 和 page report，不要推断。
8. 若完成但 `collect_unavailable_pages` 覆盖大量页面，这是预期，因为 HZ21 仍未主线化；不得升级为商用发布依据。
9. 禁止继续旧 HZ23 LKG 3304 恢复路线；旧 3304 已判定当前磁盘不可恢复。
10. 在新 HZ23 observation 与候选质量门禁未通过前，仍禁止 HZ24、MySQL 初始化、business publish、AIdeal CPS 同步。

### 严禁事项

- 不得把 runtime evidence 提交到 `main`。
- 不得用 seen/import 文件拼凑旧 3304。
- 不得因 smoke 或 observation 通过就启用 HZ24/MySQL/publish/AIdeal CPS。
- 不得忽略 `collect_unavailable_pages`；短链采集未主线化前，observation 只能证明页面扫描能力。
