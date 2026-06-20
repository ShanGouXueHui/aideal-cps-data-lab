# AIdeal CPS Data Lab 当前项目上下文

更新日期：2026-06-20

状态：新对话当前事实入口。精确进展见 `COMMERCIALIZATION_STATUS_20260620.md`，长期设计和习惯见 `PROJECT_MEMORY_20260620.md`。

## 1. 项目边界

Data Lab 负责京东联盟授权浏览器采集、商品与推广资格解析、可信短链、终态维护、质量门禁、版本化发布和未来 Data Lab MySQL。

AIdeal CPS 负责微信/H5、搜索推荐、点击归因、订单和返佣。用户请求只访问 AIdeal CPS 本地 MySQL，不实时依赖 Data Lab 浏览器、SSH Tunnel 或远程数据库。

## 2. 环境角色

```text
杭州 Data Lab 生产：121.41.111.36 / cpsdata
目录：/home/cpsdata/projects/aideal-cps-data-lab

新加坡 CI Bridge：43.106.55.255 / datalab
目录：/home/datalab/projects/aideal-cps-data-lab

杭州 AIdeal CPS 生产：8.136.28.6 / deploy
目录：/home/deploy/projects/aideal-cps
```

杭州是唯一允许真实 JD、HZ23/HZ24、生产状态和 Data Lab MySQL 的环境。新加坡只运行离线编译、测试、审计和脱敏报告回写。

用户从杭州 `cpsdata` 运行仓库脚本，脚本 SSH 到新加坡 `datalab`。SSH 只减少人工切换，不传输生产数据或 Secret。

## 3. HZ23

最后一次已验证基线：

```text
round_id=20260615_100135
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
scanned_total=4017
last_known_sku_count=3858
successful_probes=4
```

当前 latest manifest 回归：

```text
row_count=0
eligible_sku_count=0
trusted_dedup_sku_count=0
candidate_integrity_ready=false
observation_ready=false
gate_failures=[candidate_nonempty]
```

3304 条是 last-known-good，不是当前 latest。当前 0 行产物无效，不能用于 MySQL、publish 或商用。

代码已覆盖空源回退、无效 finalize 不晋级、观测门禁和 last-known-good 保护。代码治理完成后，必须在杭州只读恢复和核验 3304 JSONL、manifest、备份、checksum 及实际运行入口。

## 4. HZ24

```text
专题 membership=250
去重后 SKU=239
重叠=18
增量队列=221
旧 linked=72
明确 sold-out=5
旧 pending=149
预计可行动 pending=144
```

V2 离线代码和测试已覆盖 linked/unavailable/pending、sold-out、幂等 upsert、原子迁移和回滚、72/5/144、linked hash、恢复授权和报告白名单。

但没有生产报告证明杭州已实际完成 5 条迁移和 72/5/144 核验。

```text
HZ24_RUNTIME_MIGRATION_CONFIRMED=false
HZ24_RESUME_ALLOWED=false
```

不得启动旧采集器。

## 5. 工程治理

最新已发布审计：

```text
git_head=07b8db89274addd4d85c1308bc41a89a0352abab
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

该次扫描未发现重复函数/类/方法、重复实现、大文件或长函数，但当前扫描器尚未完整覆盖 Python/Shell 重复变量、模块常量、配置键和默认值来源。

历史快照分支：

```text
history-snapshot-20260620
```

main 仍有 54 个历史 Shell blocker 文件和 6 个 support blocker 文件。全局 blocker 未清零前，不推进业务功能。

## 6. 离线验证与统一脚本

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

已提交：

```text
scripts/ops/run_ci_bridge_from_hangzhou.sh
scripts/ops/run_data_lab_ci_bridge.sh
scripts/ops/ci_bridge_runner.py
scripts/ops/ci_bridge_report_gate.py
scripts/ops/ci_bridge_summary.py
```

脚本会归档旧报告，并阻止 HEAD 不匹配、非 offline、JD live 标志异常或缺少全局门禁字段的报告回写。

```text
CI_BRIDGE_RUNTIME_VALIDATED=false
CURRENT_HEAD_VALIDATED=false
```

首次服务器实跑留给新对话代码治理阶段。

## 7. 编程和交互规则

- 先修代码，后推进功能；
- 扫描重复函数、类、方法、变量、常量、配置键和跨文件重复实现；
- 正式验收要求全局 blocker=0；
- 文件 >300 行、函数 >80 行、入口 >120 行必须拆分；
- 分层：browser、application、domain、persistence、contracts、configuration、ops、tests；
- 配置与环境分离，默认值只有一个来源；
- main 是唯一正式主线；
- 历史只保留 Git 历史或只读快照分支；
- 自动测试禁止 JD live；
- Secret、Cookie、Profile、Token、私钥和数据库密码不进入 GitHub；
- 助手直接修改 GitHub并二次确认；
- 复杂操作上传为仓库脚本，用户只执行单一入口；
- 日志写入 GitHub可读报告，用户只返回紧凑 Summary；
- 不使用 Codex CLI；
- Shell 不使用 `set -e` 或 `|| exit 1`。

## 8. MySQL 和同步

目标 Data Lab 数据库：

```text
aideal_cps_data_lab
commission_products
commission_refresh_runs
commission_product_history
commission_publish_versions
v_published_commission_products
```

设计和部分离线代码已准备，但尚未执行初始化、有效候选回填、二次幂等回填、dual-write、7 天稳定运行、publish version 或 AIdeal CPS dry-run。

所有写入、发布和同步开关保持 false。

## 9. 严格下一步

1. 新对话读取权威文档、当前 main 和报告；
2. 补齐重复变量/常量/配置键审计和测试；
3. 清理全部历史 Shell 和 support blocker；
4. 首次运行 CI Bridge并回写当前 HEAD 报告；
5. 全局工程门禁清零；
6. 杭州只读恢复和核验 3304 last-known-good；
7. 修复并验证 HZ23 canonical promotion；
8. 杭州执行 HZ24 sold-out 迁移并确认 72/5/144；
9. 221 队列全终态后恢复剩余采集；
10. 冻结最终候选后初始化 MySQL、回填和 dual-write；
11. dual-write 稳定 7 天；
12. publish version；
13. AIdeal CPS dry-run、灰度和正式商用。

## 10. 当前门禁

```text
CODE_CLEANUP_COMPLETE=false
CI_BRIDGE_RUNTIME_VALIDATED=false
CURRENT_HEAD_VALIDATED=false
HZ23_LKG_CANDIDATE_CONFIRMED=false
HZ24_RUNTIME_MIGRATION_CONFIRMED=false
HZ24_RESUME_ALLOWED=false
MYSQL_INITIALIZATION_ALLOWED=false
PUBLISH_ALLOWED=false
AIDEAL_CPS_SYNC_ALLOWED=false
COMMERCIAL_ENABLED=false
```
