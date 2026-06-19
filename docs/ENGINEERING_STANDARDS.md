# Data Lab 编程与交付规范

> 最后更新：2026-06-19  
> 适用范围：`aideal-cps-data-lab` 的代码、配置、脚本、报告、CI、运行和交接。

## 1. 基本原则

1. **正确性优先**：价格、佣金、短链和可推广状态必须来自可追溯数据机制，不用文案或猜测补齐。
2. **安全优先**：遇到京东风控、验证码、登录失效立即停止，不绕过、不自动重试撞库。
3. **分层解耦**：页面、应用、领域结果、持久化、验证和导入相互隔离。
4. **配置分离**：环境与业务参数进入 `config/` 或环境变量，代码只消费 typed settings。
5. **单主流实现**：`main` 为唯一主流分支，同一能力只有一个 canonical implementation。
6. **可恢复与幂等**：中断后从 checkpoint 继续；同一 SKU 重跑不生成重复记录。
7. **证据驱动**：没有报告、manifest、hash、测试或现场日志支持的结论，不写成“已完成”。

## 2. 目录与分层

推荐结构：

```text
config/                         配置与策略
run/                            极薄运行入口、运行状态
scripts/                        构建、验证、诊断、运维入口
src/aideal_cps_data_lab/
  application/                  用例与编排
  domain/                       领域模型和业务不变量
  contracts/                    数据合同和序列化
  persistence/                  文件/MySQL repository
  hz24/                         HZ24 页面采集子域
reports/                        可提交的非敏感报告
logs/                           本地运行日志，默认不提交
tests/                          单元、合同、门禁和回归测试
```

禁止：

- 在 `run/*.py` 中长期堆积数百行业务逻辑；
- 页面适配器直接写生产数据库；
- validator 调用浏览器产生副作用；
- importer 自己重新解析网页；
- 同一字段在多个脚本中各自定义不同含义。

## 3. 入口与服务

- CLI/脚本入口控制在约 20–40 行，负责参数和退出码。
- 单个函数目标不超过 80 行；单文件目标不超过 300 行。超过时按职责拆分，不做机械切片。
- 每个 service 接收明确的 settings/repository/adapter，不读取隐式全局状态。
- 纯函数用于：哈希、URL 校验、字段校验、终态分类、差异计算。
- 外部副作用集中在 adapter/repository/session 边界，便于测试和替换。

## 4. 配置规范

必须配置化的项目包括：

- host、port、scheme、URL path/query；
- 文件路径、schema version、service 名称；
- timeout、sleep、batch、failure fuse；
- 频道、风控标记、允许的终态原因；
- 链接过期和刷新窗口；
- 验证必填字段和来源标识。

优先级：环境变量覆盖 TOML，TOML 覆盖代码默认值。除非是语言级常量或稳定算法常量，禁止新增代码硬编码。

所有配置加载失败必须 fail closed：报告缺失键和文件路径，不使用静默兜底继续商业采集。

## 5. 数据合同与版本

- schema 使用明确版本，如 `.../v1`、`.../v2`。
- schema 升级时记录：新增字段、删除字段、语义变化、兼容策略、迁移方式。
- manifest 必须绑定数据文件 hash 和 row count。
- record hash 的字段集合必须固定并复用；构造端与验证端不得各写一套列表。
- 金额、比例、时间、SKU 的类型和单位必须在合同中固定。
- 原始页面文本只能作为诊断证据，不能成为生产主合同的无界字段。

## 6. 幂等、恢复与并发

- JSONL 写入按 SKU upsert，并采用临时文件原子替换。
- checkpoint 在每个 SKU 终态后更新。
- linked、unavailable、pending 三个集合必须可由持久化结果重建。
- 同一队列只允许一个 active collector；需使用 lock/PID/systemd 状态防止并发双写。
- supervisor 不得对风险退出码无限重启。
- 重跑必须保持记录唯一、hash 可验证、结果可解释。

## 7. 错误分类

错误必须分为：

- `terminal business state`：sold out、delisted、not promotable；
- `retryable interaction failure`：点击、modal、临时网络、元素时序；
- `configuration/integrity failure`：配置缺失、queue hash 错误、schema 不匹配；
- `risk/session failure`：验证码、滑块、登录失效、风险页；
- `programming defect`：异常、合同破坏、不可达状态。

不得把 terminal business state 计入连续技术失败熔断；不得把风险错误当普通 retryable failure。

## 8. 测试要求

每个改动至少覆盖对应层：

- 纯函数单元测试；
- repository 幂等和原子写测试；
- schema/hash/manifest 合同测试；
- linked/unavailable/pending accounting 测试；
- 风险和 failure fuse 状态机测试；
- 入口 compile/import smoke；
- 不连接京东的 CI 静态测试；
- 杭州采集机上的最小授权 session smoke；
- 完整批次 E2E 仅在 smoke 通过后执行。

CI 不安装浏览器二进制即可完成纯单元测试；真实页面测试不得在 GitHub Actions 中登录京东账号。

## 9. 日志与报告

- 日志写入 `logs/`，运行状态写入 `run/`，稳定报告写入 `reports/`。
- 屏幕输出以 JSON summary 或最后 80–180 行关键日志为主。
- 日志字段至少包括：timestamp、run/round、worker、event、tab、sku、outcome、reason。
- 禁止记录：密码、Cookie、session、二维码、完整 HTML/HAR、个人账户信息。
- 报告中的样本数量要有限制，避免把全量敏感页面内容提交 GitHub。

## 10. Git 与版本策略

- `main` 是唯一主流分支；日常直接在 GitHub 形成小而清晰的提交。
- 不创建长期 `v2`、`v3`、`rewrite`、`backup` 业务分支。
- 兼容入口必须委托 canonical service；迁移结束后删除。
- 备份使用：tag、release、artifact、数据库快照或归档包。
- 每个提交只解决一个主题；文档、配置、代码和测试应在同一主题提交链中同步更新。
- 禁止提交临时凭证、浏览器会话、生产 `.env`、运行锁、私密截图和原始账户页面。

## 11. GitHub 直接协作规范

- ChatGPT 默认直接读取/修改 GitHub 文档和代码，不让用户通过超长 shell heredoc 改文件。
- GitHub 中的代码、报告和交接文档是事实源；回答前先核对当前版本。
- 用户需要现场执行时，只给最小命令；不使用 `set -e`。
- 每一步固定包含：
  1. `pwd`/路径确认；
  2. `git status --short`；
  3. 最小执行动作；
  4. compile/unit/smoke；
  5. 日志路径；
  6. 仅 tail 关键输出。
- 一问一答排障，不在一个回合同时修改多个独立故障域。

## 12. 商用发布定义

“可商用”至少满足：

- 没有敏感信息进入仓库；
- 当前主线 CI 静态检查通过；
- 授权 session smoke 通过；
- 完整队列 accounting 为 100%；
- validation manifest `merge_allowed=true`；
- dry-run importer 输出可审计；
- 生产写入有显式批准、幂等键、landed validation 和回滚方案；
- 运行手册和 STOP_REQUIRED 恢复手册已验证。

在上述条件未全部满足前，只能称为“candidate”或“已完成某阶段验证”，不能称为已上线商用。
