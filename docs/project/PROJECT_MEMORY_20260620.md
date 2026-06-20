# AIdeal CPS Data Lab 项目记忆与长期约束

更新日期：2026-06-20

状态：新对话长期记忆入口。本文记录项目设计、环境角色、工程规范、交互习惯和不可逆决策；运行进展以最新状态文档和报告为准。

## 1. 项目定位

AIdeal CPS Data Lab 是“智省优选 / AIdeal CPS”的京东联盟佣金商品数据生产系统，负责：

- 使用已授权的京东联盟浏览器会话采集商品；
- 维护 SKU、标题、图片、价格、佣金、推广资格和商品终态；
- 生成并校验可信 `u.jd.com` 推广短链；
- 维护可审计的 JSONL、state、history、report 和未来 Data Lab MySQL；
- 生成版本化发布数据，供 AIdeal CPS 商用系统定时同步。

Data Lab 不直接服务终端用户。微信/H5、搜索、推荐、点击归因、订单和返佣由 `ShanGouXueHui/aideal-cps` 负责。

## 2. 仓库和唯一主线

```text
Data Lab：ShanGouXueHui/aideal-cps-data-lab
AIdeal CPS：ShanGouXueHui/aideal-cps
正式代码分支：main
```

规则：

- 正式版本只有一个主流分支 `main`；
- 可以建立只读历史快照分支或短期修复分支，但不得长期分叉；
- 历史实验代码不得与正式实现同时留在 main 作为可执行主线；
- 当前历史快照分支：`history-snapshot-20260620`；
- 备份不等于正式代码来源，恢复后必须重新进入审计和测试链。

## 3. 环境拓扑

### 3.1 杭州 Data Lab 生产

```text
服务器：Ubuntu-datacollection
公网 IP：121.41.111.36
用户：cpsdata
项目目录：/home/cpsdata/projects/aideal-cps-data-lab
角色：唯一 Data Lab 生产环境
Chrome CDP：127.0.0.1:19228
X11 display：:79
x11vnc：59072
noVNC/websockify：18772
systemd：aideal-hz23-observer.service
```

只有该环境允许：

- 真实 JD 登录和浏览器 Profile；
- HZ23/HZ24 真实采集；
- 生产 linked/unavailable/pending 状态写入；
- Data Lab MySQL 初始化、回填、dual-write 和发布。

### 3.2 新加坡 CI Bridge

```text
服务器：Ubuntu-Oris-OpenClaw
公网 IP：43.106.55.255
Data Lab 隔离用户：datalab
Data Lab 目录：/home/datalab/projects/aideal-cps-data-lab
其他项目用户：cpsdev
角色：替代 GitHub Actions 的离线验证节点
```

只允许：

- Git 拉取；
- Python 编译、静态检查；
- Offline Quality；
- Engineering Audit；
- 无 JD live 的单元测试；
- 回写脱敏报告。

禁止保存或运行：JD Cookie、Profile、账号资料、生产 JSONL、生产数据库、真实采集、MySQL 生产写入和商用同步。

### 3.3 AIdeal CPS 生产

```text
服务器：8.136.28.6
用户：deploy
项目目录：/home/deploy/projects/aideal-cps
MySQL：aideal_cps
systemd：aideal.service
```

它是消费端生产环境，不承担京东联盟浏览器采集。

### 3.4 统一登录方式

运维人员可以只登录杭州 Data Lab 服务器，再从杭州 SSH 进入新加坡：

```text
121.41.111.36 / cpsdata
        ↓ SSH
43.106.55.255 / datalab
```

SSH 只减少人工切换，不改变角色边界，也不用于复制生产数据、Secret 或数据库备份。代码与报告仍通过 GitHub 交接。

## 4. 数据与数据库边界

### 4.1 Data Lab 目标 MySQL

```text
database：aideal_cps_data_lab
commission_products
commission_refresh_runs
commission_product_history
commission_publish_versions
v_published_commission_products
```

约束：

- MySQL 只监听 Data Lab `127.0.0.1:3306`；
- 不开放公网 3306；
- Data Lab 是佣金商品源数据权威；
- SKU 是唯一业务键；
- 金额使用 Decimal/DECIMAL；
- 所有写入幂等、事务化，并保留 payload hash 和 lineage；
- 不物理删除商品；
- unavailable 不得进入 published。

### 4.2 AIdeal CPS 消费方式

AIdeal CPS 定时任务使用短生命周期 SSH Tunnel 和只读数据库用户读取 Data Lab 已发布视图，再同步到本地 `aideal_cps.products`。

用户请求只能读取 AIdeal CPS 本地 MySQL，不得实时依赖 Data Lab、远程 MySQL、SSH Tunnel 或浏览器。

JSONL 永久保留为回填输入、不可变快照、审计、灾备和跨系统兜底出口。

## 5. 模型边界

