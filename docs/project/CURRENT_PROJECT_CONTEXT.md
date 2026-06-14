# AIdeal CPS Data Lab 当前项目上下文

更新日期：2026-06-14

状态：当前主线权威文档。新对话必须先读本文，再读本文引用的专项文档。

## 1. 项目目标

AIdeal CPS Data Lab 负责从京东联盟“商品推广 -> 全部商品”4000 条商品池中获取可推广商品，生成带佣金归因的推广短链，持续刷新商品价格、佣金、状态和时间戳，并向 AIdeal CPS 商用微信导购系统提供可靠的佣金商品数据。

本项目不是面向终端用户的业务系统。终端用户访问、推荐、点击归因、订单和返佣均由 `ShanGouXueHui/aideal-cps` 负责。

## 2. 当前已验证主链路

### HZ21/HZ22

已经验证并完成：

1. 自动进入京东联盟商品推广页面；
2. 精确点击“全部商品”；
3. 确认页面为“共 4000 条”商品池；
4. 使用 4000 条商品池对应分页器跳转指定页；
5. 通过 SKU 所在真实商品卡片和真实鼠标/Pointer 链路执行“一键领链”；
6. 生成 `https://u.jd.com/...` 推广短链；
7. 按 SKU 去重并保留已验证数据；
8. 遇到真正的京东验证信号时安全停止，不绕过验证；
9. 每页保存进度，支持断点继续。

HZ22 已完成 page 61-67，结果：

```text
commercial_segment_complete=true
completed_pages=[61,62,63,64,65,66,67]
unfinished_pages=[]
stop_reason=null
本轮新增成功=162
本轮失败=5
可信推广短链 SKU=2385
```

当前准确口径是：

```text
京东展示池=4000 条
已生成并验证推广短链的可信商品=2385 条
```

不得把 4000 条展示池误写为 4000 条全部已入库。

## 3. HZ23 生产观察层

HZ23 已安装为 systemd 服务：

```text
aideal-hz23-observer.service
```

固定策略：

- 服务器本地时间 09:30-21:30 才操作京东页面；
- 夜间只写心跳，不操作浏览器；
- 每天随机从 1、17、34、50、67 页中选择一页进行只读健康探针；
- 完整刷新成功后，随机间隔 3-5 天启动下一轮；
- 新商品领链等待随机 3-7 秒；
- 页面等待随机 90-210 秒；
- 强风控信号仅包括 `risk_handler`、京东验证、快速验证、安全验证、验证码、滑块；
- “购物无忧”等普通页面文案不得作为风控信号；
- 遇到强风控立即停止并保存断点，不尝试绕过。

### 已完成的首次探针

GitHub 已确认 2026-06-14 10:05 的首次探针完成：

```text
目标页=50
全部商品池=4000 条
扫描卡片=59
risk=[]
prepare ok=true
scan ok=true
```

对应提交：

```text
7aeb147 docs: publish HZ23 daily observation probe
```

探针报告中 `new=59` 表示 HZ23 本地目录索引首次初始化 59 条，不表示重新生成 59 条推广链接。

### 尚未完成的首次全量观察轮次

首次 HZ23 1-67 页全量轮次计划时间：

```text
2026-06-15 09:56 server-local
```

截至本文更新时，GitHub 尚未出现完整轮次完成报告，因此：

```text
商用观察尚未最终通过
正式商用发布尚未启用
MySQL 正式迁移尚未执行
```

终端断开不影响已完成的首次探针，因为探针报告和提交已经落到 GitHub。终端断开后是否完成全量轮次，必须以 GitHub 中新的 `reports/hz23_round_*`、manifest 和提交为准，不能凭进程 PID 猜测。

## 4. 当前数据存储事实

当前运行数据主要是：

```text
data/import/*.jsonl          已验证推广链接历史与 latest
data/state/                  HZ23 本机状态和目录索引
data/history/                商品字段变化历史
data/export/                 候选/正式导出文件
reports/                     运行和验收报告
logs/                        本机运行日志
```

当前尚没有正式 Data Lab MySQL 数据库。因此此前文档中“没有可提供的数据库账号”在当前阶段是事实。

