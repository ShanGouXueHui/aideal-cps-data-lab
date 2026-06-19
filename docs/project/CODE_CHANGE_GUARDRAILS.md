# 代码变更强制门禁

更新日期：2026-06-18

状态：强制执行，优先级高于一般开发习惯。

## 1. 修改前必须扫描

任何代码、脚本、配置、DDL 或测试修改开始前，必须先完成：

1. 扫描目标文件是否存在同名重复定义；
2. 扫描同一模块及相邻模块是否已有相同实现；
3. 扫描跨文件完全相同或高度重复的函数实现；
4. 扫描环境地址、端口、路径、URL、时间窗口、阈值、Tab 名称、风险词、selector、服务名、数据库名等是否写死；
5. 检查目标文件是否已超过大文件阈值；
6. 运行仓库级工程审计并保存报告。

未完成扫描，不得开始修改；发现阻断项，不得继续叠加新逻辑。

## 2. 禁止重复定义

禁止以下情况：

- 同一 Python 作用域重复定义同名函数或类；
- 同一类中重复定义同名方法；
- 同一 Shell 文件重复定义同名函数；
- 多个运行脚本复制相同业务函数；
- 同一常量、状态枚举、Tab 列表、风险规则、路径合同在多个文件分别维护；
- 旧版本和新版本同时包含可执行的重复业务实现，但没有统一适配层或明确下线计划。

公共能力必须进入共享模块，由薄入口调用。脚本只负责参数解析、调用服务和输出 Summary。

## 3. 禁止硬编码

可变化值不得直接写在业务代码或运维脚本中，包括但不限于：

- IP、域名、端口、CDP 地址；
- 用户名、项目绝对路径、服务名；
- 数据库名、表名、Tunnel 端口；
- 页面 URL、Tab 名称、selector、风险关键词；
- 页面范围、批大小、等待时间、时间窗口、熔断阈值；
- 输入输出文件路径；
- 商用开关、发布开关、同步开关；
- Secret、密码、Token、Cookie、私钥。

处理方式：

- 环境差异放环境变量或服务器 Secret；
- 非敏感运行参数放版本化配置文件；
- schema 版本、字段合同、状态枚举放单一共享模块；
- 业务代码通过 typed settings/config provider 读取；
- 测试通过 fixture 注入，不依赖生产默认值。

不得在多个文件重复提供默认值。默认值只能在一个配置入口定义。

## 4. 大文件必须拆分

强制阈值：

- Python/Shell 单文件超过 300 行：禁止继续增加业务逻辑，必须先拆分；
- 单函数超过 80 行：必须拆分职责；
- 单函数圈复杂度明显过高或包含浏览器、业务、持久化、发布多个职责：必须分层；
- 运行入口超过 120 行：必须收敛为薄入口。

固定分层：

```text
browser/collector       DOM、selector、真实点击、风险检测
application/service     用例编排、批次、断点、状态机
 domain                  SKU、商品、链接、结果状态
persistence/repository  JSONL/MySQL、事务、原子写入
contracts/schema         schema、枚举、跨系统合同
configuration            typed settings、配置加载
ops                      systemd、部署、备份、状态入口
tests                    fixture、单元测试、无 JD live
```

## 5. 变更执行顺序

每次变更固定执行：

```text
pre-change scan
→ 复用/抽取公共模块
→ 最小修改
→ 静态检查
→ 单元测试
→ repository audit
→ smoke（禁止自动调用 JD live）
→ 数据一致性检查
→ Git 提交
→ fetch_file/fetch_commit 或服务器 git log 二次确认
```

## 6. 工程审计产物

仓库级扫描工具：

```text
scripts/project_engineering_audit.py
```

报告：

```text
reports/project_engineering_audit_latest.json
reports/project_engineering_audit_latest.md
```

审计必须覆盖：

- 同文件重复定义；
- 跨文件完全重复实现；
- 硬编码环境值和运行参数；
- Secret 风险；
- 大文件和长函数；
- 重复配置常量；
- Python/Shell 基础语法。

审计报告中的 blocker 必须清零后，才允许进入商用切换。
