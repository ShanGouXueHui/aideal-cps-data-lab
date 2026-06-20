# AIdeal CPS Data Lab 项目记忆与长期约束

更新日期：2026-06-20

## 项目与仓库

- Data Lab：`ShanGouXueHui/aideal-cps-data-lab`。
- AIdeal CPS：`ShanGouXueHui/aideal-cps`。
- 正式代码只有一个 `main`。
- 历史实验只保留在 Git 历史或只读快照。
- 证据分支不是第二代码主线。

Data Lab 负责京东联盟授权采集、商品和推广资格、可信短链、终态、质量门禁、源数据和版本化发布。AIdeal CPS 负责终端用户、搜索推荐、归因、订单和返佣。

## 环境角色

- 杭州 `cpsdata`：唯一 Data Lab 生产环境，允许真实 JD、HZ23/HZ24、生产状态和未来 Data Lab MySQL。
- 新加坡 `datalab`：离线验证节点，只运行编译、Offline Quality、Engineering Audit 和无 JD live 测试。
- 杭州 `deploy`：AIdeal CPS 生产，只消费已发布数据。

杭州到新加坡统一使用 SSH 别名 `sg-aideal-datalab`。正确用户是 `datalab`，不是 `cpsdev`。`datalab` 不在 sudoers。

## 数据与模型边界

- Data Lab 是佣金商品源数据权威；SKU 是唯一业务键。
- 金额使用 Decimal/DECIMAL，写入幂等、事务化并保留 lineage。
- unavailable 不进入 published。
- 用户请求只读取 AIdeal CPS 本地 MySQL。
- JSONL 永久保留为回填、快照、审计和灾备格式。
- 价格、佣金、推广链接和状态判断不得依赖大模型。
- AI 推荐字段与 Data Lab 源字段分离。

## 固定分层

```text
browser/collector       DOM、selector、点击、风险检测
application/service     用例编排、批次、断点、状态机
domain                  SKU、商品、链接、终态规则
persistence/repository  JSONL/MySQL、事务、原子写入
contracts/schema         schema、枚举、跨系统合同
configuration            typed settings、配置加载
ops                       systemd、部署、备份、验证入口
tests                     fixture、单元测试、禁止 JD live
```

- selector 只能位于浏览器适配层或集中配置。
- 数据库层不得依赖浏览器对象。
- Shell/Python 入口必须是薄入口。
- 默认值只能有一个 typed settings/config 来源。
- 正式能力必须适用于通用商品、批次和页面，不能为单 SKU 或临时 DOM 写死。
- 当前只实现京东，不提前堆叠无业务价值的多平台抽象。

## 工程硬门禁

```text
global/full 及全部 scope blocker=0
duplicate definition/assignment/constant/config/default/implementation=0
large file=0
long function=0
python/shell/config syntax=PASS
offline quality=PASS
jd_live_called=false
report git_head=current main
```

当前扫描器已经完整覆盖重复函数、变量、常量、配置键、默认值多源和跨文件实现。

阈值：Python/Shell 单文件 300 行、函数 80 行、运行入口 120 行。超过阈值必须先拆分。

## 报告架构

- `main`：代码、配置、合同、测试、文档和非权威指针。
- `quality-reports`：Engineering Audit 与 Offline Quality。
- `runtime-evidence`：HZ23、HZ24 和 MySQL readiness 脱敏证据。

运行报告不得提交到 main。CI Bridge 只验证，不承担质量报告发布。

## 配置与 Secret

非敏感共享参数进入版本化配置；环境差异进入环境变量；Secret 进入服务器 Secret。密码、Token、Cookie、Profile、私钥和数据库密码不得进入 GitHub。

## 交互习惯

- 中文、职业化、直接、结构化。
- 优先直接读取、修改和确认 GitHub。
- 长代码、复杂脚本和文档直接上传 GitHub。
- 用户只执行仓库内审核过的单一 `.sh` 入口。
- 日志写入 `logs/`、`reports/` 或 `docs/debug/`，用户只返回 Summary。
- 每次 GitHub 写入后二次确认。
- 不使用 Codex CLI。
- Shell 不使用 `set -e`。
- 自动测试禁止 JD live。

## 当前长期记忆

- 代码治理逻辑已经清零，正式验收仍因报告绑定未闭环。
- 新加坡可能存在旧任务继续把工程审计提交到 main。
- 必须先停止旧任务并建立 `runtime-evidence`，再执行 HZ23 只读盘点。
- HZ23 last-known-good 为 3304 行，当前 latest 为 0 行无效。
- HZ24 72/5/144 无生产落地证据。
- MySQL、publish 和 AIdeal CPS 同步均未开始。