但是最终商用架构已经调整：

- 观察期继续使用 JSONL + manifest，作为备份、审计和迁移输入；
- HZ23 商用验收通过后，立即建设 Data Lab 本地 MySQL；
- MySQL 成为佣金商品在线同步的主数据源；
- JSONL 保留为原子快照、灾备和审计出口。

权威设计见：

```text
docs/architecture/COMMISSION_DATA_MYSQL_SYNC_V1.md
```

## 5. 商用验收门槛

至少满足：

1. HZ23 服务持续稳定运行 48-72 小时；
2. 至少两个每日探针成功；
3. 至少一个完整 1-67 页轮次成功；
4. 完整轮次：
   - `commercial_segment_complete=true`
   - `unfinished_pages=[]`
   - `stop_reason=null`
5. 一轮扫描覆盖至少 3900 个唯一 SKU；
6. 推广短链数据无重复 SKU；
7. 没有 HZ20 不安全数据重新进入可信池；
8. 生成候选 manifest 且 checksum、行数和 schema 均通过；
9. MySQL 迁移演练和回滚测试通过；
10. AIdeal CPS 只读取其本地 MySQL，用户请求不依赖远程 Data Lab。

## 6. 下一步计划

### Phase A：观察期间立即准备

1. 继续观察 HZ23 服务；
2. 从 GitHub读取第二次探针和首次全量轮次报告；
3. 创建 Data Lab MySQL migration/DDL；
4. 创建持久化层和 Repository 接口；
5. 实现 JSONL -> MySQL 一次性回填，要求幂等；
6. 实现采集结果对 JSONL 和 MySQL 的一致性校验；
7. 创建只读数据库用户和短生命周期 SSH Tunnel 访问方案；
8. 在 AIdeal CPS 准备定时同步器，但保持 disabled/dry-run。

### Phase B：观察通过后执行

1. 初始化 Data Lab MySQL 正式 schema；
2. 回填当前 2385+ 条可信商品；
3. 校验数据库行数、短链、SKU 去重、金额字段和时间戳；
4. HZ23 改为事务性写 MySQL，同时继续生成 JSONL 快照；
5. 发布只读视图 `v_published_commission_products`；
6. AIdeal CPS 通过短生命周期 SSH Tunnel 定时同步到本地 `aideal_cps.products`；
7. 灰度验证推荐和推广跳转；
8. 验收后启用商用同步。

## 7. 重要风险和约束

- 京东页面 DOM、分页和卡片结构可能变化；必须以严格页面探针判断，不可静默采集错误频道。
- 推广短链可能存在有效期；必须保留 `link_expire_at`、`refresh_due_at` 和刷新策略。
- 商品价格和佣金变化时，需要更新业务字段；未变化时只更新时间戳，避免无意义写入。
- 商品连续两次完整轮次未出现才可标记 inactive，不能因单次页面异常下架。
- 自动化测试不能调用 JD live API；JD live 仅用于真实浏览器流量或明确手工 smoke。
- 禁止提交 Cookie、浏览器 Profile、数据库密码、SSH 私钥、京东账号资料。

## 8. 权威文档索引

```text
docs/project/CURRENT_PROJECT_CONTEXT.md
docs/project/ENVIRONMENT_AND_WORKING_RULES.md
docs/architecture/COMMISSION_DATA_MYSQL_SYNC_V1.md
docs/ops/DL2_HZ23_COMMERCIAL_OBSERVATION_PLAN.md
docs/project/NEXT_CHAT_HANDOFF_PROMPT.md
docs/contracts/AIDEAL_CPS_PRODUCT_FEED_V1.md
docs/contracts/aideal-cps-product-feed-v1.schema.json
docs/contracts/aideal-cps-product-feed-manifest-v1.schema.json
```

发生冲突时，优先级：

1. 当前代码和最新可验证运行报告；
2. `CURRENT_PROJECT_CONTEXT.md`；
3. MySQL V1 架构文档；
4. HZ23 观察计划；
5. 旧 JSONL/rsync 合同仅作为过渡和灾备参考。
