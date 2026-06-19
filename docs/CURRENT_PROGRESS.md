# DL2 当前进展与商用推进计划

> 截止：2026-06-19  
> 结论：**HZ24 已完成结构分析、增量队列和主要工程化重构，但尚未完成当前代码版本下的杭州授权 E2E、全量 accounting、验证门禁和生产 dry-run，因此不能标记为已商用。**

## 1. 已验证的业务与数据事实

### 1.1 特殊频道结构与候选池

GitHub 已保存的报告显示：

- 特殊频道共 5 个：超补爆品、限量高佣、秒杀专区、定向高佣、粉丝爱买。
- 频道重叠分析报告 `analysis_ready=true`、`ok=true`。
- 商业候选池 SKU 数：`3304`。
- 特殊频道之间跨频道重复成员：`11` 个，集中在“秒杀专区”和“粉丝爱买”。
- 每个特殊频道均确认存在、可识别，并按当次报告判定为单页稳定结构。
- 增量队列 manifest：`221` 行，`commercial_enabled=false`，并绑定数据 SHA-256 和结构 SHA-256。

这说明 HZ24 增量范围已形成确定的数据集合，但不代表 221 个 SKU 已全部获得有效推广链接。

### 1.2 最近一次已提交采集报告

`reports/hz24_increment_collection_latest.json` 的现场结果：

- queue：`221`
- 已成功生成链接：`72`
- pending：`149`
- 最近批次 processed：`7`
- 最近批次 success：`2`
- 最近批次 fail：`5`
- stop reason：`item_fail_fuse`
- complete：`false`
- risk：空数组

5 个失败样本的页面根文本均包含“已抢光”，点击命中 `card-disabled`，但旧运行结果仍把它们记为 `click_failed` 并触发连续失败熔断。这是当前最明确的业务分类缺陷证据。

## 2. 代码已实现但尚待杭州现场复验

HZ24 已从大脚本向分层模块重构，当前代码包含：

- typed settings 和 TOML 配置分离；
- 浏览器/CDP、频道、timeout、sleep、schema、路径、service 名称配置化；
- 页面适配、session、tab runner、outcome、link、repository、state、validation 分层；
- JSON/JSONL 原子写入；
- SKU 级 upsert 与去重；
- queue hash 和 row-count 完整性校验；
- linked/unavailable/pending accounting；
- `sold_out`、`delisted`、`not_promotable` 终态分类；
- 连续技术失败熔断；
- 可信短链 scheme/host 校验；
- record hash、manifest、validation report；
- HZ24 单元测试和 GitHub Actions 静态 workflow；
- 原 `run/hz24_collect_increment_links.py` 与 `_v2.py` 已委托同一 application service；
- 两个 validator 入口已委托同一 validation service。

其中，“已抢光不再计入技术失败”已经体现在当前 `records.unavailable_reason()` 和 outcome service 的设计中，但尚未用当前 GitHub HEAD 在杭州采集机重新跑最小批次证明。

## 3. 当前已知工程缺口

按优先级排序：

### P0：商用阻断项

1. **当前代码版本未完成杭州授权 smoke/E2E**  
   需要先用 1–3 个 SKU 验证：配置加载、CDP 连接、频道切换、已抢光终态、正常短链、checkpoint 和退出码。

2. **221 个 SKU 未完成 accounting**  
   当前持久化结果为 72 linked + 149 pending；没有最新 unavailable 计数和完整验证报告。

3. **STOP_REQUIRED 机制不完整**  
   设计要求风险/登录失效写机器可读 STOP 文件并阻止 supervisor 自动重启；当前主线主要依赖 stop reason 和退出码，需完成统一 stop-state contract。

4. **尚无可证明的 validation pass**  
   `reports/hz24_increment_validation_latest.json` 当前未提交。必须在 accounting 完整后生成，并要求 `merge_allowed=true`。

5. **生产 importer 未进入本轮执行**  
   Data Lab 结果尚未执行生产 dry-run、landed validation 或显式商用发布。

### P1：可靠性与解耦

