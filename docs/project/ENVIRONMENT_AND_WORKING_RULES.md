# 环境、周边系统与协作规则

更新日期：2026-06-14

## 1. 服务器与仓库

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

noVNC 常用入口：

```text
http://121.41.111.36:18772/vnc.html?autoconnect=true&resize=scale
```

密码属于服务器秘密，不写入 GitHub；从 `.secrets/x11vnc.pass` 管理。

### AIdeal CPS 生产服务器

```text
公网 IP：8.136.28.6
用户：deploy
项目目录：/home/deploy/projects/aideal-cps
GitHub：ShanGouXueHui/aideal-cps
默认分支：main
```

当前技术栈：

```text
FastAPI
SQLAlchemy
Alembic
MySQL / schema aideal_cps
Nginx / systemd
公众号 + H5
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

- 京东联盟手工登录和浏览器会话；
- 商品推广/全部商品 4000 池采集；
- SKU、标题、图片、价格、佣金等解析；
- 推广短链生成和刷新；
- 风控检测和安全停止；
- 数据去重、历史、快照、质量门禁；
- 未来 Data Lab MySQL 主数据。

### AIdeal CPS 负责

- 微信/H5 用户入口；
- 商品推荐、搜索和展示；
- 点击归因；
- 订单和返佣；
- AI 推荐理由；
- 本地 MySQL 业务数据；
- 从 Data Lab 定时同步已发布佣金商品。

用户请求不得实时依赖 Data Lab 浏览器、SSH 或远程数据库。

## 3. 交互习惯

1. 全程使用中文，职业化、直接、结构化。
2. 优先直接读取和修改 GitHub，不依赖聊天短期上下文。
3. 每次写 GitHub 后，必须使用 `fetch_file`、`fetch_commit` 或服务器 `git log` 二次确认。
4. GitHub 连接器写入不稳定、不弹确认或未落库时，立刻改用服务器本地 `git add / commit / push`。
5. 日志优先由脚本生成到 `logs/`、`reports/` 或 `docs/debug/`，必要摘要提交 GitHub；用户不复制大段日志。
6. 用户只贴最终 `SUMMARY`；助手直接从 GitHub读取详细报告。
7. 定位问题时一问一答，避免一次给多个不相关排障分支。
8. 不用话术掩盖工程问题；价格、佣金、链接和数据一致性必须通过机制验证。
9. 用户允许必要时手工登录京东联盟，但账号密码不得进入脚本。
10. 不使用 Codex CLI，除非用户重新明确要求。

## 4. 命令规范

- Linux 命令必须 copy-paste 可执行；
- 不使用 `set -e`；
- 每次命令分小步；
- 每一步包含路径、分支/HEAD、最小修改、静态检查、smoke 和摘要；
- 屏幕输出控制在关键 80-180 行；
- 大日志写文件，不让用户粘贴整个日志；
- 不用未确认路径执行 `rm -rf`；
- 运行中报告和数据不要随意提交，结束后提交稳定摘要；
- `backups/` 可以保留在本机，但不作为正式代码来源。

## 5. Git 与分支规则

- 正式代码只有 `main` 一个主流分支；
- 可以临时备份文件或创建短期修复分支，但完成后必须合并/清理；
- 不长期维护多个功能分叉；
- 运行时数据、日志、Profile、Secret 不进入 Git；
- 文档和 schema 必须随代码同一变更窗口更新；
- 每个关键节点建立可验证 commit；
- commit message 使用 `dl2:`、`docs:`、`fix:`、`chore:` 等明确前缀；
- push 后二次确认 remote HEAD 和文件内容。

## 6. 编程规范

### 分层解耦

建议固定分层：

```text
browser/collector       浏览器与 DOM 操作
application/service     采集编排、刷新和发布用例
domain                   商品、链接、轮次、状态模型
persistence/repository  JSONL/MySQL 持久化实现
contracts/schema         跨系统合同和 schema
ops                      systemd、部署、备份和状态命令
tests                    无 JD live 的自动化测试
```

业务层不得直接散落 Playwright selector；数据库层不得依赖浏览器对象。

### 配置分离

- 服务器、端口、等待区间、页面范围、数据库 DSN、开关使用环境变量或配置文件；
- 默认值可以进入代码，密码/Token/私钥不能进入代码；
- `.env`、`.secrets/`、SSH 私钥、Cookie、Profile 必须 gitignore；
- 商用和测试配置分离；
- feature flag 控制 candidate/published 和正式同步开关。

### 数据一致性

- SKU 是唯一业务键；
- 金额使用 Decimal/DECIMAL，不使用二进制 float 作为持久化金额；
- 佣金率统一存为数值百分比，合同明确单位；
- 所有写入幂等；
- 使用事务、唯一约束和原子文件替换；
- 未变化记录只更新时间戳；
- 变更记录保留 payload hash；
- 同一轮次不得重复生成不一致结果；
- 删除采用 inactive/软删除，不能因单次异常物理删除。

### 可观测性

- 每轮有 round_id；
- 每页有 page_no 和计数；
- 每条失败记录 reason；
- 报告包括开始/结束时间、成功/失败、已知 SKU、风险信号、未完成页；
- systemd 服务可自动重启；
- 状态命令只输出紧凑摘要；
- GitHub 保存关键运行结论，不保存敏感原始材料。

### 测试原则

- 自动化测试不能调用 JD live API；
- 使用 fixture、保存的安全 DOM 结构或模拟 Repository；
- JD live 只允许真实微信流量或显式手工 smoke；
- 测试必须覆盖：重复 SKU、错误页、风险页、空卡片、字段变化、事务回滚、断点续跑、幂等和 checksum；
- 上线前执行静态检查、最小 smoke、数据质量检查和回滚验证。

## 7. 商用通用性原则

- 不针对单个 SKU、单次页面或临时 DOM 写死不可复用逻辑；
- selector 需要可替换和多候选策略；
- 页面、商品、渠道、数据源适配器解耦；
- 数据合同版本化；
- 旧字段兼容期有明确截止和迁移计划；
- 支持未来扩展淘宝、拼多多、抖音，但当前主线只实现京东，不提前堆叠无用抽象；
- 任何“最终方案”必须包含异常停止、断点、重试、审计、备份、回滚和安全边界。

## 8. 模型与 AI 使用

Data Lab 当前核心采集、佣金、推广链接和数据质量不依赖大模型。

AIdeal CPS 可以使用 Qwen 等模型生成推荐理由和标签，但：

- AI 不决定佣金、价格或链接真实性；
- 模型失败不能影响商品访问和推广跳转；
- AI 字段与 Data Lab 源字段分离；
- Data Lab 同步不能覆盖 `ai_reason`、`ai_tags`；
- 模型 Key 仅存服务器 Secret/`.env`。
