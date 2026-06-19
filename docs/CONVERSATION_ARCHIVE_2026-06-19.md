# AIdeal CPS / 智省优选 — DL2 对话归档

> 归档日期：2026-06-19  
> 适用仓库：`ShanGouXueHui/aideal-cps-data-lab`  
> 状态：设计与工程上下文归档；运行态以最新 GitHub 报告和现场日志为准。

## 1. 项目目标与边界

本仓库是 AIdeal CPS / 智省优选的京东联盟授权数据采集与验证仓库，负责：

1. 在人工登录并授权的京东联盟网页会话中采集候选商品与推广链接；
2. 标准化为 JSONL；
3. 生成 manifest、hash、state、collection report、validation report；
4. 向生产 importer 交付 validated artifact；
5. 在进入生产前执行 fail-closed 质量门禁。

本仓库不负责用户对话、推荐排序、会员、支付、返佣结算、在线生产 API 或直接写生产数据库。

## 2. 环境与周边系统

### 2.1 杭州采集机

- IP：`121.41.111.36`
- 用户：`cpsdata`
- 项目路径：`/home/cpsdata/projects/aideal-cps-data-lab`
- Chrome CDP：`127.0.0.1:19228`
- noVNC：`18772`
- x11vnc：`59072`
- 职责：人工登录、授权页面采集、生成非敏感制品与报告。
- 禁止：提交账号密码、Cookie、session、二维码、HAR、HTML、原始账户页面或敏感日志。

### 2.2 杭州生产机

- IP：`8.136.28.6`
- 用户：`deploy`
- 项目路径：`/home/deploy/projects/aideal-cps`
- 职责：生产服务、validated artifact 校验、importer dry-run、受控导入、landed validation。
- 禁止：浏览器自动化、京东账号登录、复用采集机 Cookie/session。

### 2.3 新加坡开发机

- IP：`43.106.55.255`
- 用户：`cpsdev`
- 可用于 `aideal-cps` 应用开发；不是当前 DL2 采集双主。

### 2.4 数据库与模型

- 生产数据库：MySQL；连接信息与凭证不得进入仓库、日志或文档。
- Data Lab 默认只生成文件制品，不直接写生产 MySQL。
- Data Lab 核心链路保持确定性，不依赖大模型判断页面、价格、佣金、短链、哈希或导入门禁。
- 面向用户的模型 Provider 属于 `aideal-cps`；ZenMux 已排除。

## 3. 交互与操作习惯

- 使用中文，职业化、直接、结构化。
- 默认由 ChatGPT 直接读取和修改 GitHub；不要让用户执行超长文件写入命令。
- 不使用 Codex CLI。
- 服务器命令可直接 copy-paste、分小步、不使用 `set -e`。
- 每一步尽量包含路径确认、`git status`、最小动作、静态检查、smoke/E2E、日志路径。
- 日志写入 `logs/` 或 `run/`；屏幕只显示关键 80–180 行。
- 排障一次只推进一个问题。
- GitHub 是长期事实源；运行态不能由 GitHub 证明时必须标为“待现场验证”。

## 4. 编程与架构规范

### 4.1 分层

主线按以下职责解耦：

- entrypoint：只解析参数并调用 application service；
- configuration：TOML + typed settings；
- browser/page adapter：CDP、DOM、tab、modal；
- application/session：批次编排与生命周期；
- outcome service：linked / unavailable / retryable failure 分类；
- repository/state：原子写、去重、checkpoint、lock；
- validation：纯数据合同与一致性校验；
- importer：生产侧 dry-run、幂等写入、landed validation。

### 4.2 配置分离

host、port、scheme、URL、路径、timeout、sleep、batch、risk marker、频道、schema、service 名称必须配置化。运行时覆盖通过环境变量完成，禁止在业务逻辑重复硬编码。

### 4.3 单一主流实现

- `main` 是唯一主流分支。
- 同一能力只保留一个 canonical implementation。
- 兼容入口只能委托 canonical service。
- 备份通过 tag、release、artifact 或快照，不维护长期 v2/v3/backup 并行主线。

### 4.4 商用质量属性

通用商用版本必须具备：幂等、可恢复、可审计、可回滚、fail closed、进程互斥、数据互斥、版本化合同、hash 校验、显式审批和生产默认关闭。

## 5. HZ24 设计决策

- 特殊频道：超补爆品、限量高佣、秒杀专区、定向高佣、粉丝爱买。
- 队列：`data/export/hz24_special_tab_increment_latest.jsonl`
- linked：`data/import/hz24_special_tab_links_latest.jsonl`
- unavailable：`data/import/hz24_special_tab_unavailable_latest.jsonl`
- collection report：`reports/hz24_increment_collection_latest.json`
- validation report：`reports/hz24_increment_validation_latest.json`
- 终态分类：`sold_out`、`delisted`、`not_promotable`。
- 风险页、验证码、滑块、登录失效必须立即停止，不绕过验证。
- `linked + unavailable + pending = queue`；linked 与 unavailable 必须互斥。
- 采集成功不等于允许商用导入；只有 validation 与 importer gate 共同通过才可进入生产。

## 6. 本轮已完成的代码方向

本轮已直接在 GitHub 推进：

- HZ24 typed settings 与 TOML 配置；
- browser contract、JD page adapter、session、tab runner、outcome、link、records、repository、state store、validation 分层；
- canonical collector/validator 入口委托；
- sold-out 等终态分类；
- JSONL SKU upsert、hash、manifest、accounting；
- HZ24 静态 workflow 与单元测试；
- shell runner 去除项目路径和 service 名称硬编码；
- 工程审计增加汇总，并缩小部分硬编码误报范围。

这些属于“代码已实现”；当前 GitHub HEAD 是否全部 compile/unit 通过，以及杭州授权 E2E 是否通过，仍必须以 Actions 和现场日志验证。

## 7. 当前风险与纠错

- 历史报告中的全仓 blocker 数会随审计规则和代码变化，不应写死为稳定事实。最新已看到的报告为 605 blocker；它主要反映 HZ11–HZ23 legacy debt，不等于 HZ24 主线有 605 个运行故障。
- `reports/project_engineering_audit_latest.json` 是动态审计快照；后续应同时输出“当前主线门禁”和“legacy debt”两套视图。
- HZ24 validation 不应依赖浏览器/HZ21 adapter；应使用纯 URL validator。
- linked/unavailable 互斥、进程 lock、STOP_REQUIRED、最终 checkpoint 仍需完整实现和测试。
- HZ21 adapter 是兼容依赖，后续应抽取通用点击与 modal 协议。

## 8. 商用推进阶段

1. Phase A：静态基线、compile、unit、contract、Actions；
2. Phase B：杭州 2–3 SKU 授权 smoke；
3. Phase C：完成 221 SKU accounting；
4. Phase D：validation pass，`merge_allowed=true`；
5. Phase E：生产 importer dry-run、显式批准、幂等导入、landed validation；
6. Phase F：定时运行、刷新队列、监控、legacy 退役。

## 9. 事实等级

- 已验证事实：GitHub 代码、提交报告、manifest、CI 或现场日志证明；
- 代码已实现但未现场验证：代码存在，当前环境未完成 smoke/E2E；
- 设计决策：已确定但实现或验证未完成；
- 风险/假设：必须附验证方法，不得包装成完成项。