1. validation service 当前为了复用可信 URL 判断而构造 `JDPageAdapter`；应改为纯 URL validator，避免验证层加载 HZ21 页面适配依赖。
2. application 需要确保最终状态也写入 checkpoint，包括 `complete`、最终 pending 和 stop reason。
3. linked/unavailable 互斥写入需要 repository 层防护：一种结果落盘时，应检测并拒绝/清理对侧旧记录。
4. 缺少进程级 lock，需防止 supervisor、手工命令或重复 timer 同时写同一 JSONL。
5. HZ21 兼容 adapter 仍是依赖，应逐步抽取真正通用的点击/modal 协议，避免 HZ24 被历史脚本实现牵制。
6. URL 构造仍有少量字符串拼接，应统一通过配置与 URL builder。

### P2：全仓工程债

- 最新工程审计报告仍有 `390` 个 blocker，主要来自 HZ11–HZ23 历史 `run/` 脚本的大文件、重复实现和硬编码。
- 该数字是全仓历史债，不等于当前 HZ24 主线有 390 个直接运行故障。
- 后续应把审计拆为：
  1. 当前商用主线阻断门禁；
  2. legacy debt 清单；
  3. 逐阶段退役计划。
- 不应为了全仓 blocker 清零而停止 HZ24 的安全收口，但任何进入生产的主线路径必须无 blocker。

## 4. 下一步实施计划

### Phase A：冻结事实与静态基线

目标：确保 GitHub HEAD 自洽，不触碰京东账号。

1. 编译 HZ24 全部模块和入口。
2. 运行 `tests/test_hz24_refactor.py` 及相关 repository/contract 测试。
3. 增加测试：
   - card-disabled + 已抢光 → unavailable，不增加 failure fuse；
   - linked/unavailable 互斥；
   - 风险 stop state；
   - 最终 checkpoint；
   - validator 不加载浏览器 adapter。
4. 记录 CI commit 和结果；失败先修复，不进入现场采集。

完成标准：HZ24 static workflow 通过，主线测试无失败。

### Phase B：杭州授权最小 smoke

目标：验证当前代码，而不是继续全量跑。

顺序固定：

1. 人工确认京东联盟会话有效。
2. 只读 session/risk smoke。
3. 选 1 个正常可推广 SKU。
4. 选 1 个已抢光 SKU。
5. batch limit 设置为 2–3。
6. 检查 linked、unavailable、state、collection report 和退出码。
7. 出现验证码/滑块/登录失效立即 STOP_REQUIRED。

完成标准：正常 SKU 得到可信短链；已抢光 SKU 进入 unavailable；不触发技术 failure fuse；无风险事件。

### Phase C：完成 221 SKU accounting

1. 复用已有 72 linked，按持久化结果重建 pending。
2. 小批次运行，每批 20–35，批间等待由配置控制。
3. 每批后提交非敏感 collection report/manifest；不提交页面原文和会话信息。
4. 对连续失败只处理可重试项，终态不再重试。
5. 完成后要求：linked + unavailable = 221、pending = 0、overlap = 0。

### Phase D：验证与候选发布

1. 运行 canonical validation service。
2. 检查 queue hash、row count、duplicate、extra、overlap、trusted URL、required fields、record hash 和 source tab。
3. 生成 outcome manifest。
4. 只有 `merge_allowed=true` 时，才可生成“validated candidate”。
5. `commercial_enabled` 仍保持 false，直到生产 dry-run 审批。

### Phase E：生产 dry-run 与受控导入

在杭州生产机执行，但不运行任何浏览器自动化：

1. 拉取已验证 artifact/commit。
2. 验证 manifest/hash。
3. importer dry-run，输出 insert/update/skip/reject。
4. 对价格、佣金、短链、过期时间和 payload hash 做样本核验。
5. 显式批准后执行幂等批量写入。
6. landed validation 和回滚演练。

### Phase F：通用商用运行

- systemd timer/supervisor 只负责安全调度，不绕过人工登录和风控。
- 链接到期前进入 refresh queue。
- 每轮产出运行摘要、数据质量和异常分类。
- 逐步退役 HZ11–HZ23 遗留并行脚本，只保留 canonical collector/validator/importer。

## 5. 新对话第一项任务

不要直接全量采集。先完成 **Phase A：确认当前 GitHub HEAD 的 HZ24 静态测试状态，并修复所有 HZ24 主线 compile/unit 问题**。完成后再给杭州采集机的 2–3 SKU 最小 smoke 步骤。
