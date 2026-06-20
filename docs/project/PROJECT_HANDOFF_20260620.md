# AIdeal CPS Data Lab 商用化项目无缝交接

更新日期：2026-06-20

状态：新对话高密度交接入口。不得依赖聊天历史，先读取当前 main、本文、当前状态和权威报告。

## 1. 唯一推进顺序

```text
停止旧报告发布任务并恢复报告权威
→ 正式完成代码治理验收
→ 杭州只读核验 HZ23 last-known-good 3304
→ 验证原子恢复和 canonical promotion
→ 完成 HZ24 终态迁移和剩余采集
→ 冻结最终候选
→ 初始化 Data Lab MySQL
→ 两次幂等回填
→ dual-write 稳定 7 天
→ publish version
→ AIdeal CPS dry-run、灰度和正式商用
```

HZ24、MySQL、publish 和 AIdeal CPS 同步继续禁止。

## 2. 仓库与系统边界

```text
Data Lab：ShanGouXueHui/aideal-cps-data-lab
AIdeal CPS：ShanGouXueHui/aideal-cps
正式代码主线：main
历史快照：history-snapshot-20260620
```

Data Lab 负责京东联盟授权浏览器采集、商品和推广资格解析、可信短链、终态、质量门禁、JSONL/MySQL 权威源和版本化发布。

AIdeal CPS 负责微信/H5、搜索推荐、点击归因、订单和返佣。终端请求只访问 AIdeal CPS 本地 MySQL，不实时依赖 Data Lab 浏览器、远程 MySQL或 SSH Tunnel。

## 3. 环境拓扑

### 杭州 Data Lab 生产

```text
地址：121.41.111.36
用户：cpsdata
目录：/home/cpsdata/projects/aideal-cps-data-lab
```

唯一允许真实 JD、HZ23/HZ24 采集、生产状态写入、Data Lab MySQL、dual-write 和正式发布。

### 新加坡 CI Bridge

```text
地址：43.106.55.255
用户：datalab
目录：/home/datalab/projects/aideal-cps-data-lab
SSH 别名：sg-aideal-datalab
```

只允许 Git 拉取、编译、Offline Quality、Engineering Audit、无 JD live 测试和脱敏报告处理。

正确用户是 `datalab`，不是 `cpsdev`。`datalab` 按设计不在 sudoers。杭州已验证：

```text
ssh -o BatchMode=yes sg-aideal-datalab
USER=datalab
HOST=iZt4n62qkjefjya5xa097pZ
HOME=/home/datalab
```

### 杭州 AIdeal CPS 生产

```text
地址：8.136.28.6
用户：deploy
目录：/home/deploy/projects/aideal-cps
数据库：aideal_cps
```

该环境只消费已发布数据，不承担京东采集。

## 4. 交互规则

- 中文、职业化、直接、结构化；
- 直接读取和修改 GitHub，不要求用户复制旧日志；
- 长代码、复杂脚本和文档直接提交 GitHub；
- 用户只执行仓库内审核过的单一 `.sh` 入口；
- 每次写 GitHub 后必须 `fetch_file`、`fetch_commit` 或服务器 `git log` 二次确认；
- 日志写入 `logs/`、`reports/` 或 `docs/debug/`，终端只输出 Summary；
- 不使用 Codex CLI；
- Shell 不使用 `set -e`；
- 不向用户发送容易截断的超长临时命令；
- 自动测试禁止 JD live；
- Secret、Cookie、Profile、Token、私钥和数据库密码不得进入 GitHub。

## 5. 编程规范

固定分层：

```text
browser/collector       DOM、selector、点击、风险检测
application/service     用例编排、批次、断点、状态机
domain                  SKU、商品、链接、终态规则
persistence/repository  JSONL/MySQL、事务、原子写入
contracts/schema         schema、枚举、跨系统合同
configuration            typed settings、配置加载
ops                       systemd、部署、备份、统一入口
tests                     fixture、单元测试、禁止 JD live
```

强制规则：

- browser、domain、persistence、publish 职责不得混在同一函数；
- selector 只能在浏览器适配层或集中配置；
- 数据库层不得依赖 Playwright/browser 对象；
- Shell/Python 入口必须是薄入口；
- 默认值只能在一个 typed settings/config 入口定义；
- 正式能力必须适用于通用商品、批次和页面，不为单 SKU 或临时 DOM 写死；
- 当前只实现京东，不提前堆叠无实际价值的多平台抽象；
- Python/Shell 单文件超过 300 行必须拆分；
- 单函数超过 80 行必须拆分；
- 运行入口超过 120 行必须收敛；
- 正式代码只有一个 `main`，备份和证据分支不能成为第二代码主线。

## 6. 代码治理结果

已验证代码树：

```text
files_scanned=258
global_blocker_count=0
full_gate_blocker_count=0
active_blocker_count=0
compatibility_blocker_count=0
historical_blocker_count=0
support_blocker_count=0
duplicate_definition_count=0
duplicate_assignment_count=0
duplicate_constant_assignment_count=0
duplicate_config_key_count=0
duplicate_default_source_count=0
duplicate_implementation_count=0
large_file_count=0
long_function_count=0
python_syntax_count=0
shell_syntax_count=0
config_syntax_count=0
```

