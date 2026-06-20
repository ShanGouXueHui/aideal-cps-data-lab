# AIdeal CPS Data Lab 当前项目上下文

更新日期：2026-06-20

状态：新对话必须优先读取的当前事实入口。长期设计和交互习惯见 `PROJECT_MEMORY_20260620.md`，精确任务状态见 `COMMERCIALIZATION_STATUS_20260620.md`。

## 1. 项目目标与系统边界

AIdeal CPS Data Lab 负责京东联盟授权浏览器采集、商品与推广资格解析、可信推广短链生成、终态维护、质量门禁、版本化发布和未来 Data Lab MySQL。

AIdeal CPS 负责微信/H5、搜索推荐、点击归因、订单和返佣。用户请求只访问 AIdeal CPS 本地 MySQL，不实时依赖 Data Lab 浏览器、SSH Tunnel 或远程数据库。

## 2. 环境角色

### 杭州 Data Lab 生产

```text
121.41.111.36 / cpsdata
/home/cpsdata/projects/aideal-cps-data-lab
```

唯一允许真实 JD 登录、浏览器 Profile、HZ23/HZ24 采集、生产状态写入和 Data Lab MySQL 的环境。

### 新加坡 CI Bridge

```text
43.106.55.255 / datalab
/home/datalab/projects/aideal-cps-data-lab
```

只替代 GitHub Actions 执行离线编译、测试、工程审计和脱敏报告回写。不得保存 Cookie/Profile、运行真实采集或初始化生产 MySQL。

新加坡原有 `cpsdev` 服务其他开发项目；Data Lab 使用隔离用户 `datalab`。

### 杭州 AIdeal CPS 生产

```text
8.136.28.6 / deploy
/home/deploy/projects/aideal-cps
MySQL=aideal_cps
```

它是消费端生产，不承担京东联盟采集。

### 统一运维入口

用户可以只登录杭州 `cpsdata`，再 SSH 进入新加坡 `datalab`。SSH 只用于进入离线验证 Shell，不传输生产数据或 Secret。

## 3. HZ23 当前事实

### 3.1 最后一次已验证基线

2026-06-15 已验证：

```text
round_id=20260615_100135
completed_pages=1..67
candidate_rows=3304
duplicate_sku_count=0
payload_hash_mismatch=0
successful_probes=2
observation_ready=true
```

这 3304 条是 last-known-good 历史基线，不是当前 latest manifest 的状态。

### 3.2 当前 latest 发生回归

当前轮次：

```text
round_id=20260620_101332
completed_pages=1..67
commercial_segment_complete=true
scanned_total=4017
last_known_sku_count=3858
successful_probes=4
```

但当前 candidate manifest：

```text
row_count=0
eligible_sku_count=0
trusted_dedup_sku_count=0
candidate_integrity_ready=false
observation_ready=false
gate_failures=[candidate_nonempty]
data_sha256=empty-file SHA-256
```

因此当前 latest candidate 无效。3304 条基线必须从杭州生产机的 last-known-good JSONL/manifest/备份中只读恢复并重新校验，不能从当前 latest manifest 推断。

在恢复前：

- 禁止 MySQL 回填；
- 禁止发布；
- 禁止将 0 行 latest 当作新基线；
- 禁止再次运行可能覆盖 canonical candidate 的任务。

## 4. HZ24 当前事实

```text
专题 Tab membership=250
专题去重后 SKU=239
与已验证候选/可信链接重叠=18
真实增量队列=221
旧采集 linked=72
明确 sold-out/card-disabled=5
旧 pending=149
预计可行动 pending=144
```

HZ24 v2 离线代码和测试已经覆盖：

- linked/unavailable/pending 互斥状态；
- sold-out 和 not-promotable 终态；
- 原子 JSONL upsert 和回滚；
- 72/5/144 精确核算；
- linked hash 保持；
- 恢复授权和未授权不启动；
- 脱敏报告白名单。

但 GitHub 没有生产报告证明杭州已实际完成 5 条 sold-out 迁移、72 条 linked hash 核验和 144 pending 核算。

```text
HZ24 v2 code ready=true
HZ24 runtime migration confirmed=false
HZ24 resume allowed=false
```

HZ24 继续暂停，不得启动旧采集器。

## 5. 工程治理

最新已发布审计：

```text
git_head=07b8db89274addd4d85c1308bc41a89a0352abab
files_scanned=298
status=FAIL
global/full gate blocker=210
active blocker=0
compatibility blocker=0
historical blocker=195
support blocker=15
warning=635
```

blocker 当前全部属于历史 Shell 硬编码和测试 fixture：

```text
hardcoded_absolute_path=3
hardcoded_ip=42
hardcoded_parameter=107
hardcoded_url=58
```

该报告未发现重复函数/类/方法、跨文件重复实现、超长文件或超长函数，但审计器尚未完整覆盖 Python/Shell 同作用域重复变量、模块常量和配置赋值。因此不能宣称“重复定义 100% 清零”。

