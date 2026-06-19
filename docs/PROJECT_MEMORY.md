# AIdeal CPS / 智省优选 — DL2 项目记忆

> 最后更新：2026-06-19  
> 权威范围：项目定位、环境、数据库边界、协作方式、安全约束和长期设计。  
> 新对话先读：`COMMERCIALIZATION_HANDOFF_20260619.md`、本文、`CURRENT_PROGRESS.md`。

## 1. 项目定位

- 产品：AIdeal CPS / 智省优选。
- 业务：微信公众号/服务号入口的 AI 导购 + 京东联盟 CPS 返佣系统，不是自营电商平台。
- Data Lab：人工授权京东联盟网页采集、标准化、验证、发布候选和生产导入前门禁。
- AIdeal CPS：终端对话、推荐、会员、返佣业务、生产 API 和本地 MySQL 消费端。
- Data Lab 不直接承载终端用户流量，也不允许生产请求实时读取远端采集数据库。

## 2. 仓库边界

| 仓库 | 角色 | 原则 |
|---|---|---|
| `ShanGouXueHui/aideal-cps-data-lab` | 京东联盟授权采集、标准化、验证、发布候选 | `main` 唯一主流分支 |
| `ShanGouXueHui/aideal-cps` | AIdeal CPS 后端和生产业务 | 消费本地 MySQL，不运行京东浏览器自动化 |
| `ShanGouXueHui/aideal-site` | 品牌官网、备案站点 | 与佣金采集链路隔离 |

跨仓库交付只能通过版本化数据合同、validated artifact、published view 或 controlled importer/sync，不依赖共享工作目录和临时复制代码。

## 3. 环境事实

### 3.1 杭州采集机

- IP：`121.41.111.36`
- 用户：`cpsdata`
- 路径：`/home/cpsdata/projects/aideal-cps-data-lab`
- Chrome CDP：`127.0.0.1:19228`
- noVNC：`18772`
- x11vnc：`59072`
- systemd：`aideal-hz23-observer.service`
- 允许：人工登录京东联盟、授权采集、生成 Data Lab 数据和报告。
- 禁止：把密码、Cookie、session、二维码、HAR、HTML、原始账户页面或敏感日志提交 GitHub。

### 3.2 杭州生产机

- IP：`8.136.28.6`
- 用户：`deploy`
- 路径：`/home/deploy/projects/aideal-cps`
- 本地 MySQL：`aideal_cps`
- 允许：生产服务、Data Lab dry-run、同步/import、landed validation、回滚。
- 禁止：运行京东联盟浏览器自动化、登录联盟账号、复用采集机 Cookie/session。

### 3.3 新加坡开发机

- IP：`43.106.55.255`
- 用户：`cpsdev`
- 用于 `aideal-cps` 开发和非生产测试。
- 不作为当前 DL2 双主采集源。

## 4. 数据库与同步架构

### 4.1 Data Lab MySQL 目标

目标数据库：`aideal_cps_data_lab`

表：

- `commission_products`
- `commission_refresh_runs`
- `commission_product_history`
- `commission_publish_versions`

只读发布视图：`v_published_commission_products`

安全规则：

- 只监听 `127.0.0.1:3306`；
- 不开放公网 3306；
- Secret、账号、密码、私钥不进入 GitHub；
- 写入、dual-write、publish、consumer sync 开关默认关闭；
- 实际是否已经初始化必须以服务器和最新报告核验，不能把设计文档当运行事实。

### 4.2 AIdeal CPS 消费方式

允许两种受控交付：

1. validated JSONL/artifact 经 importer 写入 AIdeal CPS 本地 MySQL；
2. AIdeal CPS 建立短生命周期 SSH Tunnel，读取 Data Lab published view 后同步到本地 MySQL。

