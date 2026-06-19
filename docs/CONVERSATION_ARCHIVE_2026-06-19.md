# AIdeal CPS / 智省优选 — DL2 对话与设计归档

> 归档日期：2026-06-19  
> 适用仓库：`ShanGouXueHui/aideal-cps-data-lab`  
> 当前主线：HZ24 特殊频道增量采集与商用收口  
> 事实基线：GitHub `main`、版本化报告、manifest、CI 和杭州现场日志；不能由证据证明的事项必须标为待验证。

## 1. 项目目标与系统边界

本仓库是 AIdeal CPS / 智省优选的京东联盟授权数据采集、标准化、验证和生产导入前门禁仓库，负责：

1. 在人工登录并授权的京东联盟网页会话中采集候选商品与推广链接；
2. 将结果标准化为版本化 JSONL；
3. 生成 manifest、SHA-256、state、collection report、validation report；
4. 将 validated artifact 交付受控生产 importer；
5. 在任何生产写入前执行 fail-closed 质量门禁。

本仓库不负责用户对话、推荐排序、会员、支付、返佣结算、在线生产 API，也不直接写生产 MySQL。

相关仓库：

- `ShanGouXueHui/aideal-cps-data-lab`：授权网页采集、验证与导入前门禁；
- `ShanGouXueHui/aideal-cps`：AIdeal CPS 后端与生产业务系统；
- `ShanGouXueHui/aideal-site`：品牌官网与备案站点。

跨仓库交付必须通过版本化数据合同、固定 commit/artifact 和受控 importer，不得依赖共享工作目录、复制临时脚本或直接连接生产数据库。

## 2. 环境与周边系统

### 2.1 杭州采集机：DL2 唯一当前主执行环境

- 公网 IP：`121.41.111.36`
- Linux 用户：`cpsdata`
- 项目路径：`/home/cpsdata/projects/aideal-cps-data-lab`
- 规格：2C / 4G / 50G
- Chrome CDP：`127.0.0.1:19228`
- noVNC：`18772`
- x11vnc：`59072`
- 职责：人工登录京东联盟、授权页面采集、生成非敏感数据制品与报告。

禁止把账号密码、Cookie、session、二维码、HAR、HTML、原始账户页面或敏感运行日志提交到聊天或 GitHub。

### 2.2 杭州生产机

- 公网 IP：`8.136.28.6`
- Linux 用户：`deploy`
- 项目路径：`/home/deploy/projects/aideal-cps`
- 职责：运行生产服务、校验 validated artifact、执行 importer dry-run、显式批准后的幂等导入与 landed validation。

生产机禁止运行浏览器自动化、登录京东联盟或复用采集机 Cookie/session。

### 2.3 新加坡开发机

- 公网 IP：`43.106.55.255`
- Linux 用户：`cpsdev`
- 可用于 `aideal-cps` 应用开发和非生产测试。
- 不是当前 DL2 采集主机，不得与杭州采集机形成双主或两套并行数据源。

### 2.4 数据库和模型边界

- 生产业务数据库为 MySQL；地址、账号和密码不得进入代码、文档、日志或 GitHub。
- Data Lab 默认只生成文件制品和验证结果，不直接写生产 MySQL。
- 页面识别、价格、佣金、短链、哈希、去重、验证和导入门禁必须保持确定性，不依赖大模型判断。
- 面向用户的模型 Provider、推荐与对话属于 `aideal-cps`；ZenMux 已排除，不应默认恢复。

## 3. 固定交互与运作方式

- 使用中文，职业化、直接、结构化。
- 默认由 ChatGPT 直接读取和修改 GitHub；不让用户执行超长 heredoc 或大文件改写命令。
- 不使用 Codex CLI。
- 只有访问人工登录会话、systemd 或服务器本地文件时，才让用户执行命令。
- Linux 命令必须可 copy-paste、分小步，并且不使用 `set -e`。
- 每一步尽量包含：路径确认、`git status --short`、最小动作、静态检查或 smoke、日志路径和关键输出。
- 日志写入 `logs/` 或 `run/`，屏幕只显示关键 80–180 行。
- 排障一次只推进一个故障域，不把登录、采集、验证、导入和生产发布混在同一补丁中。
- GitHub 是长期上下文和事实源；优先查询已提交的代码、配置、报告、manifest、Actions 和相关 commit。GitHub 无法证明的运行态必须明确标为“待现场验证”。