当前主线任务：

1. 扩展审计器，覆盖重复变量/常量/配置键；
2. 清理 main 中剩余 HZ12-HZ21 历史 Shell，历史只留 `history-snapshot-20260620`；
3. 收口测试 fixture；
4. 全局 blocker 清零；
5. 新加坡对当前 main 重新跑 Offline Quality 和 Engineering Audit；
6. 报告 `git_head` 必须等于当前 main。

在全局代码门禁通过前，不推进业务功能。

## 6. 离线测试

最新已发布离线报告：

```text
git_head=07b8db89274addd4d85c1308bc41a89a0352abab
status=PASS
tests_run=63
failures=0
errors=0
jd_live_called=false
```

该结果证明当时 commit 通过，但已落后于当前 main。必须在新加坡 CI Bridge 重跑后才能作为当前门禁。

## 7. 编程规范

固定要求：

- 修改前扫描重复函数、类、方法、变量、常量、配置键和跨文件重复实现；
- 正式验收要求全局 blocker=0，不只看 active scope；
- 分层：browser、application、domain、persistence、contracts、configuration、ops、tests；
- 配置与环境分离，默认值只有一个来源；
- Python/Shell 文件 >300 行先拆分；
- 函数 >80 行先拆分；
- 入口 >120 行收敛为薄入口；
- main 是唯一正式主线；
- 历史证据保留在只读快照分支，不留在 main 执行路径；
- 自动测试禁止 JD live；
- Secret、Cookie、Profile、Token、私钥、数据库密码不进入 GitHub。

## 8. 执行与交互规则

- 使用中文，职业化、直接、结构化；
- 助手直接读取和修改 GitHub；
- 代码、长脚本和复杂命令上传为仓库文件，不在对话中打印；
- 用户只执行仓库内单一 `.sh` 入口；
- 用户从杭州 `cpsdata` SSH 进入新加坡 `datalab` 运行离线验证；
- 日志写入 `logs/`、`reports/`、`docs/debug/`；
- 用户只返回紧凑 Summary，助手直接从 GitHub读取详细报告；
- GitHub 写入后必须二次确认；
- 不使用 Codex CLI；
- Linux 脚本不用 `set -e`，不用 `|| exit 1`。

## 9. MySQL 状态

目标数据库：

```text
aideal_cps_data_lab
commission_products
commission_refresh_runs
commission_product_history
commission_publish_versions
v_published_commission_products
```

已完成设计和较多代码准备，但尚未执行：

```text
MySQL 初始化
有效候选回填
二次幂等回填
dual-write
7 天稳定运行
publish version
AIdeal CPS dry-run/灰度/正式同步
```

所有写入、发布和同步开关保持 false。

## 10. 严格下一步顺序

1. 完成文档和新对话归档；
2. 提交新加坡 CI Bridge 单一验证脚本；
3. 增加重复变量/常量/配置键审计；
4. 清理全部历史 Shell 和 support blocker；
5. 当前 main 全局工程审计和离线测试通过；
6. 杭州只读恢复并验证 3304 last-known-good；
7. 修复并验证 HZ23 canonical promotion 链；
8. 杭州执行 HZ24 sold-out 迁移并确认 72/5/144；
9. 221 队列全终态完成后再恢复剩余采集；
10. 冻结最终候选后初始化 MySQL；
11. dual-write 稳定 7 天；
12. publish version；
13. AIdeal CPS dry-run、灰度、正式商用。

## 11. 当前门禁

```text
CODE_CLEANUP_COMPLETE=false
CURRENT_HEAD_VALIDATED=false
HZ23_LKG_CANDIDATE_CONFIRMED=false
HZ24_RUNTIME_MIGRATION_CONFIRMED=false
HZ24_RESUME_ALLOWED=false
MYSQL_INITIALIZATION_ALLOWED=false
PUBLISH_ALLOWED=false
AIDEAL_CPS_SYNC_ALLOWED=false
COMMERCIAL_ENABLED=false
```

## 12. 权威入口

```text
docs/DOCUMENT_AUTHORITY.md
docs/project/CURRENT_PROJECT_CONTEXT.md
docs/project/PROJECT_MEMORY_20260620.md
docs/status/COMMERCIALIZATION_STATUS_20260620.md
docs/project/EXECUTION_TOPOLOGY.md
docs/project/ENVIRONMENT_AND_WORKING_RULES.md
docs/project/CODE_CHANGE_GUARDRAILS.md
docs/project/CODE_CHANGE_GUARDRAILS_IMPLEMENTATION.md
docs/project/NEXT_CHAT_HANDOFF_PROMPT.md
reports/project_engineering_audit_latest.json
reports/offline_quality_latest.json
reports/hz23_round_latest.json
data/export/aideal_cps_products_commercial_candidate_manifest.json
```

冲突时：当前 main 代码与绑定当前 HEAD 的报告 > 2026-06-20 状态 > 本文 > 长期记忆 > 专项设计 > 旧状态快照。