- Data Lab 的价格、佣金、推广链接、SKU、状态和质量判断不得依赖大模型；
- AIdeal CPS 可选使用 Qwen 等模型生成推荐理由和标签；
- AI 不得决定或改写价格、佣金和链接真实性；
- 模型失败不能阻断商品访问；
- Data Lab 同步不得覆盖 AIdeal CPS 的 `ai_reason`、`ai_tags`；
- 模型 Key 只存在服务器 Secret/`.env`。

## 6. 固定分层

```text
browser/collector       DOM、selector、真实点击、风险检测
application/service     用例编排、批次、断点、状态机
domain                  SKU、商品、链接、终态和业务规则
persistence/repository  JSONL/MySQL、事务、原子写入
contracts/schema         schema、枚举、跨系统合同
configuration            typed settings、配置加载
ops                       systemd、部署、备份、验证入口
tests                     fixture、单元测试、禁止 JD live
```

边界：

- selector 只能在浏览器适配层或集中配置；
- 数据库层不得依赖 Playwright/browser 对象；
- Shell/Python 入口必须是薄入口，只做参数解析、调用服务和输出 Summary；
- 当前只实现京东，不提前堆叠无业务价值的多平台抽象；
- 正式能力必须可复用，禁止为单一 SKU、单次 DOM 或临时故障写死专用逻辑。

## 7. 代码治理硬门禁

任何功能推进前必须先完成代码治理。验收口径为全局，不只检查 active scope：

```text
global_blocker_count=0
full_gate_blocker_count=0
duplicate_definition=0
duplicate_assignment=0
duplicate_implementation=0
large_file=0
long_function=0
python/shell syntax=PASS
offline_quality=PASS
jd_live_called=false
report git_head=current main
```

特别要求：

- 禁止同一作用域重复定义函数、类、方法和 Shell 函数；
- 禁止同一作用域重复定义或覆盖配置变量、模块常量和状态常量，除非显式标注为运行时状态更新；
- 禁止多文件复制相同业务实现；
- 公共逻辑必须抽取到共享模块；
- 默认值只能在一个 typed settings/config 入口定义；
- Python/Shell 单文件超过 300 行必须拆分；
- 单函数超过 80 行必须拆分；
- 运行入口超过 120 行必须收敛为薄入口；
- 历史实验脚本应保留在历史快照分支，main 不承担历史可执行实现。

已知审计能力缺口：当前扫描器已覆盖重复函数/类/方法、Shell 函数和跨文件函数指纹，但尚未完整覆盖 Python/Shell 重复变量或常量赋值。完成该检测并取得零结果前，不得宣称“重复定义 100% 清零”。

## 8. 配置与 Secret

禁止在业务代码和运维脚本散落：

- IP、域名、端口、用户名和绝对路径；
- 页面 URL、Tab、selector、风险词；
- 页面范围、批大小、等待时间、时间窗口、熔断阈值；
- 数据库名、表名、Tunnel 端口；
- 输入输出路径、服务名和开关；
- 密码、Token、Cookie、Profile、私钥。

处理规则：

- 非敏感共享参数进入版本化配置；
- 环境差异进入环境变量；
- Secret 进入服务器 Secret；
- 测试通过集中 fixture 注入；
- 不在 GitHub 提交账号、密码、Cookie、Profile、Token、私钥或数据库密码。

## 9. 交互与执行习惯

- 使用中文，职业化、直接、结构化；
- 优先直接读取、修改和确认 GitHub，不依赖聊天短期上下文；
- 代码、长脚本和复杂命令直接上传 GitHub，不在聊天中打印；
- 用户只执行仓库内已审核的 `.sh` 入口，避免零散命令和复制截断；
- 操作时从杭州 `cpsdata` 登录，再 SSH 进入新加坡 `datalab` 执行离线验证脚本；
- 详细日志写入 `logs/`、`reports/`、`docs/debug/`，用户只返回紧凑 Summary；
- 助手从 GitHub读取报告，不要求用户重复复制旧日志；
- 每次 GitHub 写入后必须 `fetch_file`、`fetch_commit` 或服务器 `git log` 二次确认；
- 不使用 Codex CLI；
- Linux 脚本不使用 `set -e`，也不使用会退出登录 Shell 的 `|| exit 1`；
- 自动测试不得调用 JD live；
- 真实京东登录/验证可人工完成，但不得写入脚本和日志。

## 10. 当前不可推进事项

在代码治理和当前候选回归未闭环前，保持：

```text
HZ24 collection paused
Data Lab MySQL uninitialized
DATA_LAB_DB_WRITE_ENABLED=false
DATA_LAB_DB_DUAL_WRITE_ENABLED=false
DATA_LAB_PUBLISH_ENABLED=false
DATA_LAB_SYNC_ENABLED=false
AIdeal CPS production sync disabled
```

## 11. 冲突处理

```text
当前 main 代码和绑定当前 HEAD 的运行报告
> docs/status/COMMERCIALIZATION_STATUS_20260620.md
> docs/project/CURRENT_PROJECT_CONTEXT.md
> 本文
> 专项架构与计划
> 2026-06-19 及更早的状态快照
> 历史实验文档
```

任何旧文档中的数量和状态都必须先与最新报告的 `generated_at`、`git_head`、round_id 和 checksum 对齐。