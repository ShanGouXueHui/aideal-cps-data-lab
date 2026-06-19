# DL2 环境与运作手册

> 最后更新：2026-06-19  
> 本文只记录非密钥环境事实、系统边界和标准运作方式。账号、密码、Cookie、session、数据库密码和私钥不得进入 GitHub。

## 1. 环境矩阵

| 环境 | 主机/用户 | 项目路径 | 用途 | 禁止事项 |
|---|---|---|---|---|
| 杭州采集 | `121.41.111.36` / `cpsdata` | `/home/cpsdata/projects/aideal-cps-data-lab` | 京东联盟人工登录、授权页面采集、Data Lab 验证与候选发布 | 不绕过门禁写生产库；不提交会话与原始账户页面 |
| 杭州生产 | `8.136.28.6` / `deploy` | `/home/deploy/projects/aideal-cps` | AIdeal CPS 生产服务、受控 importer/sync、landed validation | 禁止浏览器自动化、禁止登录京东联盟 |
| 新加坡开发 | `43.106.55.255` / `cpsdev` | 以目标仓库文档为准 | `aideal-cps` 开发、非生产测试 | 不作为当前 DL2 双主采集源 |

杭州采集机规格：2C / 4G / 50G。

## 2. 浏览器与人工会话

杭州采集机当前浏览器通道：

- Chrome CDP：`127.0.0.1:19228`
- noVNC：`18772`
- x11vnc：`59072`

标准流程：

1. 人工通过 noVNC 查看并登录京东联盟。
2. 自动化仅连接现有授权浏览器/CDP，不保存账号密码。
3. 每次采集前先做只读 risk/session smoke。
4. 页面出现验证码、滑块、安全验证、登录页或身份不确定时立即停止。
5. 写 STOP_REQUIRED/停止原因，禁止 supervisor 无限重启。
6. 人工恢复会话后，从只读 smoke 重新开始，不能直接恢复全量批次。

## 3. 周边系统

### 3.1 京东联盟网页

- Data Lab 只操作经授权的联盟后台页面。
- 页面结构属于外部不稳定依赖，所有 selector 和文本识别必须集中在 adapter/contract 层。
- 不允许把页面变化直接扩散到领域模型、repository、validator 或 importer。
- 自动化测试不得登录真实联盟页面；真实页面只用于人工授权 smoke/E2E。

### 3.2 HZ23 observer

- 当前 service 名称由 `config/hz24-contracts.toml` 配置为 `aideal-hz23-observer.service`，运行时以配置为准。
- 执行 HZ24 单批次时，如 observer 原先为 active，应先安全暂停，批次结束后恢复原状态。
- 无论采集成功、失败还是风险退出，都必须执行恢复逻辑；应使用 trap/finally 级保证防止服务遗留停止。
- 风险退出后不应自动恢复采集循环，需由 STOP_REQUIRED 状态控制。
- observer/supervisor、nohup 和手工任务不得同时写同一队列结果；collector 必须有进程级 lock。

### 3.3 Data Lab MySQL 目标

以下属于目标架构；当前是否已初始化、DDL 是否已执行、数据是否已回填必须现场核验：

- 数据库：`aideal_cps_data_lab`
- 目标表：
  - `commission_products`
  - `commission_refresh_runs`
  - `commission_product_history`
  - `commission_publish_versions`
- 发布视图：`v_published_commission_products`
- 只监听 `127.0.0.1:3306`，不开放公网 3306。
- write、dual-write、publish 和 consumer sync 开关默认关闭。
- Data Lab 数据库不直接服务终端用户请求。

### 3.4 AIdeal CPS 生产系统与 MySQL

- 项目：`/home/deploy/projects/aideal-cps`
- 本地业务库：MySQL `aideal_cps`。
- 终端用户请求始终读取生产本地 MySQL，不实时访问 Data Lab。
- 生产环境不接收浏览器会话、Cookie、页面截图、HTML 或 HAR。
- 生产导入不得通过临时 SQL、共享工作目录或无合同复制绕过 dry-run 和 validation。

每个发布版本只允许选择一条 canonical delivery path：

1. validated JSONL/artifact → importer → AIdeal CPS 本地 MySQL；或
2. Data Lab published view → 短生命周期 SSH Tunnel sync → AIdeal CPS 本地 MySQL。

Tunnel 目标约定：生产机 `127.0.0.1:13306` → `cpsdata@121.41.111.36` → Data Lab `127.0.0.1:3306`。同步完成后关闭 Tunnel。

两条路径不得作为两套互相漂移的生产主线并行维护。无论选择哪条路径，都必须经过 manifest/hash、dry-run、样本核验、显式批准、幂等写入、landed validation 和回滚证据。

### 3.5 AI 模型系统

- DL2 采集、解析、金额、佣金、短链、hash、去重和验证链路不依赖 AI 模型。
- 推荐、对话和模型路由属于 `aideal-cps`。
- 本仓库只提供结构化、版本化、带来源证据的数据输入。
- ZenMux 已排除，除非用户明确重新开放。

## 4. GitHub 作为事实源

默认工作方式：

