# 商用化状态快照 — 2026-06-20

状态：当前权威进展快照，取代 `COMMERCIALIZATION_STATUS_20260619.md` 作为默认状态入口。

## 1. 当前结论

```text
代码治理完成=false
HZ24 恢复允许=false
Data Lab MySQL 初始化允许=false
dual-write 允许=false
publish 允许=false
AIdeal CPS 正式同步允许=false
```

当前第一优先级不是继续功能，而是：

```text
修复并验证工程代码
-> 清零全局 blocker
-> 补齐重复变量/常量赋值检测
-> 重新验证当前 main
-> 修复 HZ23 候选最新产物回归
-> 再恢复 HZ24 和 MySQL 路线
```

## 2. HZ23：历史已验证基线与当前最新产物必须分开

### 2.1 最后一次已验证的商用候选基线

2026-06-15 已完成并通过：

```text
round_id=20260615_100135
pages=1..67
commercial_segment_complete=true
candidate_rows=3304
duplicate_sku_count=0
payload_hash_mismatch=0
successful_probes=2
observation_ready=true
```

`3304` 是最后一次已验证的 HZ23 候选基线，不等同于当前 GitHub 中的 latest manifest。

### 2.2 当前最新 HZ23 轮次

当前 `reports/hz23_round_latest.json`：

```text
round_id=20260620_101332
completed_pages=1..67
commercial_segment_complete=true
scanned_total=4017
last_known_sku_count=3858
successful_probes=4
```

轮次扫描本身完成，但当前 `data/export/aideal_cps_products_commercial_candidate_manifest.json` 显示：

```text
row_count=0
eligible_sku_count=0
trusted_dedup_sku_count=0
candidate_integrity_ready=false
observation_ready=false
gate_failures=[candidate_nonempty]
data_sha256=e3b0c442...b855
```

该 SHA 是空内容 SHA-256。结论：**当前 latest candidate 产物无效，不能当作 3304 基线，也不能用于 MySQL 回填或商用。**

### 2.3 当前 HZ23 风险和处理要求

已完成代码层保护设计和离线测试：

- 空首选来源应回退到可用次选来源；
- 无效 finalize 不应覆盖 canonical candidate/manifest；
- 观测时长和探针不足不得晋级；
- 上一版候选应作为 last-known-good 保留。

但当前 GitHub latest manifest 已经是 0 行无效产物，说明至少存在以下一种情况：

1. 无效产物在保护逻辑落库前已经生成并发布；
2. 生产机运行代码未同步到保护后的 commit；
3. canonical 文件和报告发布链仍有旁路；
4. 生产源 JSONL 为空或未挂载，但 finalize 仍写了 latest manifest。

下一阶段必须在杭州生产机：

- 只读确认最后有效 3304 JSONL、manifest、备份和对应 checksum 是否仍存在；
- 确认 systemd/cron/脚本实际运行的 commit 和 finalize 入口；
- 禁止再次运行会覆盖 canonical candidate 的任务；
- 修复后以新 round 在临时路径生成，全部门禁通过后再原子晋级；
- 未恢复 last-known-good 前，不初始化 MySQL。

不得在文档中把当前 0 行 latest manifest继续描述为“当前 3304 条候选”。

## 3. HZ24 专题增量

### 3.1 已确认事实

```text
5 个专题 Tab membership=250
专题 Tab 去重后 SKU=239
与 HZ23 已验证候选/可信链接重叠=18
真实增量队列=221
旧采集成功 linked=72
明确 sold-out/card-disabled=5
旧 pending=149
预计可行动 pending=144
```

### 3.2 代码状态

HZ24 v2 相关代码和离线测试已经存在，当前离线测试覆盖：

- `linked/unavailable/pending` 终态互斥；
- sold-out / not-promotable 进入 unavailable；
- JSONL 单 SKU 幂等 upsert；
- 72/5/144 精确核算；
- linked hash 不变保护；
- 多文件原子修复和回滚；
- 恢复授权单调性；
- 未授权时不得启动采集；
- 旧 HZ21 适配器移除；
- 脱敏报告发布白名单。

### 3.3 尚未完成

GitHub 当前没有已发布的生产运行报告可证明以下动作已经在杭州执行：

```text
5 条 sold-out 已迁移到 unavailable
72 条 linked 生产文件完整且 hash 已确认
pending 已从 149 核算为 144
resume_gate=true
collection_authorization=true
```

因此：

```text
unavailable 分类代码=已落库并通过离线测试
unavailable 生产迁移=未证明已执行
HZ24 恢复允许=false
```

HZ24 继续暂停，不得直接重启旧采集器。

## 4. 工程代码治理

### 4.1 最新已发布审计报告

```text
git_head=07b8db89274addd4d85c1308bc41a89a0352abab
generated_at=2026-06-20T13:24:06
files_scanned=298
status=FAIL
global blocker=210
full_gate_blocker=210
active blocker=0
compatibility blocker=0
historical blocker=195
support blocker=15
warning=635
```

报告中的 blocker 分类：

