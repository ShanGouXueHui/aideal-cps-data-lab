# 环境、周边系统与协作规则

更新日期：2026-06-19

## 1. 服务器、仓库与角色

### Data Lab 数据生产服务器

```text
公网 IP：121.41.111.36
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

noVNC：

```text
http://121.41.111.36:18772/vnc.html?autoconnect=true&resize=scale
```

密码、Cookie、Profile、浏览器会话和账号资料只存服务器 Secret，不进入 GitHub。

### AIdeal CPS 生产服务器

```text
公网 IP：8.136.28.6
用户：deploy
项目目录：/home/deploy/projects/aideal-cps
GitHub：ShanGouXueHui/aideal-cps
默认分支：main
systemd：aideal.service
MySQL：aideal_cps
```

技术栈：

```text
FastAPI
SQLAlchemy
Alembic
MySQL
Nginx/systemd
微信公众号 + H5
Qwen 可选推荐增强
```

### 新加坡开发服务器

```text
公网 IP：43.106.55.255
用户：cpsdev
角色：开发环境
```

杭州 `8.136.28.6` 是 AIdeal CPS 生产环境；新加坡机器不能与生产角色混淆。

## 2. 系统边界

### Data Lab 负责

- 京东联盟授权登录和浏览器会话；
- “全部商品”及专题 Tab 的只读审计和商品采集；
- SKU、标题、图片、价格、佣金、状态解析；
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

## 3. MySQL 与网络边界

Data Lab 目标数据库：

```text
aideal_cps_data_lab
```

固定对象：

```text
commission_products
commission_refresh_runs
commission_product_history
commission_publish_versions
v_published_commission_products
```

网络约束：

- Data Lab MySQL 仅监听 `127.0.0.1:3306`；
- 不开放公网 3306；
- AIdeal CPS 使用短生命周期 SSH Tunnel；
- AIdeal CPS 本地端口约定 `127.0.0.1:13306`；
- 同步任务完成后关闭 Tunnel；
- 用户请求始终读取 AIdeal CPS 本地 MySQL；
- 数据库密码和 SSH 私钥不进入 GitHub。

## 4. 模型与 AI 边界

Data Lab 的采集、价格、佣金、推广链接和质量判断不依赖大模型。

AIdeal CPS 可以使用 Qwen 等模型生成推荐理由，但：

- AI 不决定价格、佣金和链接真实性；
- 模型失败不能阻断商品访问；
- AI 字段与 Data Lab 源字段分离；
- Data Lab 同步不能覆盖 `ai_reason`、`ai_tags`；
- 模型 Key 只存服务器 Secret/`.env`。

## 5. 交互习惯

1. 全程使用中文，职业化、直接、结构化。
2. 优先直接读取和修改 GitHub，不依赖聊天短期上下文。
3. 用户要求代码、长脚本和大段命令不要打印在对话中；工程修改直接通过 GitHub 完成。
4. 每次 GitHub 写入后，必须使用 `fetch_file`、`fetch_commit` 或服务器 `git log` 二次确认。
5. GitHub 连接器写入不稳定时，才改用服务器本地 `git add / commit / push`。
6. 详细日志写入 `logs/`、`reports/` 或 `docs/debug/`；关键摘要提交 GitHub。
7. 用户通常只贴最终 `SUMMARY`；助手直接从 GitHub读取详细报告。
8. 定位问题时一问一答，避免一次给多个无关排障分支。
9. 不用话术掩盖工程问题；价格、佣金、链接和数据一致性必须通过机制验证。
10. 用户允许必要时手工登录或完成京东验证，但账号密码不得进入脚本、日志或 GitHub。
11. 不使用 Codex CLI，除非用户重新明确要求。
12. 后续状态、设计和下一步计划以 GitHub 为连续性载体。

## 6. 命令规范

- Linux 命令必须 copy-paste 可执行；
- 不使用 `set -e`；
- 不使用会退出当前登录 Shell 的 `|| exit 1`；
- 每次命令分小步；
- 大日志写文件，屏幕只输出紧凑 Summary；
- 不用未确认路径执行 `rm -rf`；
- 不依赖用户当前工作目录；脚本必须从自身位置解析仓库根目录；
- `backups/` 可保留在本机，但不是正式代码来源；
- 用户明确要求直接 GitHub 修改时，不再发送大段文件修改命令。

## 7. Git 与分支规则

- 正式代码只维护 `main` 一个主流分支；
- 可以本地备份或创建短期修复分支，但不得长期分叉；
- 运行时数据、日志、Profile、Secret 不进入 Git，只有经过筛选的报告和 manifest 可以提交；
- 文档和 schema 必须随代码同一变更窗口更新；
- 每个关键节点建立可验证 commit；
- push 后二次确认 remote HEAD 和文件内容；
- 旧版本运行脚本不得与新版本同时作为可执行主线；历史脚本应明确归档或通过适配层复用公共实现。

## 8. 代码修改强制门禁

任何文件修改前必须：

1. 扫描目标文件是否存在重复定义；
2. 扫描相邻模块是否已有相同实现；
3. 扫描跨文件重复函数和重复配置；
4. 扫描硬编码环境地址、路径、端口、URL、Tab、selector、等待时间和阈值；
5. 检查文件和函数是否超过维护阈值；
6. 运行仓库级工程审计。

权威规则：

```text
docs/project/CODE_CHANGE_GUARDRAILS.md
docs/project/CODE_CHANGE_GUARDRAILS_IMPLEMENTATION.md
reports/project_engineering_audit_latest.json
```

当前全仓基线：

```text
files_scanned=255
blocker_count=390
```

blocker 未经治理或明确归档前，不得继续向同一大文件叠加新业务逻辑。

## 9. 分层解耦

固定分层：

```text
browser/collector       DOM、selector、真实点击、风险检测
application/service     采集编排、批次、断点、状态机
domain                  SKU、商品、链接、轮次、终态模型
persistence/repository  JSONL/MySQL、事务、原子写入
contracts/schema         schema、枚举、跨系统合同
configuration            typed settings、配置加载
ops                      systemd、部署、备份、状态入口
tests                    fixture、单元测试、无 JD live
```

业务层不得散落 Playwright selector；数据库层不得依赖浏览器对象；Shell/Python 入口只负责参数解析、调用服务和输出 Summary。

强制阈值：

- Python/Shell 单文件超过 300 行：先拆分再修改；
- 单函数超过 80 行：拆分职责；
- 运行入口超过 120 行：收敛为薄入口；
- 浏览器、业务、持久化、发布职责不得混在同一函数。

## 10. 配置与 Secret 分离

禁止在业务代码和运维脚本中散落：

- IP、域名、端口、用户名、绝对路径；
- 页面 URL、Tab 名称、selector、风险词；
- 页面范围、批大小、等待时间、时间窗口和熔断阈值；
- 数据库名、表名、Tunnel 端口；
- 输入输出文件路径；
- 写入、发布和同步开关；
- 密码、Token、Cookie、私钥。

非敏感运行参数进入版本化配置；环境差异进入环境变量；Secret 进入服务器 Secret。默认值只能在一个配置入口定义。

## 11. 数据一致性

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
- HZ24 结果必须区分 `linked`、`unavailable` 和 `pending`；
- unavailable 商品不得进入商用候选。

## 12. 测试与可观测性

- 自动化测试禁止调用 JD live API；
- JD live 仅用于真实浏览器流量或明确手工 smoke；
- 使用 fixture、安全 DOM 快照和模拟 Repository；
- 测试覆盖重复 SKU、风险页、空卡片、字段变化、事务回滚、断点续跑、幂等、checksum、sold-out 和 unavailable 分类；
- 每轮有 round_id；
- 每页有 page_no 和计数；
- 每条失败有 reason；
- 报告记录生成时间、来源 checksum、成功/失败/不可用/待处理和风险；
- 任何报告必须绑定本次运行，禁止失败后复用陈旧报告。

## 13. 商用通用性

- 不针对单个 SKU 或临时 DOM 写死不可复用逻辑；
- selector 使用集中配置和多候选策略；
- 页面、商品、渠道和数据源适配器解耦；
- 数据合同版本化；
- 旧字段兼容期有明确迁移计划；
- 当前只实现京东，不提前堆叠无用抽象；
- 任何正式方案必须包含异常停止、断点、审计、备份、回滚和一致性报告。