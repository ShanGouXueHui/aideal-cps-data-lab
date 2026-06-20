# 环境、周边系统与协作规则

更新日期：2026-06-20

## 1. 服务器、仓库与角色

### 1.1 杭州 Data Lab 生产服务器

```text
服务器名称：Ubuntu-datacollection
公网 IP：121.41.111.36
区域：华东1（杭州）
规格：2 核 / 4 GiB / 50 GiB
用户：cpsdata
项目目录：/home/cpsdata/projects/aideal-cps-data-lab
GitHub：ShanGouXueHui/aideal-cps-data-lab
默认分支：main
```

运行组件：

```text
Python + Playwright
Google Chrome
CDP：127.0.0.1:19228
浏览器 Profile：.secrets/jd_union_public_manual_profile
X11 display：:79
x11vnc：59072
noVNC/websockify：18772
HZ23 systemd：aideal-hz23-observer.service
```

该服务器是唯一 Data Lab 生产环境。真实京东登录、浏览器会话、HZ23/HZ24、生产状态、MySQL 初始化和 dual-write 只能在这里运行。

密码、Cookie、Profile、账号资料、Token、私钥和数据库密码只存服务器 Secret，不进入 GitHub，也不复制到新加坡。

### 1.2 新加坡 CI Bridge

```text
服务器名称：Ubuntu-Oris-OpenClaw
公网 IP：43.106.55.255
区域：新加坡
规格：2 核 / 2 GiB / 40 GiB
Data Lab 用户：datalab
Data Lab 目录：/home/datalab/projects/aideal-cps-data-lab
其他项目用户：cpsdev
角色：GitHub Actions 的离线验证替代节点
```

`datalab` 与 `cpsdev` 必须隔离：

- 不共享项目目录；
- 不共享虚拟环境；
- 不共享 SSH 私钥；
- 不共享浏览器 Profile、Cookie、运行数据和数据库；
- `datalab` 不加入 sudo 组。

新加坡只允许：

- 拉取 GitHub；
- Python 编译和静态检查；
- Offline Quality；
- Engineering Audit；
- 无 JD live 的单元测试；
- 回写脱敏报告。

禁止真实采集、JD 登录、生产 JSONL、生产 MySQL、dual-write、publish 和 AIdeal CPS 同步。

### 1.3 杭州 AIdeal CPS 生产服务器

```text
公网 IP：8.136.28.6
用户：deploy
项目目录：/home/deploy/projects/aideal-cps
GitHub：ShanGouXueHui/aideal-cps
默认分支：main
systemd：aideal.service
MySQL：aideal_cps
```

技术栈：FastAPI、SQLAlchemy、Alembic、MySQL、Nginx/systemd、微信公众号/H5，Qwen 为可选推荐增强。

该服务器是消费端生产，不承担京东联盟浏览器采集。

## 2. 运维登录方式

为降低切换服务器和复制命令错误，操作入口固定为：

```text
运维人员登录杭州 Data Lab：121.41.111.36 / cpsdata
        ↓ SSH
进入新加坡 CI Bridge：43.106.55.255 / datalab
```

固定边界：

- SSH 后的编译、测试和审计在新加坡执行；
- 杭州只作为统一登录入口，不代替新加坡运行 CI Bridge；
- SSH 不作为生产数据同步通道；
- 不通过 SSH 复制 Cookie、Profile、生产 JSONL、数据库备份、Token、私钥或数据库密码；
- 新加坡不得反向控制杭州生产服务；
- GitHub commit 和脱敏报告仍是代码交接面。

## 3. 系统边界

### Data Lab 负责

- 京东联盟授权登录和浏览器会话；
- “全部商品”和专题 Tab 的商品采集；
- SKU、标题、图片、价格、佣金、推广资格和状态解析；
- 推广短链生成和刷新；
- 风控检测、安全停止和手工验证后断点恢复；
- SKU 去重、历史、快照、质量门禁；
- Data Lab MySQL 权威源数据；
- 发布版本和只读视图。

### AIdeal CPS 负责

