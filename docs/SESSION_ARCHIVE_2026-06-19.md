# DL2 工程会话归档 — 2026-06-19

> 作用：冻结本轮对话形成的设计决策、代码变更、运行事实、未验证项和下一步顺序。本文不是运行报告；运行事实仍以 `reports/`、manifest、GitHub Actions 和现场脱敏日志为准。

## 1. 本轮目标

本轮围绕 HZ24 特殊频道增量采集链路，完成三类工作：

1. 将历史单体脚本拆为可测试、可配置、可恢复的分层实现；
2. 修正“已抢光商品被当成点击技术失败并触发 failure fuse”的业务分类问题；
3. 建立工程审计、静态测试、长期项目记忆和新对话交接文档。

## 2. 已确认业务事实

- 特殊频道共 5 个：超补爆品、限量高佣、秒杀专区、定向高佣、粉丝爱买。
- 商业候选池 3304 SKU，跨频道重复 11 SKU。
- HZ24 增量队列 221 SKU，队列 manifest 保持 `commercial_enabled=false`。
- 最近一次已提交采集结果为 72 linked、149 pending、complete=false。
- 最近批次 processed=7、success=2、fail=5、stop_reason=`item_fail_fuse`。
- 5 个失败样本的页面根文本均包含“已抢光”，点击命中 disabled card；旧实现把业务终态错误计入连续技术失败。
- 目前仍无可证明的完整 validation pass，也未执行生产 importer dry-run。

## 3. 本轮代码与配置变更

### 3.1 HZ24 配置化

已建立或更新：

- `config/hz24-browser.toml`
- `config/hz24-collection.toml`
- `config/hz24-contracts.toml`
- `config/hz24-validation.toml`

已集中配置：CDP host/port/scheme、联盟页面 host、可信短链 scheme/host、商品 host、timeout、批次、sleep、failure fuse、链接生命周期、文件路径、schema、worker、observer service 和验证字段。

### 3.2 HZ24 分层模块

当前 canonical 路径位于 `src/aideal_cps_data_lab/hz24/`，主要职责如下：

- `settings.py`：typed settings 和 TOML/env 装载；
- `browser_contract.py`：DOM 文本、正则与 JS contract；
- `jd_page.py`：CDP/page/tab/card/modal adapter；
- `application.py`：采集用例入口；
- `session.py`：浏览器会话和频道级编排；
- `tab_runner.py`：单频道批处理；
- `outcome_service.py`：linked/unavailable/retryable 分类；
- `link_service.py`：领链和可信短链校验；
- `batch.py`：批次计数和 failure fuse；
- `repository.py`：JSON/JSONL 原子读写和 SKU upsert；
- `records.py`：记录构造、终态识别和稳定 hash；
- `state_store.py`：queue 完整性、checkpoint 和 collection report；
- `validation_io.py`、`validation_config.py`、`validation_rules.py`、`validation_service.py`：文件验证链路。

### 3.3 canonical entrypoint

以下入口已委托统一实现：

- `run/hz24_collect_increment_links.py`
- `run/hz24_collect_increment_links_v2.py`
- `scripts/hz24_validate_increment_links.py`
- `scripts/hz24_validate_increment_outcomes.py`

`_v2` 和旧 validator 当前仅作为兼容入口，不得发展成第二套实现。

### 3.4 已抢光终态

当前 `records.unavailable_reason()` 已定义：

- `sold_out`
- `delisted`
- `not_promotable`

`outcome_service` 先判定 terminal business state，再决定是否进入 link/click 流程；terminal state 不应增加 consecutive technical failures。

### 3.5 测试与 CI

已增加：

- `tests/test_hz24_refactor.py`
- `.github/workflows/hz24-static.yml`
- `.github/workflows/engineering-audit-publish.yml`

测试覆盖了 JSONL SKU upsert、unavailable 集合、已抢光/不可推广分类、failure fuse 重置和 duplicate SKU 索引。

## 4. 当前代码状态的事实等级

### 已验证事实

- 上述文件已存在于 GitHub `main`。
- 221 队列及 72 linked / 149 pending 报告已提交。
- 全仓最新工程审计报告记录 `blocker_count=605`、`files_scanned=243`；该数字主要反映 HZ11–HZ23 历史脚本债务，不代表 HZ24 有 605 个直接运行故障。

