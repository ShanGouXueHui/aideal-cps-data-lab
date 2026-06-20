# AIdeal CPS Data Lab 对话归档（二）

更新日期：2026-06-20

状态：本文件归档本轮从“代码治理清零”到“HZ23 last-known-good 只读核验准备”的完整决策、事实、纠错和遗留事项。当前状态仍以 `docs/status/COMMERCIALIZATION_STATUS_20260620.md` 为准。

## 1. 本轮启动要求

本轮最初的唯一优先级是先完成代码治理，不从头设计，不要求用户复制旧日志，并直接读取和修改 GitHub。

强制目标：

- 重复函数、异步函数、类、方法和 Shell 函数为 0；
- 重复变量、模块常量、配置键和默认值多源为 0；
- 跨文件重复实现为 0；
- global/full 以及全部 scope blocker 为 0；
- 大文件和长函数为 0；
- 工程审计和 Offline Quality 必须绑定当前代码版本；
- 代码治理完成前不恢复 HZ24、不初始化 MySQL、不 publish、不同步 AIdeal CPS。

交互要求：

- 中文、职业化、直接、结构化；
- 长代码、复杂脚本和文档直接写入 GitHub；
- 用户只执行仓库内审核过的单一 `.sh` 入口；
- 日志写入 `logs/`、`reports/` 或 `docs/debug/`，终端只返回 Summary；
- 不使用 Codex CLI；
- Shell 不使用 `set -e`；
- 自动测试禁止 JD live；
- Secret、账号、Cookie、Profile、Token、私钥和数据库密码不得进入 GitHub。

## 2. 代码治理完成情况

本轮完成了以下审计能力和代码清理：

- Python 同作用域函数、异步函数、类和方法重复定义；
- Shell 函数重复定义；
- Python/Shell 重复赋值、模块常量和配置赋值；
- TOML、YAML、INI、JSON 配置键重复；
- 环境变量、配置和 CLI 默认值多源；
- 跨文件函数实现指纹；
- Python、Shell 和配置语法；
- 大文件和长函数；
- 全局 scope 门禁，不再只看 active。

历史 HZ12-HZ22 实验入口已从正式候选树清理，历史仍保存在 Git 历史或 `history-snapshot-20260620`。

