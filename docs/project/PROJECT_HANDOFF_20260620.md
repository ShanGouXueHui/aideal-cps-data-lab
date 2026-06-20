# AIdeal CPS Data Lab 商用化项目无缝交接

更新日期：2026-06-20

状态：本文件是本轮长对话的高密度交接入口。新对话不依赖聊天历史，必须从当前 `main`、权威文档和绑定当前 HEAD 的报告恢复上下文。

## 1. 当前唯一执行顺序

```text
先完成代码治理
→ 再恢复并验证 HZ23 last-known-good
→ 再完成 HZ24 终态迁移和剩余采集
→ 再冻结最终候选
→ 再初始化 Data Lab MySQL
→ 再做两次幂等回填和 dual-write 7 天
→ 再生成 publish version
→ 再接入 AIdeal CPS 商用
```

代码治理未完成前，禁止恢复 HZ24、初始化 MySQL、开启 dual-write、publish 或 AIdeal CPS 正式同步。

## 2. 仓库与系统边界

```text
Data Lab：ShanGouXueHui/aideal-cps-data-lab
AIdeal CPS：ShanGouXueHui/aideal-cps
正式主线：main
历史快照：history-snapshot-20260620
```

Data Lab 负责京东联盟授权浏览器采集、商品和推广资格解析、可信短链、终态、质量门禁、JSONL/MySQL 权威源数据和版本化发布。

AIdeal CPS 负责微信/H5、搜索推荐、点击归因、订单和返佣。用户请求只访问 AIdeal CPS 本地 MySQL，不实时依赖 Data Lab 浏览器、远程 MySQL 或 SSH Tunnel。

正式代码只有 `main` 一个主流分支。历史实验只能留在 Git 历史或只读快照分支，不得与正式实现同时保留在 main 的可执行路径。

## 3. 环境拓扑

### 3.1 杭州 Data Lab 生产

```text
服务器：Ubuntu-datacollection
公网 IP：121.41.111.36
用户：cpsdata
项目目录：/home/cpsdata/projects/aideal-cps-data-lab
规格：2 核 / 4 GiB / 50 GiB
```

唯一允许执行：

- 真实 JD 登录和浏览器 Profile；
- HZ23/HZ24 真实采集；
- linked/unavailable/pending 生产状态写入；
- Data Lab MySQL 初始化、回填、dual-write 和发布；
- 生产 systemd、Chrome/CDP、X11/noVNC。

### 3.2 新加坡 CI Bridge

```text
服务器：Ubuntu-Oris-OpenClaw
公网 IP：43.106.55.255
用户：datalab
项目目录：/home/datalab/projects/aideal-cps-data-lab
规格：2 核 / 2 GiB / 40 GiB
```

只允许：Git 拉取、Python/Shell 编译检查、Offline Quality、Engineering Audit、无 JD live 单元测试和脱敏报告回写。

禁止保存或运行：JD Cookie/Profile、真实采集、生产 JSONL、生产数据库、MySQL 写入、publish 和商用同步。

新加坡原有 `cpsdev` 属于其他项目；Data Lab 必须使用隔离用户 `datalab`，独立 HOME、仓库、虚拟环境和 SSH Key。

### 3.3 杭州 AIdeal CPS 生产

```text
公网 IP：8.136.28.6
用户：deploy
项目目录：/home/deploy/projects/aideal-cps
MySQL：aideal_cps
```

该环境是消费端生产，不承担京东联盟浏览器采集。

### 3.4 统一操作入口

```text
运维人员登录杭州 Data Lab：121.41.111.36 / cpsdata
        ↓ SSH
进入新加坡 CI Bridge：43.106.55.255 / datalab
```

SSH 只减少人工切换，不改变角色边界，也不用于复制 Cookie、Profile、生产 JSONL、数据库备份、Token、私钥或数据库密码。代码与报告仍通过 GitHub 交接。

## 4. 固定交付链

```text
ChatGPT 直接修改 GitHub
→ 用户从杭州 cpsdata SSH 到新加坡 datalab
→ 新加坡拉取当前 main
→ 执行单一仓库脚本
→ 编译、Offline Quality、Engineering Audit
→ 脱敏报告回写 GitHub
→ 助手从 GitHub读取报告并继续修代码
→ 全局门禁清零后杭州拉取已验证 commit
→ 杭州执行真实生产动作
```

复杂操作必须先上传为仓库 `.sh` 入口；不再在聊天中交付大量零散命令。

## 5. 交互与执行习惯