## 4. 编程与架构规范

### 4.1 分层解耦

主线职责固定为：

- entrypoint：只负责启动语义与退出码；
- configuration：TOML、环境变量覆盖和 typed settings；
- browser/page adapter：CDP、DOM、频道、卡片、modal 与风险识别；
- application/session：队列、批次、浏览器生命周期和频道编排；
- outcome service：linked、terminal unavailable、retryable failure 分类；
- repository/state：原子写、SKU 幂等 upsert、互斥、checkpoint、lock；
- validation：纯文件、纯合同校验，无浏览器副作用；
- importer：生产侧 dry-run、显式批准、幂等写入、landed validation 和 rollback evidence。

### 4.2 配置分离

host、port、scheme、URL、路径、timeout、sleep、batch、failure fuse、risk marker、频道、schema、service 名称和链接生命周期必须进入 `config/` 或环境变量。业务代码只消费 typed settings，不得重复硬编码。

### 4.3 单一主流实现

- `main` 是唯一主流分支；
- 同一能力只保留一个 canonical implementation；
- `v2/v3/...` 只能作为短期兼容入口，内部必须委托 canonical service；
- 备份使用 tag、release、artifact、数据库快照或受控归档，不维护长期平行代码主线；
- 每个提交只解决一个主题，代码、配置、测试和文档同步更新。

### 4.4 通用商用质量属性

商用版本必须具备：幂等、可恢复、可审计、可回滚、fail closed、进程互斥、数据互斥、版本化合同、hash 校验、显式审批、生产默认关闭和可验证的 STOP_REQUIRED 恢复语义。

## 5. HZ24 数据和设计决策

特殊频道：

- 超补爆品
- 限量高佣
- 秒杀专区
- 定向高佣
- 粉丝爱买

权威数据文件：

- queue：`data/export/hz24_special_tab_increment_latest.jsonl`
- queue manifest：`data/export/hz24_special_tab_increment_manifest.json`
- linked：`data/import/hz24_special_tab_links_latest.jsonl`
- unavailable：`data/import/hz24_special_tab_unavailable_latest.jsonl`
- state：`run/hz24_increment_collection_state.json`
- collection report：`reports/hz24_increment_collection_latest.json`
- validation report：`reports/hz24_increment_validation_latest.json`
- outcome manifest：`data/export/hz24_special_tab_outcomes_manifest.json`

终态原因固定为：`sold_out`、`delisted`、`not_promotable`。终态业务状态不得计入连续技术失败熔断。

核心不变量：

- `linked + unavailable + pending = queue`；
- linked 与 unavailable 必须互斥；
- 每个 SKU 在单个结果文件中最多一条有效记录；
- queue、输出和 manifest 通过 SHA-256 与 row count 绑定；
- 风险页、验证码、滑块、登录失效或页面身份不确定时立即停止，不绕过验证；
- 采集成功不等于允许商用导入，只有 validation 与 importer gate 共同通过才可进入生产。

## 6. 本轮已直接进入 GitHub 的实现

已加入或重构：

- HZ24 TOML 配置与 typed settings；
- browser contract、JD page adapter；
- application、session、tab runner；
- batch state、outcome service、link service、records；
- JSON/JSONL repository、SKU upsert、state store；
- validation config、IO、rules、service；
- canonical collector/validator 入口委托；
- `sold_out`、`delisted`、`not_promotable` 分类；
- trusted short URL scheme/host 校验；
- record hash、manifest、collection report、validation report；
- HZ24 静态 workflow 和基础单元测试；
- shell runner 的项目路径与 observer service 配置化；
- 工程审计汇总与部分误报收敛。

上述只能标记为“代码已实现”。当前版本是否 compile/unit/Actions 全绿、杭州授权 E2E 是否通过，必须另有证据。

## 7. 已验证的业务与运行事实

- 商业候选池：3304 SKU；
- 特殊频道跨频道重复：11 SKU；
- HZ24 增量队列：221 SKU，`commercial_enabled=false`；
- 最近已提交 collection report：72 linked、149 pending、complete=false；
- 最近批次：7 processed、2 success、5 fail，停止原因为 `item_fail_fuse`；
- 失败样本中存在“已抢光”且命中 disabled card，旧运行错误地将其计为 `click_failed`。

全仓工程审计的已提交快照显示 605 blocker、243 files scanned。该数值是动态快照，主要反映 HZ11–HZ23 历史大文件、重复实现和硬编码，不等于 HZ24 主线存在 605 个运行故障。