最终已验证的代码树结果：

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
python_shell_syntax=PASS
```

最终已验证的 Offline Quality：

```text
tests_run=69
failure_count=0
error_count=0
jd_live_called=false
offline_mode=true
status=PASS
```

72 条 `repeated_literal` 为 warning，不是 blocker；它们不能替代重复变量、常量、配置键和默认值门禁。

## 3. 当前 main 与报告绑定

归档时：

```text
main=d8eb7bdd251600b237e8c33b3eed04cc6c2257a5
validated_code_commit=33cd3ec9174ac772f3874ab88c83189e548f9990
```

GitHub compare 已确认：`d8eb7bdd...` 是 `33cd3ec9...` 的直接后继，只修改了：

```text
reports/project_engineering_audit_latest.json
```

因此代码树没有回退，代码治理逻辑仍成立；但严格报告绑定失效，因为报告提交本身推进了 `main`。

当前状态必须区分：

```text
CODE_GOVERNANCE_LOGIC_COMPLETE=true
CODE_GOVERNANCE_FORMAL_ACCEPTANCE=false
CURRENT_HEAD_VALIDATED=false
```

正式验收仍要求权威 Engineering Audit 和 Offline Quality 的 `git_head` 精确等于当前 `main`。

## 4. 报告发布架构问题

本轮发现并修复了多条“报告直接推进 main”的链路：

- Active Engineering Audit 曾直接把报告提交到 main；
- Offline Quality 的首次报告分支发布可成功，但第二次更新因 Git identity 配置顺序问题失败；
- CI Bridge 的 `validate-publish` 曾调用通用 worktree publisher，把质量报告提交到 main；
- 旧 `scripts/run_engineering_scan_and_publish.sh` 曾直接发布工程审计到 main。

主线代码中已完成：

- Active Audit 改为 artifact-only；
- CI Bridge 改为 validation-only，不再发布质量报告；
- 删除旧工程审计 main publisher；
- Full Audit 和 Active Audit 在 main 中应为非权威指针；
- GitHub Actions 的权威质量报告目标为 `quality-reports`。

但是新加坡机器上仍可能存在旧 checkout、cron、systemd user timer 或残留命令，继续执行旧发布脚本。最近的异常提交信息为：

```text
reports: update engineering audit baseline
```

必须先在新加坡 `datalab` 只读定位并停止该旧任务，再重新生成绑定当前 main 的权威报告。

## 5. 报告分支长期设计

为避免任何运行报告推进代码 main，后续必须采用：

```text
main              代码、配置、合同、测试、文档和非权威指针
quality-reports   Engineering Audit 与 Offline Quality 权威报告
runtime-evidence  HZ23/HZ24/MySQL readiness 等脱敏运行证据
```

`quality-reports` 和 `runtime-evidence` 是证据分支，不是代码主线，不违反“正式代码只有一个 main”。

必须重构或限制 `scripts/git_publish_files_via_worktree.sh`：

- 禁止质量报告写入 main；
- 禁止 HZ23/HZ24/MySQL 运行报告写入 main；
- 运行证据发布到 `runtime-evidence`；
- 报告必须记录 `code_git_head`、round_id、schema、checksum 和生成时间；
- JSONL、Cookie、Profile、Secret 和数据库备份永远不得发布。

## 6. HZ23 last-known-good

最后一次已验证历史基线：

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

主线已加入只读审计能力：

```text
config/hz23-last-known-good.toml
src/aideal_cps_data_lab/hz23/lkg_settings.py
src/aideal_cps_data_lab/hz23/lkg_candidate_audit.py
src/aideal_cps_data_lab/hz23/lkg_runtime_audit.py
scripts/hz23_readonly_lkg_audit.py
scripts/hz23_run_lkg_readonly_audit.sh
tests/test_hz23_lkg_readonly_audit.py
```

该能力只计算：文件相对路径、大小、SHA256、行数、SKU 唯一性和 JSON 完整性，不输出商品明细。

尚未在杭州生产机执行。执行前必须先把其报告发布从 main 改为 `runtime-evidence` 或临时仅本地生成，否则会再次推进 main 并让质量报告陈旧。

## 7. HZ24

当前事实：

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

离线代码已覆盖 linked/unavailable/pending、sold-out、幂等 upsert、原子迁移和回滚、72/5/144 核算、linked hash 和恢复授权。

仍无杭州生产证据证明：

```text
5 条 sold-out 已迁移
72 条 linked 完整且 hash 未变
pending=144
resume_gate=true
collection_authorization=true
```

因此 HZ24 继续暂停。

## 8. MySQL 与 AIdeal CPS

尚未执行：

```text
Data Lab MySQL 初始化
有效候选首次回填
二次幂等回填
JSONL/MySQL dual-write
dual-write 连续 7 天稳定运行
publish version
AIdeal CPS dry-run、灰度和正式同步
```

所有写入、发布和同步开关保持 false。

## 9. 环境与 SSH 纠错

环境：

```text
杭州 Data Lab：121.41.111.36 / cpsdata
新加坡 CI Bridge：43.106.55.255 / datalab
杭州 AIdeal CPS：8.136.28.6 / deploy
```

本轮曾错误尝试使用新加坡用户 `cpsdev`。正确的 Data Lab 隔离用户是 `datalab`；`cpsdev` 属于其他项目。

新加坡 SSH 服务实际一直正常运行。失败根因是 `datalab` 的 `authorized_keys` 缺少杭州 bridge 公钥，而不是 sshd 未启动。

已完成：

- 杭州专用密钥存在；
- 新加坡 `datalab` 用户存在且不在 sudoers；
- 公钥已加入 `/home/datalab/.ssh/authorized_keys`；
- 杭州 SSH 别名 `sg-aideal-datalab` 已验证成功；
- `BatchMode=yes` 可无密码登录。

验证结果：

```text
USER=datalab
HOST=iZt4n62qkjefjya5xa097pZ
HOME=/home/datalab
```

后续统一使用：

```text
ssh -o BatchMode=yes sg-aideal-datalab
```

不要再使用 `cpsdev@43.106.55.255`，也不要在 `datalab` 下反复执行 sudo；该用户按设计不具备 sudo 权限。

## 10. 已纠正的错误认知

- 新加坡 SSH 服务并未停止；
- 正确用户是 `datalab`，不是 `cpsdev`；
- 代码治理扫描器已完整覆盖重复变量、常量、配置键和默认值多源，不再是能力缺口；
- 代码治理逻辑已清零，但报告绑定仍未正式闭环；
- `d8eb7bdd...` 没有回退代码，只增加了报告提交；
- CI Bridge 不应再承担质量报告发布，只做离线验证；
- 运行报告提交到 main 会永久制造自陈旧，必须改为 evidence 分支。

## 11. 未完成任务

严格顺序：

1. 在新加坡 `datalab` 定位并停止旧工程审计发布任务；
2. 拉取当前 main，确认旧 checkout/cron/systemd timer 不再写 main；
3. 把通用运行报告发布器收敛到 `runtime-evidence`，禁止运行证据写 main；
4. 重新运行当前 main 的 Full Audit 和 Offline Quality；
5. 确认 `quality-reports.git_head == main` 且 main 不再因报告推进；
6. 将 `CODE_GOVERNANCE_FORMAL_ACCEPTANCE` 置为 true；
7. 在杭州执行 HZ23 3304 只读盘点；
8. 若找到精确 SHA256 匹配，只生成证据，不立即恢复 canonical；
9. 单独设计和验证原子恢复、备份、回滚和 canonical promotion；
10. 完成 HZ24 5 条 sold-out 迁移和 72/5/144 生产核算；
11. 221 队列全终态后再恢复剩余采集；
12. 冻结最终候选；
13. 初始化 Data Lab MySQL并做两次幂等回填；
14. dual-write 连续稳定 7 天；
15. 生成 publish version；
16. AIdeal CPS dry-run、灰度和正式商用。

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
