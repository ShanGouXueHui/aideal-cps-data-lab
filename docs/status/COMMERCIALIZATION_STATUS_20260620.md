# 商用化状态快照 — 2026-06-20

状态：当前权威任务进展。长期设计见 `PROJECT_MEMORY_20260620.md`，完整归档见 `docs/status/CHAT_ARCHIVE_20260620_PART2.md`。

## 1. 总体门禁

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

当前唯一优先级：先修复报告发布权威并完成当前 main 的正式工程验收，再执行 HZ23 只读核验。

## 2. 工程治理

已验证代码树：

```text
files_scanned=258
all blocker scopes=0
all duplicate categories=0
large_file=0
long_function=0
python/shell/config syntax=PASS
```

Offline Quality：

```text
tests_run=69
failures=0
errors=0
jd_live_called=false
status=PASS
```

扫描器已经完整覆盖重复定义、重复赋值、模块常量、配置键、默认值多源和跨文件重复实现。旧状态文件中的“能力尚未补齐”已失效。

归档时当前 main 是已验证代码树的直接后继，只修改工程审计报告，代码没有回退；但报告提交推进 main，导致严格 HEAD 绑定失败。

当前最先修复：

1. 新加坡旧 checkout、cron、systemd user timer 或残留命令；
2. 提交信息 `reports: update engineering audit baseline` 的来源；
3. 通用运行报告发布到 main 的路径；
4. `runtime-evidence` 证据分支。

## 3. HZ23

last-known-good：

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

3304 是历史基线，不是当前 latest。0 行产物无效，不能用于 MySQL、publish 或商用。

只读审计代码和测试已经进入 main，但尚未在杭州执行。执行前必须先将报告发布迁移出 main。

## 4. HZ24

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

离线代码已覆盖终态、sold-out、幂等 upsert、原子迁移和回滚、72/5/144 核算、linked hash 和恢复授权。

仍无杭州生产证据证明 5 条迁移和 72/5/144 已落地，因此 HZ24 继续暂停。

## 5. CI Bridge 与 SSH

杭州到新加坡无密码 SSH 已验证：

```text
ssh -o BatchMode=yes sg-aideal-datalab
USER=datalab
HOST=iZt4n62qkjefjya5xa097pZ
HOME=/home/datalab
```

正确用户是 `datalab`，不是 `cpsdev`。`datalab` 不在 sudoers。

SSH 可用不等于 CI Bridge runtime 已验证。当前仍需在新加坡定位旧报告发布任务并对当前 main 运行统一离线门禁。

## 6. MySQL 与 AIdeal CPS

尚未执行：

- Data Lab MySQL 初始化；
- 有效候选首次和二次幂等回填；
- JSONL/MySQL dual-write；
- dual-write 连续稳定 7 天；
- publish version；
- AIdeal CPS dry-run、灰度和正式同步。

所有写入、发布和同步开关保持 false。

## 7. 严格下一步

1. 在新加坡只读定位旧工程审计发布任务；
2. 停止并禁用旧任务；
3. 新加坡仓库拉取当前 main；
4. 将运行证据发布迁移到 `runtime-evidence`；
5. 重跑 Full Audit 和 Offline Quality；
6. 确认权威报告绑定 current main，main 不再被报告推进；
7. 杭州执行 HZ23 3304 只读盘点；
8. 只生成证据，不立即恢复 canonical；
9. 后续单独验证原子恢复、HZ24、MySQL 和商用链。
