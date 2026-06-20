# 对话归档与未完成事项 — 2026-06-20

状态：本文件归档本轮长对话中的设计决策、环境校正、已完成事项、被否决方案和未完成任务。新对话不得依赖聊天历史，必须从 GitHub 当前 main、权威文档和绑定当前 HEAD 的报告恢复上下文。

## 1. 本轮核心结论

唯一执行顺序：

```text
先完成代码治理
→ 再恢复和验证 HZ23 last-known-good
→ 再完成 HZ24 终态迁移与剩余采集
→ 再初始化 Data Lab MySQL
→ 再 dual-write 7 天
→ 再发布版本并接入 AIdeal CPS
```

代码治理未完成前，禁止通过“先跑起来再改”“只看 active blocker”“降低严重度”“扩大排除目录”或恢复旧采集器推进功能。

## 2. 环境角色最终校正

### 杭州 Data Lab 生产

```text
服务器：Ubuntu-datacollection
公网 IP：121.41.111.36
用户：cpsdata
目录：/home/cpsdata/projects/aideal-cps-data-lab
```

唯一允许真实 JD 登录、浏览器 Profile、HZ23/HZ24、生产 linked/unavailable/pending、Data Lab MySQL、dual-write 和发布。

### 新加坡 CI Bridge

```text
服务器：Ubuntu-Oris-OpenClaw
公网 IP：43.106.55.255
用户：datalab
目录：/home/datalab/projects/aideal-cps-data-lab
```

仅替代 GitHub Actions 执行离线编译、测试、全量工程审计和脱敏报告回写。不得保存或运行 JD Cookie/Profile、真实采集、生产 JSONL、生产数据库和商用同步。

新加坡原有 `cpsdev` 属于其他项目；Data Lab 使用隔离用户 `datalab`，独立 HOME、仓库、虚拟环境和 SSH Key。

### 杭州 AIdeal CPS 生产

```text
公网 IP：8.136.28.6
用户：deploy
目录：/home/deploy/projects/aideal-cps
```

该环境是消费端生产，不承担 JD 浏览器采集。

### 统一操作入口

运维人员可以只登录杭州 `cpsdata`，再 SSH 进入新加坡 `datalab`：

```text
121.41.111.36 / cpsdata
        ↓ SSH
43.106.55.255 / datalab
```

SSH 只用于减少人工切换和进入新加坡 Shell。代码和报告仍通过 GitHub 交接；不得通过该链路复制 Cookie、Profile、生产 JSONL、数据库备份、Token、私钥或数据库密码。

## 3. 被否决和已纠正的方案

以下方案不得恢复：

1. 把新加坡视为 Data Lab 生产或灾备采集节点；
2. 把杭州 AIdeal CPS 生产 `8.136.28.6/deploy` 与杭州 Data Lab 生产混为一台机器；
3. 让新加坡反向控制杭州生产服务；
4. 让杭州本机代替新加坡执行 CI Bridge；
5. 将杭州到新加坡 SSH 当作生产数据同步链路；
6. 在聊天中交付大量零散命令；
7. 依赖陈旧 GitHub Actions 报告放行当前 main；
8. 在 full/global blocker 未清零时只依据 active blocker=0 推进功能；
9. 用测试 fixture 豁免、降低 severity 或扩大 excluded directories 伪造审计通过；
10. 在 main 同时保留多个历史实验版本作为可执行实现。

此前方向错误的杭州到新加坡“远程生产 worker/controller”已从 main 删除。环境角色以 `EXECUTION_TOPOLOGY.md` 为准。

## 4. GitHub、分支和交互约束

```text
Data Lab 仓库：ShanGouXueHui/aideal-cps-data-lab
AIdeal CPS 仓库：ShanGouXueHui/aideal-cps
正式主线：main
历史快照：history-snapshot-20260620
```

固定规则：

- 正式商用版本只有 `main` 一个主流分支；
- 历史实验保留在 Git 历史或只读快照分支，不留在 main 执行路径；
- 助手直接修改 GitHub，长代码和复杂脚本不打印到聊天；
- 每次 GitHub 写入后必须 `fetch_file`、`fetch_commit` 或服务器 `git log` 二次确认；
- 用户只执行仓库中的单一 `.sh` 入口；
- 日志和详细报告进入 `logs/`、`reports/` 或 `docs/debug/`；
- 用户只返回紧凑 Summary，助手从 GitHub读取详细报告；
- 不使用 Codex CLI；
- Shell 不使用 `set -e`，也不使用会退出登录 Shell 的 `|| exit 1`；
- 自动测试不得调用 JD live；
- Secret、账号、密码、Cookie、Profile、Token、私钥和数据库密码不得进入 GitHub。

## 5. 代码治理口径

用户明确要求先把代码问题 100% 改完，尤其是重复定义函数和变量。正式验收必须同时满足：

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

- Python 同作用域函数、类、方法重复定义；
- Shell 函数重复定义；
- Python/Shell 同作用域变量、常量和配置赋值的静默覆盖；
- TOML/YAML/INI/JSON 配置键重复；
- 默认值在多个配置来源重复定义；
- 跨文件业务实现复制；
- 硬编码 IP、URL、端口、路径、selector、Tab、等待时间和阈值；
- Python/Shell 单文件超过 300 行；
- 函数超过 80 行；
- 入口超过 120 行。

不得把合法运行时状态更新误判为重复赋值；审计规则必须有测试和明确允许列表，不能靠路径级豁免绕过。

## 6. 分层与通用商用版本

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

规范：