Offline Quality：

```text
tests_run=69
failure_count=0
error_count=0
jd_live_called=false
status=PASS
```

扫描器已完整覆盖重复函数、变量、常量、配置键、默认值多源和跨文件重复实现。旧文档中的“能力尚未补齐”已失效。

当前必须区分：

```text
CODE_GOVERNANCE_LOGIC_COMPLETE=true
CODE_GOVERNANCE_FORMAL_ACCEPTANCE=false
```

逻辑已经清零；正式验收仍因报告未绑定当前 main 而未闭环。

## 7. 报告发布架构

长期职责：

```text
main              代码、配置、合同、测试、文档和非权威指针
quality-reports   Engineering Audit 与 Offline Quality
runtime-evidence  HZ23/HZ24/MySQL readiness 脱敏证据
```

任何运行报告提交到 `main` 都会推进 main，并让原质量报告立即陈旧。因此：

- CI Bridge 只验证，不发布质量报告；
- Active Audit 只上传 artifact；
- 运行证据必须迁移到 `runtime-evidence`；
- 通用 worktree publisher 不得再把运行报告写入 main。

归档时当前 main 是已验证代码树的直接后继，只修改了工程审计报告文件，代码没有回退；但严格报告绑定失效。

新加坡仍可能存在旧 checkout、cron、systemd user timer 或残留命令，继续执行旧发布逻辑，提交信息为 `reports: update engineering audit baseline`。必须先定位并停止。

## 8. HZ23

历史 last-known-good：

```text
round_id=20260615_100135
candidate_rows=3304
duplicate_sku_count=0
payload_hash_mismatch=0
successful_probes=2
observation_ready=true
data_sha256=509d5b09bc9843d2e083ecd29fa2cfc83569c4cf877ced7a13d37a1e820d457a
```

当前 latest：

```text
round_id=20260620_101332
candidate_rows=0
candidate_integrity_ready=false
observation_ready=false
gate_failures=[candidate_nonempty]
```

0 行 latest 无效，不能用于 MySQL、publish 或商用。

只读审计能力已进入 main：

```text
config/hz23-last-known-good.toml
src/aideal_cps_data_lab/hz23/lkg_settings.py
src/aideal_cps_data_lab/hz23/lkg_candidate_audit.py
src/aideal_cps_data_lab/hz23/lkg_runtime_audit.py
scripts/hz23_readonly_lkg_audit.py
scripts/hz23_run_lkg_readonly_audit.sh
tests/test_hz23_lkg_readonly_audit.py
```

尚未在杭州执行。执行前先改造报告发布，避免审计报告再次推进 main。

## 9. HZ24

```text
membership=250
deduplicated_sku=239
overlap=18
queue=221
old_linked=72
sold_out=5
old_pending=149
expected_actionable_pending=144
```

无杭州生产证据证明 5 条迁移和 72/5/144 已落地，继续暂停。

## 10. MySQL 与 AIdeal CPS

尚未执行：

```text
Data Lab MySQL 初始化
有效候选首次和二次幂等回填
JSONL/MySQL dual-write
dual-write 连续稳定 7 天
publish version
AIdeal CPS dry-run、灰度和正式同步
```

所有写入、发布和同步开关保持 false。

## 11. 下一步

1. 新加坡只读定位旧工程审计发布任务；
2. 停止并禁用旧任务，拉取当前 main；
3. 将运行报告发布迁移到 `runtime-evidence`；
4. 对当前 main 重跑 Full Audit 和 Offline Quality；
5. 确认报告绑定当前 main，且 main 不再被报告推进；
6. 正式关闭代码治理门禁；
7. 杭州执行 HZ23 3304 只读盘点；
8. 若精确 SHA256 匹配，只生成证据，不立即恢复 canonical；
9. 单独验证备份、原子恢复、回滚和 canonical promotion；
10. 再推进 HZ24、MySQL 和商用链。

## 12. 当前门禁

```text
CODE_GOVERNANCE_LOGIC_COMPLETE=true
CODE_GOVERNANCE_FORMAL_ACCEPTANCE=false
CI_BRIDGE_SSH_VALIDATED=true
CI_BRIDGE_RUNTIME_VALIDATED=false
CURRENT_HEAD_VALIDATED=false
STALE_AUDIT_PUBLISHER_STOPPED=false
RUNTIME_EVIDENCE_BRANCH_READY=false
HZ23_LKG_CANDIDATE_CONFIRMED=false
HZ24_RUNTIME_MIGRATION_CONFIRMED=false
HZ24_RESUME_ALLOWED=false
MYSQL_INITIALIZATION_ALLOWED=false
DUAL_WRITE_ALLOWED=false
PUBLISH_ALLOWED=false
AIDEAL_CPS_SYNC_ALLOWED=false
COMMERCIAL_ENABLED=false
```