- 微信/H5 用户入口；
- 商品搜索、推荐和展示；
- 点击归因；
- 订单和返佣；
- AI 推荐理由和标签；
- 本地 MySQL 业务数据；
- 从 Data Lab 定时同步已发布佣金商品。

用户请求不得实时依赖 Data Lab 浏览器、SSH Tunnel 或远程数据库。

## 4. MySQL 与网络边界

Data Lab 目标数据库：

```text
aideal_cps_data_lab
commission_products
commission_refresh_runs
commission_product_history
commission_publish_versions
v_published_commission_products
```

网络约束：

- Data Lab MySQL 只监听 `127.0.0.1:3306`；
- 不开放公网 3306；
- AIdeal CPS 使用短生命周期 SSH Tunnel；
- AIdeal CPS 本地端口约定 `127.0.0.1:13306`；
- 使用只读数据库用户；
- 同步完成后关闭 Tunnel；
- 用户请求始终读取 AIdeal CPS 本地 MySQL；
- 数据库密码和 SSH 私钥不进入 GitHub。

## 5. 模型与 AI 边界

Data Lab 的采集、价格、佣金、推广链接、状态和质量判断不依赖大模型。

AIdeal CPS 可以使用 Qwen 等模型生成推荐理由，但：

- AI 不决定价格、佣金和链接真实性；
- 模型失败不能阻断商品访问；
- AI 字段与 Data Lab 源字段分离；
- Data Lab 同步不能覆盖 `ai_reason`、`ai_tags`；
- 模型 Key 只存服务器 Secret/`.env`。

## 6. 交互习惯

1. 全程使用中文，职业化、直接、结构化。
2. 优先直接读取和修改 GitHub，不依赖聊天短期上下文。
3. 代码、长脚本和复杂命令直接提交 GitHub，不在聊天中打印大段内容。
4. 用户只执行仓库内经过审核的单一 `.sh` 入口，避免零散命令和粘贴截断。
5. 每次 GitHub 写入后必须使用 `fetch_file`、`fetch_commit` 或服务器 `git log` 二次确认。
6. 详细日志写入 `logs/`、`reports/` 或 `docs/debug/`；关键摘要提交 GitHub。
7. 用户通常只贴最终 Summary；助手直接从 GitHub读取详细报告。
8. 定位问题一问一答，不一次提供多个无关排障分支。
9. 不用话术掩盖工程问题；价格、佣金、链接和数据一致性必须通过机制验证。
10. 用户可手工完成京东登录/验证，但账号密码不得进入脚本、日志或 GitHub。
11. 不使用 Codex CLI。
12. 状态、设计、任务和下一步以 GitHub 文档为连续性载体。

## 7. 命令与脚本规范

- Linux 脚本必须 copy-paste 可执行；
- 不使用 `set -e`；
- 不使用会退出当前登录 Shell 的 `|| exit 1`；
- 复杂操作封装为仓库脚本；
- 脚本必须从自身位置解析仓库根目录；
- 大日志写文件，屏幕只输出紧凑 Summary；
- 不用未确认路径执行 `rm -rf`；
- 不直接覆盖生产状态，先 dry-run、备份、校验再原子切换；
- `backups/` 可保留本机，但不是正式代码来源；
- 助手直接修改 GitHub 时，不再向用户发送大段文件修改命令。

## 8. Git 与分支规则

- 正式代码只维护 `main` 一个主流分支；
- 可以创建只读历史快照或短期修复分支，但不得长期分叉；
- 当前历史快照：`history-snapshot-20260620`；
- 运行数据、日志、Profile 和 Secret 不进入 Git；
- 只有经过筛选的报告、manifest、schema 和文档可以提交；
- 文档和 schema 必须随代码同一变更窗口更新；
- 每个关键节点建立可验证 commit；
- push 后二次确认 remote HEAD 和文件内容；
- 旧版本脚本不得与新版本同时作为可执行主线。

## 9. 代码修改强制门禁

修改前必须扫描：

