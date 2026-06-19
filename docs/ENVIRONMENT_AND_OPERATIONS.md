# DL2 环境与运作手册

> 最后更新：2026-06-19  
> 本文只记录非密钥环境事实、系统边界和标准运作方式。账号、密码、Cookie、session 和生产数据库凭证不得进入 GitHub。

## 1. 环境矩阵

| 环境 | 主机/用户 | 项目路径 | 用途 | 禁止事项 |
|---|---|---|---|---|
| 杭州采集 | `121.41.111.36` / `cpsdata` | `/home/cpsdata/projects/aideal-cps-data-lab` | 京东联盟人工登录、授权页面采集、Data Lab 验证与导出 | 不写生产库；不提交会话与原始账户页面 |
| 杭州生产 | `8.136.28.6` / `deploy` | `/home/deploy/projects/aideal-cps` | AIdeal CPS 生产服务、受控 importer | 禁止浏览器自动化、禁止登录京东联盟 |
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
5. 人工恢复会话后，从只读 smoke 重新开始，不能直接恢复全量批次。

## 3. 周边系统

### 3.1 京东联盟网页

- Data Lab 只操作经授权的联盟后台页面。
- 页面结构属于外部不稳定依赖，所有 selector 和文本识别必须集中在 adapter/contract 层。
- 不允许把页面变化直接扩散到领域模型、repository 或 importer。

### 3.2 HZ23 observer

- 当前 service 名称由 `config/hz24-contracts.toml` 配置为 `aideal-hz23-observer.service`。
- 执行 HZ24 单批次时，如 observer 原先为 active，应先安全暂停，批次结束后恢复原状态。
- 无论采集成功、失败还是风险退出，都必须执行恢复逻辑；长期应使用 trap/finally 形式防止服务遗留停止。
- 风险退出后不应自动恢复采集循环，需由 STOP_REQUIRED 状态控制。

### 3.3 生产系统与 MySQL

- 生产系统只消费经过验证的数据制品或 controlled importer。
- Data Lab 不通过 SSH 脚本、共享目录或直接数据库连接绕过合同。
- 生产环境不接收浏览器会话、Cookie、页面截图、HTML 或 HAR。

### 3.4 AI 模型系统

- DL2 采集和验证链路不依赖 AI 模型。
- 推荐、对话和模型路由属于 `aideal-cps`。
- 本仓库只提供结构化、版本化、带来源证据的数据输入。

## 4. GitHub 作为事实源

默认工作方式：

1. 先读取 GitHub 当前代码、配置、报告和交接文档。
2. 文档和代码由 ChatGPT 直接修改 GitHub，避免用户执行超长 heredoc。
3. 所有结论注明来源等级：代码存在、CI 通过、现场日志通过、完整 E2E 通过。
4. 运行报告可提交 GitHub，但必须脱敏且不包含账户页面原文。
5. `logs/` 的详细运行日志通常留在服务器；提交 GitHub 的是结构化 summary/report，而不是完整敏感日志。

从 GitHub 查询运行状态时优先顺序：

1. `reports/*latest.json`
2. `data/export/*manifest.json`
3. GitHub Actions 状态和 job log
4. 最近相关 commit
5. 只有 GitHub 无法确认时，才让用户从服务器 tail 指定日志

## 5. 用户现场执行规范

只有必须访问人工登录会话、systemd 或本机文件时，才要求用户执行命令。

每轮命令：

- 不使用 `set -e`；
- 一次只做一个目标；
- 先 `pwd` 和 `git status --short`；
- 不通过 shell 直接改大文件；
- 输出重定向到 `logs/`；
- 最后只显示关键摘要或 tail 80–180 行；
- 报告路径和退出码必须明确；
- 出现风险立即停止，不继续给下一组采集命令。

## 6. 标准运行阶段

### 6.1 静态阶段

不需要京东登录：

- 配置 parse；
- Python compile/import；
- unit/contract test；
- queue/manifest hash 校验；
- validator 对固定 fixture 的测试。

### 6.2 授权 smoke 阶段

需要杭州采集机人工会话：

- CDP 连接；
- 页面 host 与登录态；
- 风险标记；
- 单频道定位；
- 1 个正常 SKU；
- 1 个 terminal unavailable SKU；
- state/report/exit code。

### 6.3 批次阶段

- 每批 20–35 个；
- SKU 终态后 checkpoint；
- 批次间等待配置化；
- 连续技术失败熔断；
- terminal state 不进入失败熔断；
- 风险立即 STOP_REQUIRED。

### 6.4 验证阶段

- 全量 accounting；
- JSONL 合法性；
- queue/output hash；
- duplicate/extra/overlap；
- trusted URL；
- required fields；
- record hash；
- source tab；
- manifest `merge_allowed`。

### 6.5 生产阶段

只在杭州生产机：

- 拉取固定 commit/artifact；
- dry-run；
- 显式批准；
- 幂等导入；
- landed validation；
- 回滚验证。

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

### queue hash 错误

- 分类：`integrity failure`
- 动作：fail closed；重新生成 queue/manifest，禁止忽略 hash 继续运行。

### 生产导入差异

- 分类：`import/landed validation failure`
- 动作：停止后续批次；保留 dry-run/import report；按 source run/round 回滚或修复，不手工临时 SQL 补数据。

## 8. 备份与恢复

- 代码备份：Git tag / GitHub Release，不维护平行主分支。
- 数据制品备份：固定 commit 对应的 JSONL、manifest、validation report artifact。
- 数据库备份：由生产备份机制负责，导入前后记录批次边界。
- 会话不备份到 GitHub；Cookie/session 仅保留在受控采集机运行环境。
- 恢复必须从明确的 queue hash、record hash、source run/round 和 checkpoint 开始。
