# AIdeal CPS / 智省优选 — DL2 商用化交接总览

> 归档日期：2026-06-19  
> 仓库：`ShanGouXueHui/aideal-cps-data-lab`  
> 主分支：`main`，唯一主流分支  
> 状态：当前权威交接；运行数据仍以最新 GitHub 报告、manifest、CI 和脱敏现场日志为准。

## 1. 项目目标与系统边界

DL2 是 AIdeal CPS / 智省优选的京东联盟授权数据采集、标准化、验证和生产导入前门禁系统。

负责：

1. 在人工登录、已授权的京东联盟浏览器会话中发现佣金商品；
2. 精确定位 SKU，生成可信推广链接；
3. 对价格、佣金、推广链接和来源信息进行标准化；
4. 按 SKU 幂等落盘，生成 JSONL、manifest、hash、checkpoint 和验证报告；
5. 通过受控同步/importer 向 AIdeal CPS 本地 MySQL 交付已验证数据；
6. 提供备份、审计、回滚和一致性证据。

不负责：终端用户对话、推荐排序、会员、支付、佣金结算、在线生产 API 或绕过生产导入门禁直接修改业务库。

## 2. 环境与周边系统

### 2.1 杭州采集机

- IP：`121.41.111.36`
- 用户：`cpsdata`
- 项目：`/home/cpsdata/projects/aideal-cps-data-lab`
- Chrome CDP：`127.0.0.1:19228`
- systemd：`aideal-hz23-observer.service`
- noVNC：`http://121.41.111.36:18772/vnc.html?autoconnect=true&resize=scale`
- 用途：京东联盟人工登录、授权网页采集、Data Lab 数据处理、验证、发布候选制品。

### 2.2 杭州生产机

- IP：`8.136.28.6`
- 用户：`deploy`
- 项目：`/home/deploy/projects/aideal-cps`
- 本地业务数据库：MySQL `aideal_cps`
- 用途：AIdeal CPS 生产服务、Data Lab 数据 dry-run、同步/import、landed validation。
- 禁止：运行京东联盟浏览器自动化、复用采集机 Cookie/session。

### 2.3 新加坡开发机

- IP：`43.106.55.255`
- 用户：`cpsdev`
- 用途：`aideal-cps` 应用开发和非生产测试。
- 不作为当前 DL2 双主采集源，不与杭州采集机并行维护第二套事实源。

### 2.4 数据库目标架构

Data Lab MySQL 目标仍然有效，但当前是否已初始化必须以服务器和最新报告验证，不得仅凭旧设计文档宣称完成。

目标数据库：`aideal_cps_data_lab`

核心表：

- `commission_products`
- `commission_refresh_runs`
- `commission_product_history`
- `commission_publish_versions`

发布视图：`v_published_commission_products`

安全边界：

- Data Lab MySQL 只监听 `127.0.0.1:3306`；
- 不开放公网 3306；
- AIdeal CPS 在同步任务期间建立短生命周期 SSH Tunnel：生产机 `127.0.0.1:13306` → `cpsdata@121.41.111.36` → Data Lab `127.0.0.1:3306`；
- 同步完成后关闭 Tunnel；
- 用户请求始终读取 AIdeal CPS 本地 MySQL，不实时访问 Data Lab；
- Secret、密码和私钥不进入 GitHub。

当前商用交付允许两种等价受控实现：

1. validated JSONL/artifact → importer → AIdeal CPS 本地 MySQL；
2. Data Lab published MySQL view → 短生命周期 Tunnel 同步 → AIdeal CPS 本地 MySQL。

两种方式都必须经过相同的 manifest/hash、dry-run、幂等、landed validation 和 rollback gate。生产运行时不得直接查询远端 Data Lab。

### 2.5 AI 模型边界

- DL2 核心采集、去重、金额、佣金、推广链接、hash 和门禁均为确定性代码，不依赖大模型判断；
- 用户对话、推荐和模型 Provider 属于 `aideal-cps`；
- ZenMux 已排除，除非用户明确重新开放。