1. 同作用域重复函数、类、方法和 Shell 函数；
2. 同作用域重复变量、模块常量、配置键和默认值；
3. 相邻模块和跨文件重复实现；
4. 硬编码地址、路径、端口、URL、Tab、selector、等待时间和阈值；
5. 大文件和长函数；
6. Python/Shell 基础语法；
7. 仓库全量工程审计。

正式验收要求全局 blocker 清零，不只看 active scope。当前扫描器对重复变量/常量赋值仍有能力缺口，必须在下一阶段补齐。

## 10. 分层解耦

```text
browser/collector       DOM、selector、真实点击、风险检测
application/service     采集编排、批次、断点、状态机
domain                  SKU、商品、链接、结果状态
persistence/repository  JSONL/MySQL、事务、原子写入
contracts/schema         schema、枚举、跨系统合同
configuration            typed settings、配置加载
ops                       systemd、部署、备份、状态入口
tests                     fixture、单元测试、无 JD live
```

业务层不得散落 Playwright selector；数据库层不得依赖浏览器对象；Shell/Python 入口只负责参数解析、调用服务和输出 Summary。

强制阈值：

- Python/Shell 单文件超过 300 行：先拆分再修改；
- 单函数超过 80 行：拆分职责；
- 运行入口超过 120 行：收敛为薄入口；
- 浏览器、业务、持久化、发布职责不得混在同一函数。

## 11. 配置与 Secret 分离

禁止在业务代码和运维脚本散落：

- IP、域名、端口、用户名、绝对路径；
- 页面 URL、Tab、selector、风险词；
- 页面范围、批大小、等待时间、时间窗口和熔断阈值；
- 数据库名、表名、Tunnel 端口；
- 输入输出文件路径；
- 写入、发布和同步开关；
- 密码、Token、Cookie、Profile、私钥。

非敏感运行参数进入版本化配置；环境差异进入环境变量；Secret 进入服务器 Secret。默认值只能在一个配置入口定义。

## 12. 数据一致性

- SKU 是唯一业务键；
- 金额使用 Decimal/DECIMAL；
- 所有写入幂等；
- 使用事务、唯一约束和原子替换；
- 未变化记录只更新时间戳；
- 业务字段变化才写 history；
- 每条记录保留稳定 payload hash；
- 同一轮次不得生成不一致结果；
- 连续两次完整成功轮次未出现才 inactive；
- 不物理删除商品；
- HZ24 必须区分 `linked`、`unavailable` 和 `pending`；
- unavailable 不得进入商用候选；
- 无效 finalize 不得覆盖 last-known-good canonical candidate。

## 13. 测试与可观测性

- 自动化测试禁止调用 JD live API；
- JD live 只用于真实浏览器流量或明确手工 smoke；
- 使用 fixture、安全 DOM 快照和模拟 Repository；
- 覆盖重复 SKU、风险页、空卡片、字段变化、事务回滚、断点续跑、幂等、checksum、sold-out、unavailable 和 last-known-good 保护；
- 每轮有 round_id；
- 每页有 page_no 和计数；
- 每条失败有 reason；
- 报告记录 generated_at、git_head、来源 checksum、成功/失败/不可用/待处理和风险；
- 报告 `git_head` 必须等于被验证的当前 main；
- 禁止失败后复用陈旧报告。

## 14. 商用通用性

- 不针对单个 SKU 或临时 DOM 写死逻辑；
- selector 使用集中配置和多候选策略；
- 页面、商品、渠道和数据源适配器解耦；
- 数据合同版本化；
- breaking change 新建版本，不静默改字段；
- 当前只实现京东，不提前堆叠无用抽象；
- 正式方案必须包含异常停止、断点、审计、备份、回滚和一致性报告。

## 15. 当前执行冻结

在代码全局门禁和 HZ23 last-known-good 候选恢复前：

```text
HZ24 collection paused
Data Lab MySQL uninitialized
DATA_LAB_DB_WRITE_ENABLED=false
DATA_LAB_DB_DUAL_WRITE_ENABLED=false
DATA_LAB_PUBLISH_ENABLED=false
DATA_LAB_SYNC_ENABLED=false
AIdeal CPS production sync disabled
```