1. 先读取 GitHub 当前代码、配置、报告、manifest、workflow 和交接文档。
2. 文档和代码由 ChatGPT 直接修改 GitHub，避免用户执行超长 heredoc。
3. 所有结论注明来源等级：代码存在、CI 通过、现场日志通过、完整 E2E 通过。
4. 运行报告可提交 GitHub，但必须脱敏且不包含账户页面原文。
5. `logs/` 的详细运行日志通常留在服务器；提交 GitHub 的是结构化 summary/report，而不是完整敏感日志。
6. 每次 GitHub 写入后使用 `fetch_file`、commit 或服务器 `git log` 二次确认。

从 GitHub 查询运行状态时优先顺序：

1. `reports/*latest.json`
2. `data/export/*manifest.json`
3. GitHub Actions run、job、step 和 log
4. 最近相关 commit
5. 只有 GitHub 无法确认时，才让用户从服务器 tail 指定日志

combined status 或 PR-triggered workflow runs 为空，不能自动解释为 CI 通过或失败；应查询目标 workflow 最近实际 run，必要时使用 `workflow_dispatch`。

## 5. 用户现场执行规范

只有必须访问人工登录会话、systemd、MySQL localhost 或服务器本地文件时，才要求用户执行命令。

每轮命令：

- 不使用 `set -e`；
- 一次只做一个目标；
- 先 `pwd` 和 `git status --short`；
- 不通过 shell 直接改大文件；
- 输出重定向到 `logs/`、`run/` 或 `reports/`；
- 最后只显示关键摘要、tail 80–180 行或最终 SUMMARY；
- 报告路径和退出码必须明确；
- 出现风险立即停止，不继续给下一组采集命令。

## 6. 标准运行阶段

### 6.1 静态阶段

不需要京东登录：

- 配置 parse；
- Python compile/import；
- unit/contract test；
- queue/manifest hash 校验；
- validator 对固定 fixture 的测试；
- 不连接 JD live、不连接生产数据库。

### 6.2 授权 smoke 阶段

需要杭州采集机人工会话：

- CDP 连接；
- 页面 host 与登录态；
- 风险标记；
- 单频道定位；
- 1 个正常 SKU；
- 1 个 terminal unavailable SKU；
- state/report/STOP_REQUIRED/exit code；
- observer 原状态恢复。

### 6.3 批次阶段

- 每批 20–35 个；
- SKU 终态后 checkpoint；
- 批次间等待配置化；
- 连续技术失败熔断；
- terminal state 不进入失败熔断；
- 风险立即 STOP_REQUIRED；
- linked/unavailable repository 互斥；
- 单进程 lock 防止并发双写。

### 6.4 验证阶段

- 全量 accounting；
- JSONL 合法性；
- queue/output hash；
- duplicate/extra/overlap；
- trusted URL；
- required fields；
- record hash；
- source tab；
- manifest `merge_allowed`；
- validator 为纯文件/纯配置逻辑，不加载浏览器或生产数据库。

### 6.5 生产交付阶段

只在杭州生产机：

- 固定 commit/artifact 或固定 published version；
- manifest/hash 校验；
- importer/sync dry-run；
- insert/update/skip/reject 汇总；
- 价格、佣金、短链、过期时间和 payload hash 样本核验；
- 显式批准；
- 幂等写入；
- landed validation；
- 回滚验证。

### 6.6 商用稳定阶段

- 至少一周稳定运行；
- timer/supervisor 与 STOP_REQUIRED 语义验证；
- refresh queue 与链接生命周期；
- 质量指标和异常分类；
- 显式批准打开商用发布。

## 7. 故障处理

### 风控/验证码/登录失效

- 分类：`risk/session failure`
- 动作：立即停止、写 STOP_REQUIRED、禁止自动重启、人工处理。

### 页面元素变化

- 分类：`adapter contract failure`
- 动作：只修改页面 contract/adapter，加 fixture 和回归测试，不修改数据合同含义。

### 点击失败

- 先检查是否为 sold out/delisted/not promotable。
- terminal state 直接记录 unavailable。
- 只有确认不是 terminal state，才计入 retryable failure。

### queue/hash/schema 错误

- 分类：`configuration/integrity failure`
- 动作：fail closed；重新生成 queue/manifest 或修复合同，禁止忽略错误继续商业采集。

### 并发写入

- 分类：`process/data integrity failure`
- 动作：立即停止第二个 writer；保留 lock、PID、state 和报告证据；不得合并两个并发结果后假装完整。

### 生产导入差异

- 分类：`import/landed validation failure`
- 动作：停止后续批次；保留 dry-run/import report；按 source run/round 回滚或修复，不手工临时 SQL 补数据。

## 8. 备份与恢复

- 代码备份：Git tag / GitHub Release，不维护平行主分支。
- 数据制品备份：固定 commit 对应的 JSONL、manifest、validation report artifact。
- 数据库备份：由受控备份机制负责，导入前后记录批次边界、source run/round 和 payload hash。
- 会话不备份到 GitHub；Cookie/session 仅保留在受控采集机运行环境。
- 恢复必须从明确的 queue hash、record hash、published version、source run/round 和 checkpoint 开始。