```text
hardcoded_absolute_path=3
hardcoded_ip=42
hardcoded_parameter=107
hardcoded_url=58
```

当前该报告没有列出：

```text
duplicate_definition
duplicate_implementation
large_file
long_function
```

因此在该次扫描覆盖范围内这些类别为 0。但不能据此宣称“重复变量/常量定义 100% 清零”，因为当前扫描器尚未完整覆盖 Python/Shell 同作用域重复变量或常量赋值。

### 4.2 当前报告已过期

当前 main 已前进到 2026-06-20 后续文档和代码提交，最新审计/离线报告的 `git_head` 不是当前 main。下一轮必须由新加坡 `datalab` 对当前 main 重新运行，并回写绑定当前 HEAD 的报告。

### 4.3 历史归档

- 已建立只读历史快照分支：`history-snapshot-20260620`；
- main 已移除部分 HZ11-HZ21 历史 Python collector；
- 最新报告仍显示 54 个历史 Shell blocker 文件位于 main；
- support blocker 位于 6 个测试文件；
- 全局 blocker 未清零前，不推进新功能。

下一轮代码治理顺序：

1. 给审计器增加 Python/Shell 重复变量和常量赋值检测；
2. 增加重复配置键和同一默认值多源检测；
3. 将剩余 HZ12-HZ21 历史 Shell 从 main 移除，保留历史快照分支；
4. 将测试 URL、SKU、时间等集中到 fixture；
5. 重新扫描并逐项清零全局 blocker；
6. Offline Quality 和全量审计必须绑定同一个当前 main HEAD；
7. 未达到全局零 blocker 不进入 HZ24/MySQL 功能阶段。

## 5. 离线质量

最新已发布离线报告：

```text
git_head=07b8db89274addd4d85c1308bc41a89a0352abab
status=PASS
tests_run=63
failures=0
errors=0
compile_failures=[]
jd_live_called=false
```

该结果证明相关 HZ23/HZ24/MySQL 离线测试在该 commit 通过，但报告 HEAD 已落后于当前 main，必须重跑后才能作为下一阶段门禁。

## 6. MySQL 与 AIdeal CPS

### 6.1 已准备

- Data Lab MySQL V1 DDL 和 migration；
- `commission_products`、refresh/history/publish version 和只读视图设计；
- Repository、staging V2、事务和幂等 upsert；
- JSONL 回填和 post-migration 校验；
- canonical hash 校验；
- AIdeal CPS 短生命周期 SSH Tunnel 和本地 MySQL 同步设计。

### 6.2 尚未执行

```text
Data Lab MySQL 初始化
有效候选回填
二次幂等回填验证
JSONL/MySQL dual-write
dual-write 连续 7 天稳定运行
publish version
AIdeal CPS dry-run sync
灰度和正式同步
```

### 6.3 MySQL 初始化硬门禁

必须全部满足：

- 当前 main 全局工程 blocker=0；
- 当前 main Offline Quality=PASS 且 `jd_live_called=false`；
- HZ23 last-known-good 候选恢复并通过 checksum/schema/hash；
- HZ24 221 队列全部进入 linked/unavailable 终态，无未知 pending；
- unavailable 不进入候选；
- 最终候选版本冻结；
- 回滚和备份方案验证；
- 所有写入开关仍由显式人工切换。

## 7. 环境与执行方式

```text
杭州 Data Lab 生产：121.41.111.36 / cpsdata
新加坡 CI Bridge：43.106.55.255 / datalab
杭州 AIdeal CPS 生产：8.136.28.6 / deploy
```

操作入口：

1. 运维人员登录杭州 `cpsdata`；
2. 从杭州 SSH 进入新加坡 `datalab`；
3. 在新加坡运行仓库内单一离线验证脚本；
4. 报告回写 GitHub；
5. 助手从 GitHub读取报告继续修改；
6. 只有全部门禁通过后，杭州生产机才拉取已验证 commit。

后续不再在对话中提供大量零散命令。复杂操作先提交为仓库 `.sh` 文件，用户只执行一个入口。

## 8. 下一步计划

严格顺序：

1. 完成本轮文档、项目记忆、环境拓扑和新对话 Prompt 归档；
2. 提交并验证新加坡 CI Bridge 单一执行脚本；
3. 新对话首先补齐重复变量/常量赋值审计；
4. 清理 main 剩余历史 Shell 和 support fixture blocker；
5. 在新加坡对当前 main 运行编译、63+ 测试和全量工程审计；
6. 要求 global/full gate blocker、重复定义、重复赋值、重复实现、长文件、长函数全部为 0；
7. 杭州只读恢复并核验 HZ23 3304 last-known-good 候选，修复 canonical promotion 链；
8. 杭州执行 HZ24 5 条 sold-out 原子迁移并确认 72/5/144；
9. 完成 221 队列终态后，才允许恢复剩余采集；
10. 最终候选冻结后初始化 MySQL、回填、dual-write 7 天；
11. 生成 publish version；
12. AIdeal CPS dry-run、灰度、正式商用。

## 9. 当前门禁状态

```text
CODE_CLEANUP_COMPLETE=false
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