## 3. 已验证的数据与运行事实

### 3.1 HZ22/HZ23 全部商品基线

- 京东页面展示池：约 4000 条；不得描述为 4000 条全部已生成推广链接。
- HZ22 page 61–67 已完成；新增成功 162，失败 5；当时可信推广短链 SKU 为 2385。
- HZ23 首个完整观察轮次 `20260615_100135` 在人工验证后恢复并完成：
  - `completed_pages=67`
  - `unfinished_pages=0`
  - `scanned_total=4020`
  - `stop_reason=null`
- 后续候选构建和验证结果：
  - `candidate_rows=3304`
  - `duplicate_sku_count=0`
  - `invalid_row_count=0`
  - `payload_hash_mismatch_count=0`
  - `candidate_integrity_ready=true`
  - `observation_ready=true`
  - `gate_failures=[]`

3304 是当前可信商业候选基线，不等于页面所有 4000 条商品，也不等于已正式写入生产 MySQL。

### 3.2 HZ24 特殊频道增量

特殊频道：

- 超补爆品
- 限量高佣
- 秒杀专区
- 定向高佣
- 粉丝爱买

已验证重叠数据：

- 频道成员总数：250
- 跨频道去重后唯一 SKU：239
- 跨频道重复 membership：11
- 与现有 3304 候选重叠：18
- 真实增量队列：221

当前最新已提交采集事实：

- queue：221
- linked：72
- pending：149
- complete：false
- 最近旧批次 stop reason：`item_fail_fuse`
- 5 个失败样本实际为“已抢光”且命中 disabled card；旧运行错误地计为点击技术失败。

当前代码已加入 `sold_out`、`delisted`、`not_promotable` 终态分类，但尚需在杭州采集机用当前 GitHub HEAD 做最小授权 smoke，证明终态不再触发技术失败熔断。

## 4. 当前代码与设计状态

已经进入 GitHub 的主线方向：

- TOML + typed settings；
- browser contract / JD page adapter；
- application / session / tab runner；
- outcome / link service；
- JSONL repository / records / state store；
- linked、unavailable、pending accounting；
- SKU 幂等 upsert、原子替换、record hash；
- queue hash、row count、manifest；
- canonical collector 和 validator 入口委托；
- HZ24 单元测试、静态 CI 和工程审计框架；
- 配置化 host、port、scheme、路径、timeout、sleep、batch、频道、risk、schema 和 service 名称。

当前仍需确认/修复：

1. 当前 `main` HEAD 的 compile/import/unit/Actions 是否全绿；历史 PASS 报告不能替代当前 HEAD；
2. validator 必须为纯文件验证，不应为了 URL 校验加载浏览器/HZ21 adapter；
3. linked 与 unavailable 在 repository 层必须互斥；
4. collector 需进程级 lock，防止 systemd、nohup、手工命令并发双写；
5. STOP_REQUIRED 必须有机器可读状态、稳定退出码和 supervisor 禁止自动重启；
6. observer 暂停/恢复需要 trap/finally 级保证；
7. 最终 checkpoint 必须覆盖 complete、pending 和 stop reason，并有测试；
8. HZ21 adapter 仍是兼容依赖，应逐步抽取通用点击/modal 协议。

## 5. 编程和交付硬规则

### 5.1 修改前门禁

任何代码、脚本、配置、DDL 或测试修改前必须：

1. 扫描目标文件同作用域重复定义；
2. 扫描相邻模块和全仓是否已有同类实现；
3. 检查重复常量、重复配置和跨文件复制实现；
4. 检查 host、port、URL、路径、timeout、sleep、batch、频道、risk、selector、schema、service 是否硬编码；
5. 检查文件和函数是否超过可维护阈值；
6. 再进行最小修改。

### 5.2 分层与规模

