# DL2 当前进展与下一步计划 V2

> 截止：2026-06-19。本文覆盖 `CURRENT_PROGRESS.md` 中已经过时的工程审计数字；业务采集结果仍以版本化报告为准。

## 1. 当前结论

HZ24 已完成特殊频道结构分析、221 SKU 增量队列、主要分层重构、终态分类、文件幂等、验证服务和静态测试框架；但尚未完成当前 GitHub HEAD 下的静态全绿证明、杭州授权最小 E2E、221 SKU 全量 accounting、validation pass 和生产 importer dry-run，因此不能标记为可商用。

## 2. 已验证事实

- 特殊频道：5 个。
- 商业候选池：3304 SKU。
- 跨频道重复：11 SKU。
- HZ24 增量队列：221 SKU，`commercial_enabled=false`。
- 最近提交结果：72 linked、149 pending、complete=false。
- 最近批次：processed=7、success=2、fail=5、stop_reason=`item_fail_fuse`。
- 5 个失败样本均有“已抢光”页面证据并命中 disabled card；旧运行错误归类为技术点击失败。
- 最新全仓工程审计：605 blocker、243 files scanned。该数字主要是 HZ11–HZ23 历史债务，不是 HZ24 直接故障数。

## 3. 代码已实现但仍待验证

- typed settings、TOML/env 配置化；
- browser/application/session/tab/outcome/link/repository/state/validation 分层；
- JSON/JSONL 原子写、SKU upsert、queue hash/row-count 校验；
- linked/unavailable/pending accounting；
- sold_out、delisted、not_promotable；
- failure fuse、可信短链、record hash、manifest/report；
- canonical collector/validator entrypoint；
- HZ24 unit tests 和 static workflow。

## 4. 当前阻断项

### P0

1. 最新 HZ24 Actions 状态尚未在交接文档中形成全绿证据。
2. 当前代码尚未在杭州采集机完成 2–3 SKU 授权 smoke。
3. 221 SKU 尚未完成 accounting。
4. 尚无 `merge_allowed=true` 的完整 validation report。
5. 尚未执行生产 importer dry-run、显式批准、landed validation 和 rollback。

### P1

1. validator 仍通过 `JDPageAdapter` 复用可信 URL 判断，应改为纯函数。
2. linked/unavailable 缺少 repository 互斥写保护。
3. 缺少 collector 单进程 lock。
4. STOP_REQUIRED 文件合同和 supervisor 禁止自动重启仍不完整。
5. 最终 checkpoint 缺少明确回归测试。
6. 批次 shell 的 observer 恢复应使用 trap/finally 语义。
7. HZ21 adapter 仍是历史兼容依赖。

## 5. 下一步固定顺序

### Phase A：静态基线

- 查询最新 HZ24 Actions/job log。
- 修复首个 compile/import/unit failure。
- 补纯 URL validator、互斥写、STOP_REQUIRED、lock、最终 checkpoint 测试。
- 完成标准：compile、unit/contract、Actions 全绿。

### Phase B：杭州 2–3 SKU 授权 smoke

- 人工确认登录会话。
- 只读 session/risk smoke。
- 1 个正常 SKU、1 个已抢光 SKU，batch limit 2–3。
- 正常 SKU 必须得到可信短链；已抢光必须进入 unavailable；不增加 failure fuse。

### Phase C：221 accounting

- 复用已有 72 linked。
- 每批 20–35，终态不重试。
- 完成标准：linked + unavailable = 221、pending=0、overlap=0。

### Phase D：validation candidate

- 运行 canonical validation。
- 要求 queue hash、row count、JSON、duplicate、extra、overlap、trusted URL、required fields、record hash、source tab 全部通过。
- `merge_allowed=true`；`commercial_enabled` 仍保持 false。

### Phase E：生产 dry-run 与导入

- 杭州生产机只消费固定 commit/artifact。
- dry-run 输出 insert/update/skip/reject。
- 显式批准后幂等写入。
- landed validation 和 rollback evidence 必须留存。

### Phase F：通用商用

- 安全调度、refresh queue、运行质量报告。
- 逐步退役 HZ11–HZ23，仅保留 canonical collector/validator/importer。

## 6. 新对话第一动作

不要执行 221 SKU 全量采集。先查询最新 HZ24 workflow 和失败日志，以第一个静态错误为单一问题修复。