- 使用中文，职业化、直接、结构化；
- 优先直接读取、修改和确认 GitHub，不依赖聊天短期上下文；
- 代码、长脚本和复杂命令直接提交 GitHub；
- 每次写 GitHub 后必须 `fetch_file`、`fetch_commit` 或服务器 `git log` 二次确认；
- 用户只执行仓库内经过审核的单一 `.sh` 入口；
- 日志写入 `logs/`、`reports/` 或 `docs/debug/`，终端只输出紧凑 Summary；
- 助手直接从 GitHub读取报告，不要求用户重复复制旧日志；
- 不使用 Codex CLI；
- Shell 不使用 `set -e`，也不使用会退出登录 Shell 的 `|| exit 1`；
- 自动测试不得调用 JD live；
- 真实 JD 登录可人工完成，但账号密码不得进入脚本、日志或 GitHub；
- Secret、Cookie、Profile、Token、私钥和数据库密码不得提交。

## 6. 编程与架构规范

固定分层：

```text
browser/collector       DOM、selector、点击、风控
application/service     用例编排、批次、断点、状态机
domain                  SKU、商品、推广链接、终态规则
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
- 正式能力必须适用于通用商品、批次和页面，不为单 SKU、单次 DOM 或临时故障写死；
- 当前只实现京东，不提前堆叠无实际价值的多平台抽象；
- Python/Shell 单文件超过 300 行必须拆分；
- 单函数超过 80 行必须拆分；
- 运行入口超过 120 行必须收敛。

## 7. 代码治理验收口径

用户明确要求先把代码问题 100% 改完，尤其是重复定义函数、变量和配置。正式验收必须同时满足：

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

必须覆盖：

- Python 同作用域函数、异步函数、类和方法重复定义；
- Shell 函数重复定义；
- Python/Shell 同作用域变量、常量、状态常量和配置赋值的静默覆盖；
- TOML/YAML/INI/JSON 重复键；
- 默认值在多个配置来源重复定义；
- 跨文件业务实现复制；
- 硬编码 IP、URL、端口、路径、selector、Tab、等待时间和阈值；
- 大文件、长函数和多职责入口。

合法运行时状态更新不得误判为重复赋值；审计规则必须有测试和精确允许条件，不能通过路径级豁免、降低 severity 或只看 active scope 伪造通过。

当前扫描器已覆盖重复函数/类/方法、Shell 函数和跨文件函数指纹，但对重复变量、模块常量、配置键和默认值多源检测仍不完整。该能力补齐并取得零结果前，不能宣称代码治理完成。

## 8. 当前工程与测试状态

最新已提交工程审计报告：

```text
files_scanned=306
status=FAIL
global/full gate blocker=210
active blocker=0
compatibility blocker=0
historical blocker=195
support blocker=15
```

当前 blocker 主要是 main 中剩余 HZ12-HZ21 历史 Shell 的硬编码，以及少量 support fixture。报告本身已落后于当前 main，必须在新加坡对当前 HEAD 重跑。

最新已提交 Offline Quality 报告：

```text
status=PASS
tests_run=66
failures=0
errors=0
jd_live_called=false
git_head=2bf6842a60205eb32916bbad5b193f26fbb9ffde
```

该报告只能证明上述 commit，不能自动代表当前 main。CI Bridge 首次服务器实跑尚未完成。

## 9. HZ23 当前状态

最后一次已验证 last-known-good：

```text
round_id=20260615_100135
completed_pages=1..67
candidate_rows=3304
duplicate_sku_count=0
payload_hash_mismatch=0
successful_probes=2
observation_ready=true
```

当前 latest 回归：

```text
round_id=20260620_101332
completed_pages=1..67
scanned_total=4017
last_known_sku_count=3858
successful_probes=4
candidate row_count=0
candidate_integrity_ready=false
observation_ready=false
gate_failures=[candidate_nonempty]
```

3304 条是历史 last-known-good，不是当前 latest。当前 0 行 manifest 无效，不能用于 MySQL、publish 或商用。

代码已加入空首选来源回退、无效 finalize 不晋级、观测门禁和 last-known-good 保护；但代码治理完成后仍必须在杭州生产机只读核验 3304 JSONL、manifest、备份、checksum、实际 systemd/cron commit 和 finalize 入口，并排除旁路覆盖 canonical 的可能。

## 10. HZ24 当前状态

```text
专题 membership=250
去重后 SKU=239
与已验证候选/可信链接重叠=18
真实增量队列=221
旧 linked=72
明确 sold-out=5
旧 pending=149
预计可行动 pending=144
```

HZ24 v2 离线代码和测试已覆盖 linked/unavailable/pending、sold-out、幂等 upsert、原子迁移和回滚、72/5/144 核算、linked hash、恢复授权和报告白名单。

但 GitHub 没有杭州生产报告证明：5 条 sold-out 已迁移、72 条 linked 完整且 hash 未变、pending=144、resume_gate=true、collection_authorization=true。

因此 HZ24 继续暂停，不得启动旧采集器。

## 11. MySQL 和 AIdeal CPS 当前状态

Data Lab 目标数据库：

```text
aideal_cps_data_lab
commission_products
commission_refresh_runs
commission_product_history
commission_publish_versions
v_published_commission_products
```

设计和部分离线代码已准备，但尚未执行：

```text
Data Lab MySQL 初始化
有效候选回填
二次幂等回填
JSONL/MySQL dual-write
dual-write 连续 7 天稳定运行
publish version
AIdeal CPS dry-run、灰度和正式同步
```

所有写入、发布和同步开关保持 false。

## 12. 本轮已完成

- 建立杭州 Data Lab、新加坡 CI Bridge、杭州 AIdeal CPS 三环境权威拓扑；
- 建立新加坡隔离用户 `datalab` 和独立仓库；
- 明确从杭州 `cpsdata` SSH 进入新加坡 `datalab` 的统一运维入口；
- 删除把新加坡误当生产或远程生产 worker 的错误方案；
- 建立 `history-snapshot-20260620`；
- 从 main 移除部分 HZ11-HZ21 历史 Python 实现；
- 将工程门禁从 active/compatibility 扩大为 full/global blocker；
- HZ24 恢复门禁要求全局 blocker 为 0；
- 修复 MySQL batch repository 测试对已删除私有方法的旧引用；
- 建立 HZ24 v2 终态、sold-out 迁移、原子回滚、恢复授权和脱敏报告链；
- 增加 HZ23 无效 finalize 不覆盖 canonical、观测就绪才可晋级和 last-known-good 保护；
- 建立 CI Bridge 代码和报告陈旧性保护；
- 建立项目记忆、环境规则、当前状态和新对话 handoff 文档。

## 13. 尚未完成的原始任务与本轮遗留

严格顺序：

1. 读取当前 main 和最新报告，确认报告是否绑定当前 HEAD；
2. 给审计器补齐 Python/Shell 重复变量、模块常量、配置赋值、配置键和默认值多源检测；
3. 为新增审计规则补测试，精确区分合法运行时状态更新；
4. 清理 main 剩余 HZ12-HZ21 历史 Shell blocker；
5. 收口 support fixture 和配置默认值；
6. 在新加坡首次运行统一 CI Bridge，对当前 main 生成并回写报告；
7. 全局 blocker、重复定义、重复赋值、重复实现、大文件和长函数全部为 0；
8. 杭州只读恢复并核验 HZ23 3304 last-known-good；
9. 验证 HZ23 临时生成、门禁检查、原子晋级和 canonical 保护；
10. 杭州执行 HZ24 5 条 sold-out 迁移并确认 72/5/144；
11. 221 队列全终态后恢复剩余可行动采集；
12. 冻结最终候选；
13. 初始化 Data Lab MySQL并完成首次和二次幂等回填；
14. dual-write 连续稳定 7 天；
15. 生成 publish version；
16. AIdeal CPS dry-run、灰度和正式商用。

## 14. 当前门禁

```text
CODE_CLEANUP_COMPLETE=false
CI_BRIDGE_RUNTIME_VALIDATED=false
CURRENT_HEAD_VALIDATED=false
HZ23_LKG_CANDIDATE_CONFIRMED=false
HZ24_RUNTIME_MIGRATION_CONFIRMED=false
HZ24_RESUME_ALLOWED=false
MYSQL_INITIALIZATION_ALLOWED=false
DUAL_WRITE_ALLOWED=false
PUBLISH_ALLOWED=false
AIDEAL_CPS_SYNC_ALLOWED=false
COMMERCIAL_ENABLED=false
```

## 15. 新对话恢复方式

先读取：

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
docs/project/NEXT_CHAT_HANDOFF_PROMPT.md
reports/project_engineering_audit_latest.json
reports/offline_quality_latest.json
reports/hz23_round_latest.json
data/export/aideal_cps_products_commercial_candidate_manifest.json
reports/hz24_tab_overlap_analysis_latest.json
reports/hz24_increment_collection_latest.json
```

然后只继续代码治理，不要求用户复制旧日志。