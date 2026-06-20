# 商用化状态快照 — 2026-06-20

状态：当前权威进展快照。设计、环境和交互规则见 `PROJECT_MEMORY_20260620.md`；本轮归档范围见 `CHAT_ARCHIVE_20260620.md`。

## 1. 总体门禁

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

当前唯一优先级：先完成代码治理，再推进功能。

## 2. HZ23

### 最后一次已验证基线

```text
round_id=20260615_100135
completed_pages=1..67
candidate_rows=3304
duplicate_sku_count=0
payload_hash_mismatch=0
successful_probes=2
observation_ready=true
```

3304 条是 last-known-good 历史基线，不是当前 latest manifest。

### 当前 latest 回归

当前轮次：

```text
round_id=20260620_101332
completed_pages=1..67
commercial_segment_complete=true
scanned_total=4017
last_known_sku_count=3858
successful_probes=4
```

当前 candidate manifest：

```text
row_count=0
eligible_sku_count=0
trusted_dedup_sku_count=0
candidate_integrity_ready=false
observation_ready=false
gate_failures=[candidate_nonempty]
data_sha256=empty-file SHA-256
```

结论：当前 latest candidate 无效，不能用于 MySQL、publish 或商用同步。

代码层已增加并测试：空首选来源回退、无效 finalize 不覆盖 canonical、观测门禁、last-known-good 保护。但杭州生产机仍需只读确认：

- 3304 JSONL、manifest、备份和 checksum 是否仍存在；
- systemd/cron 实际运行 commit 和 finalize 入口；
- 是否存在绕过 canonical promotion 的旁路。

恢复前禁止再次覆盖 canonical candidate，禁止初始化 MySQL。

## 3. HZ24

```text
专题 membership=250
去重后 SKU=239
与已验证候选/可信链接重叠=18
真实增量队列=221
旧 linked=72
明确 sold-out/card-disabled=5
旧 pending=149
预计可行动 pending=144
```

HZ24 v2 离线代码和测试已覆盖：

- linked/unavailable/pending 互斥；
- sold-out 和 not-promotable 终态；
- JSONL 幂等 upsert；
- 多文件原子迁移和回滚；
- 72/5/144 精确核算；
- linked hash 保持；
- 恢复授权和未授权不启动；
- 旧 HZ21 适配器移除；
- 脱敏报告白名单。

GitHub 目前没有生产报告证明杭州已实际完成：

```text
5 条 sold-out 迁移
72 条 linked 完整性和 hash 核验
pending=144 核算
resume_gate=true
collection_authorization=true
```

因此 HZ24 继续暂停，不得启动旧采集器。

## 4. 工程治理

最新已发布审计报告：

```text
git_head=07b8db89274addd4d85c1308bc41a89a0352abab
generated_at=2026-06-20T13:24:06
files_scanned=298
status=FAIL
global/full gate blocker=210
active blocker=0
compatibility blocker=0
historical blocker=195
support blocker=15
warning=635
```

blocker 分类：

```text
hardcoded_absolute_path=3
hardcoded_ip=42
hardcoded_parameter=107
hardcoded_url=58
```

该次扫描未发现重复函数/类/方法、跨文件重复实现、大文件或长函数。但扫描器尚未完整覆盖 Python/Shell 重复变量、模块常量、配置键和默认值来源，不能宣称重复问题 100% 清零。

历史快照分支：

```text
history-snapshot-20260620
```

main 仍有 54 个历史 Shell blocker 文件和 6 个 support blocker 文件。下一阶段必须：

1. 增加 `duplicate_assignment`、`duplicate_constant_assignment`、`duplicate_config_key` 和默认值多源检测；
2. 将剩余 HZ12-HZ21 历史 Shell 从 main 移除；
3. 收口测试 fixture；
4. 全局 blocker 清零；
5. 对当前 main 重跑离线测试和工程审计。

## 5. 离线质量与 CI Bridge

最新已发布离线报告：

```text
git_head=07b8db89274addd4d85c1308bc41a89a0352abab
status=PASS
tests_run=63
failures=0
errors=0
jd_live_called=false
```

该报告已落后于当前 main。

已提交统一脚本：

```text
scripts/ops/run_ci_bridge_from_hangzhou.sh
scripts/ops/run_data_lab_ci_bridge.sh
scripts/ops/ci_bridge_runner.py
scripts/ops/ci_bridge_report_gate.py
scripts/ops/ci_bridge_summary.py
```

执行路径：杭州 `cpsdata` 作为登录入口，SSH 到新加坡 `datalab`；离线验证在新加坡执行。

脚本已增加陈旧报告保护：旧报告归档到 `run/`，只有新报告存在、HEAD 匹配、offline mode 为真、JD live 为假且全局门禁字段存在时才允许回写。

尚未在服务器首次实跑，因此：

```text
CI_BRIDGE_RUNTIME_VALIDATED=false
CURRENT_HEAD_VALIDATED=false
```

## 6. MySQL 与 AIdeal CPS

已完成设计和部分离线代码：

- Data Lab MySQL V1 DDL/migration；
- commission products、refresh/history/publish version 和只读视图；
- Repository、staging、事务和幂等 upsert；
- JSONL 回填和 post-migration 校验；
- canonical hash；
- AIdeal CPS 短生命周期 SSH Tunnel 和本地同步设计。

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

MySQL 初始化前必须满足：

- 当前 main 全局工程 blocker=0；
- 重复定义、重复赋值、重复实现、大文件和长函数为 0；
- Offline Quality=PASS 且 `jd_live_called=false`；
- 审计和离线报告绑定当前 main；
- HZ23 last-known-good 恢复并通过 checksum/schema/hash；
- HZ24 221 队列全终态；
- unavailable 不进入候选；
- 最终候选冻结；
- 备份和回滚验证；
- 所有写入开关由显式人工切换。

## 7. 环境和执行方式

```text
杭州 Data Lab 生产：121.41.111.36 / cpsdata
新加坡 CI Bridge：43.106.55.255 / datalab
杭州 AIdeal CPS 生产：8.136.28.6 / deploy
```

用户只需登录杭州 `cpsdata`，由仓库入口脚本 SSH 到新加坡 `datalab`。复杂操作不再以零散命令交付，必须先提交 GitHub 脚本。

## 8. 严格下一步

1. 新对话读取权威文档、当前 main 和报告；
2. 补齐重复变量/常量/配置键审计及测试；
3. 清理全部历史 Shell 和 support blocker；
4. 首次运行 CI Bridge，对当前 main 生成新报告；
5. 全局代码门禁清零；
6. 杭州只读恢复并核验 3304 last-known-good；
7. 修复并验证 HZ23 临时生成、门禁检查和原子晋级；
8. 杭州执行 HZ24 sold-out 迁移并确认 72/5/144；
9. 221 队列全终态后恢复剩余采集；
10. 冻结最终候选，初始化 MySQL并做两次幂等回填；
11. dual-write 稳定 7 天；
12. publish version；
13. AIdeal CPS dry-run、灰度和正式商用。