Tunnel 约定：生产机 `127.0.0.1:13306` → `cpsdata@121.41.111.36` → Data Lab `127.0.0.1:3306`。同步完成后关闭。终端用户请求始终读取 AIdeal CPS 本地 MySQL，不实时访问 Data Lab。

### 4.3 AI 模型

- DL2 页面识别、字段解析、金额、佣金、短链、去重、hash 和导入门禁均使用确定性代码；
- 推荐、对话和模型 Provider 属于 `aideal-cps`；
- ZenMux 已排除，除非用户明确重新开放。

## 5. 交互与协作习惯

- 中文，职业化、直接、结构化；
- ChatGPT 默认直接读取和修改 GitHub，不让用户执行超长文件写入命令；
- 不使用 Codex CLI；
- Linux 命令不使用 `set -e`；
- 命令分小步，一次只解决一个问题；
- 日志写入 `logs/`、`reports/` 或 `docs/debug/`；用户只返回最终 SUMMARY；
- 详细结果优先从 GitHub 报告和 commit 读取；
- 运行态无法由 GitHub 证明时标记“待现场验证”；
- 每次 GitHub 写入后必须用 `fetch_file`、`fetch_commit` 或服务器 `git log` 二次确认。

## 6. 安全与风控

- 京东联盟账号只允许人工登录，账号密码不得写入脚本；
- 出现验证码、滑块、风险页、登录失效或页面身份不确定时立即停止；
- 不绕过验证；
- 写 STOP_REQUIRED/停止原因，禁止 supervisor 无限重启；
- 价格、佣金和推广链接准确性依赖字段来源、校验、hash、时间戳、幂等和 landed validation，不依赖话术。

## 7. 已验证业务事实

### 7.1 HZ23 基线

- 京东页面展示池约 4000 条，但不能描述为 4000 条全部已生成推广链接；
- HZ23 完整轮次 `20260615_100135` 已完成：67 页、`scanned_total=4020`、无 unfinished page、无 stop reason；
- 商业候选：3304；
- duplicate、invalid、payload hash mismatch 均为 0；
- `candidate_integrity_ready=true`；
- `observation_ready=true`；
- HZ23 3304 是当前候选基线，不等于已正式写入生产数据库。

### 7.2 HZ24 增量

- 特殊频道：超补爆品、限量高佣、秒杀专区、定向高佣、粉丝爱买；
- 250 个频道 membership；
- 跨频道唯一 SKU 239；
- 重复 membership 11；
- 与 3304 基线重叠 18；
- 真实增量队列 221；
- 当前已提交结果：72 linked、149 pending、complete=false；
- 旧批次把 5 个“已抢光”错误记为 click failure 并触发 `item_fail_fuse`；当前代码已加入 unavailable 分类，但仍待当前 HEAD 的杭州 smoke 证明。

## 8. 固定工程原则

- 修改前先扫描重复定义、重复实现和硬编码；
- 分层：browser/collector、application/service、domain、persistence/repository、contracts/schema、configuration、ops、tests；
- selector 不散落到业务层；
- host、port、scheme、URL、路径、timeout、sleep、batch、频道、risk、schema、service 全部配置化；
- SKU 唯一，Decimal/DECIMAL，幂等、事务、原子替换；
- linked/unavailable 互斥；
- 不物理删除商品；
- 自动化测试不访问 JD live；
- `main` 是唯一主流分支；
- 同一能力只有一个 canonical implementation；
- 备份使用 tag、release、artifact、数据库快照或归档，不维护长期平行版本。

## 9. 商用定义

只有以下条件全部满足，才能称为商用：

- 当前 HEAD compile/unit/contract/Actions 通过；
- 杭州授权 session smoke 通过；
- 队列 accounting 100%；
- validation `merge_allowed=true`；
- Data Lab MySQL 或 validated artifact 交付链路完成 dry-run；
- AIdeal CPS 本地 MySQL 幂等写入、landed validation 和回滚通过；
- 至少一周稳定运行；
- 显式批准打开商用发布。