## 8. 当前 GitHub 基线与证据限制

归档时可见的 `main` HEAD：`febdeae72e6701305896f797a06bb25c63db40bb`，提交说明为 `docs: link archived context and refresh project status`。

GitHub connector 对该 HEAD 返回：

- combined status：无 status 记录；
- PR-triggered workflow runs：空。

这不能证明 Actions 已通过，也不能证明 Actions 失败。该 HEAD 是文档提交，且 HZ24 workflow 有 path filter，因此可能未触发。下一对话必须查询 HZ24 Static Checks 的最近实际 run，必要时通过 `workflow_dispatch` 触发，再读取 job/step/log。

## 9. 旧文档与旧结论纠正

后续不得继续使用以下错误或不严谨表述：

1. “主要重构已完成，所以可以直接跑 221 SKU”——错误。必须先完成当前 HEAD 静态基线和 2–3 SKU 授权 smoke。
2. “605 blocker 等于当前 HZ24 有 605 个故障”——错误。它是全仓 legacy debt 快照，应拆分当前主线门禁与历史债务。
3. “validation 代码存在即 validation 已通过”——错误。必须有最新 validation report 且 `merge_allowed=true`。
4. “采集到短链即可写生产库”——错误。必须经过 manifest/hash、dry-run、显式批准、幂等导入和 landed validation。
5. “v2/v3 文件可以长期作为备份”——错误。兼容入口只能委托 canonical service；备份使用 tag/release/artifact。
6. “运行日志都提交 GitHub”——错误。GitHub 只提交脱敏 summary/report；详细日志通常保留在服务器，必要时只 tail 指定片段。

## 10. 当前商用阻断项

P0：

1. 当前 HZ24 compile/import/unit/Actions 结果未形成可证明的绿色基线；
2. 杭州采集机尚未用当前代码完成 2–3 SKU 授权 smoke；
3. 221 SKU accounting 尚未完成；
4. 尚无可证明通过的 validation report；
5. 生产 importer dry-run、显式批准、幂等导入和 landed validation 尚未执行。

P1：

1. validation 仍通过页面适配器复用 URL 判断，应改成纯 URL validator，避免加载 HZ21/browser；
2. repository 层尚未强制 linked/unavailable 互斥；
3. 缺少统一进程级 lock；
4. STOP_REQUIRED contract、稳定退出码和 supervisor 禁止重启语义尚未统一；
5. 最终 checkpoint 需要确保写入 complete、最终 pending 和 stop reason；
6. shell runner 应使用 trap/finally 保证 observer 原状态恢复；
7. HZ21 adapter 仍是兼容依赖，后续应抽取通用点击/modal 协议。

## 11. 商用推进顺序

1. Phase A：确认当前 GitHub HEAD，触发/查询 HZ24 Static Checks，修复 compile/import/unit/contract；
2. Phase B：杭州 2–3 SKU 授权 smoke，覆盖正常 linked、terminal unavailable、checkpoint、report、exit code；
3. Phase C：按批完成 221 SKU accounting，要求 pending=0、overlap=0；
4. Phase D：生成 validation report 和 outcome manifest，要求 `merge_allowed=true`，但 `commercial_enabled` 继续为 false；
5. Phase E：杭州生产机固定 commit/artifact dry-run、显式批准、幂等导入、landed validation、rollback evidence；
6. Phase F：安全定时运行、链接刷新、指标监控和 HZ11–HZ23 历史实现退役。

## 12. 新对话读取顺序

1. `docs/PROJECT_MEMORY.md`
2. 本文
3. `docs/CURRENT_PROGRESS.md`
4. `docs/DL2_COMMERCIAL_ARCHITECTURE.md`
5. `docs/ENGINEERING_STANDARDS.md`
6. `docs/ENVIRONMENT_AND_OPERATIONS.md`
7. `docs/NEXT_DIALOG_HANDOFF.md`
8. 当前 HZ24 代码、配置、测试、Actions 和最新报告

## 13. 事实等级

- **已验证事实**：GitHub 代码、固定 commit、报告、manifest、CI 或杭州现场日志证明；
- **代码已实现但未现场验证**：代码存在，但当前环境未完成 smoke/E2E；
- **设计决策**：方向已确定，实现或验证尚未完成；
- **风险/假设**：必须附验证方式，不得包装成已完成。