- entrypoint 只负责参数、调用和退出码；
- 页面 selector 不散落到业务层；
- 浏览器、领域判断、持久化、验证、导入分层；
- Python/Shell 单文件超过约 300 行时，不继续堆业务逻辑；
- 单函数超过约 80 行时按职责拆分；
- 大文件拆分必须按职责，不做机械分片；
- validator、hash、URL、金额等尽量使用纯函数。

### 5.3 数据规则

- SKU 是唯一业务键；
- 金额使用 Decimal/DECIMAL；
- 所有写入幂等、事务化或原子替换；
- 未变化记录只更新时间戳；业务字段变化才写 history；
- 不物理删除商品；连续完整成功轮次缺失后才进入 inactive；
- linked/unavailable 必须互斥；
- 自动化测试不得调用 JD live API 或真实联盟页面；
- 真实页面只用于明确的人工授权 smoke/E2E。

### 5.4 Git 与备份

- `main` 是唯一主流分支；
- 同一能力只有一个 canonical implementation；
- `v2/v3/backup/rewrite` 不得长期并行发展；
- 兼容入口只委托 canonical service，迁移后删除；
- 备份使用 tag、release、artifact、数据库快照或归档包；
- 每次 GitHub 写入后必须通过 `fetch_file`、`fetch_commit` 或服务器 `git log` 二次确认。

## 6. 人机交互与运行习惯

- 使用中文，职业化、直接、结构化；
- 默认直接读取和修改 GitHub，不在对话中打印大段代码；
- 不使用 Codex CLI；
- Linux 命令不使用 `set -e`；
- 命令分小步，一次只解决一个问题；
- 日志写入 `logs/`、`reports/` 或 `docs/debug/`；用户只返回最终 SUMMARY；
- 详细结果优先从 GitHub 报告和 commit 读取；
- 只有必须访问人工浏览器会话、systemd 或服务器本地状态时才让用户执行最小命令；
- 京东账号只允许人工登录，账号密码不得写入脚本；
- 出现验证码、滑块、风险页或登录失效立即停止，不绕过。

## 7. 商用状态与下一步

当前商业状态：`NOT_READY`。

已完成：

- HZ23 全量观察和 3304 候选完整性门禁；
- HZ24 五频道结构、重叠和 221 增量队列；
- HZ24 已生成 72 条链接；
- 主要分层、配置和终态分类代码；
- MySQL V1 DDL、domain/repository/backfill/sync 方向已有历史实现和设计，但实际初始化/启用状态待重新核验。

未完成：

- 当前 HEAD 静态基线证明；
- HZ24 当前代码最小授权 smoke；
- 221 SKU 全量 accounting；
- validation report `merge_allowed=true`；
- Data Lab MySQL 初始化、回填、dual-write 和发布视图的现场验证；
- AIdeal CPS dry-run、正式同步/import、landed validation 和回滚演练；
- 至少一周稳定运行观察。

固定推进顺序：

1. Phase A：当前 HEAD compile/unit/contract/Actions 全绿；
2. Phase B：杭州采集机 2–3 SKU 授权 smoke；
3. Phase C：复用 72 linked，完成剩余 149 的 linked/unavailable accounting；
4. Phase D：validation pass，要求 221 全部可解释、pending=0、overlap=0、duplicate=0、`merge_allowed=true`；
5. Phase E：核验并初始化 Data Lab MySQL，回填 3304 + 已验证 HZ24 增量，完成 JSONL/MySQL 一致性和 published view；
6. Phase F：杭州生产机通过短生命周期 Tunnel 或 validated artifact 执行 dry-run、幂等同步/import、landed validation、回滚；
7. Phase G：稳定运行一周后，显式批准商用；
8. Phase H：refresh queue、监控和 HZ11–HZ23 遗留脚本退役。

## 8. 新对话第一动作

不要直接重新跑 221 SKU，也不要直接初始化数据库。

先读取本文和权威文档，检查 `main` 最新 commit、HZ24 static CI、当前代码重复定义/硬编码和第一个 compile/unit failure。只修复第一个真实阻断项。当前 HEAD 静态基线全绿后，再进入 2–3 SKU 授权 smoke。