### 代码已实现但未现场验证

- 新 HZ24 模块的 compile/unit 结果尚需以最新 GitHub Actions 状态确认。
- 已抢光不计 failure fuse 尚未用杭州采集机当前授权会话重新跑最小批次证明。
- 新 validation service 尚未基于完整 221 accounting 产生 pass 报告。

### 设计已确定但仍未完成

- STOP_REQUIRED 机器可读合同和 supervisor 禁止自动重启机制；
- linked/unavailable repository 互斥写保护；
- 单进程 lock；
- validator 去除 `JDPageAdapter`/HZ21 动态加载依赖，改为纯 URL validator；
- 最终 checkpoint 的完整回归测试；
- HZ21 历史 adapter 的正式通用协议替代；
- 生产 importer dry-run、landed validation 和 rollback evidence。

## 5. 已发现但尚未闭环的工程问题

1. `validation_service` 当前构造 `JDPageAdapter` 只为复用可信 URL 判断，导致纯文件 validator 仍加载 HZ21 adapter；需要拆出纯函数。
2. `application.py` 已生成最终 report，但最终 checkpoint 需要在测试中明确证明 `complete/pending/stop_reason` 正确持久化。
3. JSONL repository 已按 SKU upsert，但 linked 与 unavailable 对侧旧记录尚无统一互斥事务。
4. 当前没有 collector 进程锁，手工、timer、supervisor 并发可能造成覆盖写。
5. `scripts/hz24_run_one_increment_batch.sh` 已读取 observer service 配置，但异常路径的 observer 恢复应进一步使用 trap/finally 收口。
6. 全仓工程审计仍混合“当前主线 blocker”和“legacy debt”；后续报告应增加分域统计和主线 gate。

## 6. 环境与协作约束

- 杭州采集机：`121.41.111.36` / `cpsdata` / `/home/cpsdata/projects/aideal-cps-data-lab`，CDP `127.0.0.1:19228`。
- 杭州生产机：`8.136.28.6` / `deploy` / `/home/deploy/projects/aideal-cps`，禁止运行浏览器自动化和登录京东联盟。
- 新加坡开发机：`43.106.55.255` / `cpsdev`，不是当前 DL2 双主采集源。
- 京东联盟只允许人工登录；账号密码、Cookie、session、二维码、HAR、HTML、原始账户页面不得写入代码、聊天、日志或 GitHub。
- 默认由 ChatGPT 直接读取和修改 GitHub；用户只执行必须访问本机会话/systemd 的最小命令。
- Linux 命令不使用 `set -e`；输出写入 `logs/` 或 `run/`，屏幕只 tail 关键 80–180 行。

## 7. 固定工程原则

- `main` 是唯一主流分支。
- 同一能力只有一个 canonical implementation。
- 备份使用 tag、release、artifact、快照，不维护长期 v2/v3/backup 平行实现。
- entrypoint 薄、配置分离、分层解耦、幂等、可恢复、可审计、fail closed。
- 采集、验证、导入独立；Data Lab 不直接写生产 MySQL。
- 采集成功不等于可商用；必须经过完整 accounting、validation、dry-run、显式批准、landed validation 和 rollback gate。

## 8. 后续固定顺序

1. Phase A：查询最新 HZ24 Actions，修复 compile/import/unit；补齐纯 URL validator、互斥写、STOP_REQUIRED、lock、最终 checkpoint 测试。
2. Phase B：杭州采集机 2–3 SKU 授权 smoke，仅验证正常 linked、已抢光 unavailable、state/report/exit code。
3. Phase C：按 20–35 小批次完成 221 accounting，要求 linked + unavailable = 221、pending=0、overlap=0。
4. Phase D：运行 canonical validation，要求 `merge_allowed=true`；`commercial_enabled` 仍保持 false。
5. Phase E：杭州生产机 importer dry-run、显式批准、幂等导入、landed validation、回滚演练。
6. Phase F：通用商用调度、refresh queue、运行质量报告和 HZ11–HZ23 退役。

## 9. 新对话第一动作

不要直接运行 221 SKU。先读取本文件和权威文档，然后查询最新 HZ24 workflow/commit 状态；以第一个 compile 或 unit failure 为单一问题进行修复。只有静态基线全绿，才进入杭州授权 smoke。