- browser、domain、persistence、publish 职责不得混在同一函数；
- Shell/Python 入口必须薄，只做参数解析、调用服务和输出 Summary；
- selector 只在浏览器适配层或集中配置；
- 数据库层不得依赖 Playwright/browser 对象；
- 非敏感环境差异进入配置或环境变量；
- 默认值只有一个 typed settings 来源；
- 正式能力必须适用于通用商品、批次和页面，不为单 SKU、单次 DOM 或临时故障写死；
- 当前只实现京东，不提前加入无实际需求的多平台抽象。

## 7. HZ23 当前状态

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

当前 latest 轮次：

```text
round_id=20260620_101332
completed_pages=1..67
commercial_segment_complete=true
scanned_total=4017
last_known_sku_count=3858
successful_probes=4
```

当前 latest candidate manifest 回归为：

```text
row_count=0
eligible_sku_count=0
trusted_dedup_sku_count=0
candidate_integrity_ready=false
observation_ready=false
gate_failures=[candidate_nonempty]
```

结论：3304 条是历史 last-known-good，当前 0 行 latest 无效。代码治理完成后必须在杭州生产机只读核验 3304 JSONL、manifest、备份、checksum、实际 systemd/cron commit 和 finalize 入口。不得用当前 0 行 latest 初始化 MySQL或发布。

代码层已引入空首选来源回退、无效 finalize 不晋级、观测门禁和 canonical/last-known-good 保护，但仍需在当前 main 完整审计和服务器实跑后确认。

## 8. HZ24 当前状态

```text
专题 membership=250
专题去重后 SKU=239
与已验证候选/可信链接重叠=18
真实增量队列=221
旧 linked=72
明确 sold-out/card-disabled=5
旧 pending=149
预计可行动 pending=144
```

HZ24 v2 离线代码和测试已覆盖 linked/unavailable/pending、sold-out、幂等 upsert、原子迁移与回滚、72/5/144 核算、linked hash、恢复授权和脱敏报告白名单。

但目前没有杭州生产报告证明：

```text
5 条 sold-out 已迁移到 unavailable
72 条 linked 完整且 hash 未变
pending=144
resume_gate=true
collection_authorization=true
```

因此 HZ24 继续暂停，不得启动旧采集器。

## 9. MySQL 和 AIdeal CPS 尚未完成

Data Lab 目标数据库：

```text
aideal_cps_data_lab
commission_products
commission_refresh_runs
commission_product_history
commission_publish_versions
v_published_commission_products
```

尚未执行：

```text
Data Lab MySQL 初始化
有效候选回填
二次幂等回填
JSONL/MySQL dual-write
dual-write 连续 7 天稳定运行
publish version
AIdeal CPS dry-run、灰度和正式同步
```

所有写入、发布和同步开关保持 false。MySQL 初始化必须等待代码治理、当前 HEAD 离线验证、HZ23 last-known-good 恢复、HZ24 全终态和最终候选冻结。

## 10. 本轮已经完成

- 建立杭州 Data Lab、新加坡 CI Bridge、杭州 AIdeal CPS 三环境权威拓扑；
- 建立新加坡隔离用户 `datalab` 并独立克隆仓库；
- 明确杭州 `cpsdata` 可作为统一登录入口 SSH 到新加坡 `datalab`；
- 删除方向错误的远程生产控制脚本；
- 建立 `history-snapshot-20260620` 保存历史实验；
- 从 main 移除部分 HZ11-HZ21 历史 Python 实现；
- 将工程门禁从 active/compatibility 扩大为 full/global blocker；
- HZ24 恢复门禁要求全局 blocker 为 0；
- 修复 MySQL batch repository 测试对已删除私有方法的旧引用；
- 曾取得一次离线测试 58 项全绿，之后测试扩展到 63 项；
- 增加 HZ23 无效 finalize 不覆盖 last-known-good 的保护；
- 增加 HZ23 观测就绪才可晋级的策略；
- 建立项目记忆、当前上下文、2026-06-20 状态和新对话 handoff 文档。

## 11. 尚未完成和下一步

严格顺序：

1. 读取当前 main 和最新报告，确认报告是否绑定当前 HEAD；
2. 给审计器增加 Python/Shell 重复变量、模块常量、配置赋值、配置键和默认值多源检测；
3. 为新增审计规则补单元测试，处理合法运行时赋值；
4. 清理 main 剩余 HZ12-HZ21 历史 Shell blocker；
5. 收口 support 测试 fixture 和配置默认值；
6. 首次在新加坡运行统一 CI Bridge，对当前 main 生成新报告并回写 GitHub；
7. 全局 blocker、重复定义、重复赋值、重复实现、大文件和长函数全部为 0；
8. 杭州只读恢复并核验 HZ23 3304 last-known-good；
9. 修复并验证 HZ23 临时生成、门禁检查、原子晋级和 canonical 保护；
10. 杭州执行 HZ24 5 条 sold-out 迁移，确认 72/5/144；
11. 221 队列全终态后恢复剩余可行动采集；
12. 冻结最终候选；
13. 初始化 Data Lab MySQL，完成首次和二次幂等回填；
14. dual-write 稳定运行 7 天；
15. 生成 publish version；
16. AIdeal CPS dry-run、灰度和正式商用。

## 12. 新对话恢复方式

新对话必须先读取：

```text
docs/DOCUMENT_AUTHORITY.md
docs/status/COMMERCIALIZATION_STATUS_20260620.md
docs/project/CURRENT_PROJECT_CONTEXT.md
docs/project/PROJECT_MEMORY_20260620.md
docs/status/CHAT_ARCHIVE_20260620.md
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

然后直接继续代码治理，不要求用户重复复制旧日志。
