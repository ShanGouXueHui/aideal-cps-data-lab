# 代码变更强制门禁

更新日期：2026-06-20

状态：强制执行，优先级高于一般开发习惯。代码问题未闭环前，禁止继续功能开发。

## 1. 修改前必须扫描

任何代码、脚本、配置、DDL 或测试修改开始前，必须先完成：

1. 扫描目标文件是否存在同名重复函数、类、方法或 Shell 函数；
2. 扫描同一作用域是否重复定义或静默覆盖变量、模块常量、配置键和默认值；
3. 扫描相邻模块是否已有相同实现；
4. 扫描跨文件完全相同或高度重复的函数和业务流程；
5. 扫描环境地址、端口、路径、URL、时间窗口、阈值、Tab、风险词、selector、服务名和数据库名是否写死；
6. 检查文件、函数和入口是否超过维护阈值；
7. 运行仓库级全量工程审计并保存绑定当前 HEAD 的报告。

未完成扫描，不得开始修改；发现阻断项，不得继续叠加新业务逻辑。

## 2. 禁止重复定义和重复赋值

禁止：

- 同一 Python 作用域重复定义同名函数、异步函数或类；
- 同一类中重复定义同名方法；
- 同一 Shell 文件重复定义同名函数；
- 多个运行脚本复制相同业务函数；
- 旧版本和新版本同时保留可执行重复实现；
- 同一 Python 模块、类或函数作用域重复定义模块常量、配置变量或状态常量；
- 同一 Shell 作用域重复赋值环境配置或默认值，导致前值被静默覆盖；
- 同一 TOML/YAML/JSON/INI 对象出现重复键；
- 同一默认参数在多个文件分别维护；
- 同一 Tab、selector、风险词、路径合同、数据库对象或状态枚举有多个权威来源；
- 使用后定义覆盖前定义来“修复”代码，而不删除旧定义。

允许的运行时状态更新必须：

- 变量语义明确是可变状态，不是配置或常量；
- 更新点位于单一状态机或 service 内；
- 有测试覆盖状态转换；
- 不通过重复定义隐藏旧逻辑。

公共能力必须进入共享模块，由薄入口调用。默认值和配置合同只能有一个权威入口。

## 3. 禁止硬编码

可变化值不得直接散落在业务代码或运维脚本中，包括：

- IP、域名、端口和 CDP 地址；
- 用户名、项目绝对路径和服务名；
- 数据库名、表名和 Tunnel 端口；
- 页面 URL、Tab、selector 和风险关键词；
- 页面范围、批大小、等待时间、时间窗口和熔断阈值；
- 输入输出文件路径；
- 商用、写入、发布和同步开关；
- Secret、密码、Token、Cookie、Profile 和私钥。

处理方式：

- 环境差异放环境变量或服务器 Secret；
- 非敏感运行参数放版本化配置；
- schema、状态枚举和字段合同放单一共享模块；
- 业务代码通过 typed settings/config provider 读取；
- 测试通过集中 fixture 注入；
- 不得在多个文件重复提供默认值。

## 4. 文件和函数阈值

```text
Python/Shell 单文件 >300 行：必须拆分
单函数 >80 行：必须拆分
运行入口 >120 行：必须收敛为薄入口
```

浏览器、业务、持久化和发布职责不得混在同一函数。

固定分层：

```text
browser/collector       DOM、selector、点击、风控
application/service     用例编排、批次、断点、状态机
domain                  SKU、商品、链接、终态规则
persistence/repository  JSONL/MySQL、事务、原子写入
contracts/schema         schema、枚举、跨系统合同
configuration            typed settings、配置加载
ops                       systemd、部署、备份、统一入口
tests                     fixture、单元测试、禁止 JD live
```

## 5. 全局验收，不只看 active

商用前必须同时满足：

```text
global_blocker_count=0
full_gate_blocker_count=0
active_blocker_count=0
compatibility_blocker_count=0
historical_blocker_count=0
support_blocker_count=0
duplicate_definition=0
duplicate_assignment=0
duplicate_constant_assignment=0
duplicate_config_key=0
duplicate_default_source=0
duplicate_implementation=0
large_file=0
long_function=0
python_shell_syntax=PASS
offline_quality=PASS
jd_live_called=false
audit git_head=current main
offline git_head=current main
```

历史代码的正确处理方式是：保留 Git 历史或只读历史快照分支，并从 main 可执行路径移除。不得通过降低严重度、扩大排除目录或只看 active scope 伪造通过。

当前历史快照分支：`history-snapshot-20260620`。

## 6. 变更执行顺序

```text
pre-change scan
→ 确认单一权威实现
→ 复用或抽取公共模块
→ 最小修改
→ 静态检查
→ 单元测试
→ repository audit
→ smoke（自动化禁止 JD live）
→ 数据一致性检查
→ Git 提交
→ fetch_file/fetch_commit 或服务器 git log 二次确认
→ 新加坡 CI Bridge 对当前 main 重跑
→ 报告回写 GitHub
```

工程报告与 Offline Quality 必须验证同一个 commit。陈旧报告不得放行后续阶段。

## 7. 脚本交付规则

- 复杂命令和长脚本直接提交 GitHub；
- 用户只执行仓库内单一 `.sh` 入口；
- 不在聊天中发送大量零散命令；
- 脚本从自身位置解析仓库根目录；
- 不使用 `set -e`；
- 不使用会退出登录 Shell 的 `|| exit 1`；
- 日志写入 `logs/` 或 `reports/`，终端只输出 Summary；
- 生产写入必须有 dry-run、备份、校验、原子提交和回滚。

## 8. 工程审计入口和能力

唯一全量扫描入口：

```text
scripts/engineering_scan_full.py
```

报告：

```text
reports/project_engineering_audit_latest.json
```

审计必须覆盖：

- Python 函数、异步函数、类和方法重复定义；
- Shell 函数重复定义；
- Python/Shell 重复变量、常量和配置赋值；
- 配置文件重复键；
- 默认值多源；
- 跨文件重复实现；
- 硬编码环境值和运行参数；
- Secret 风险；
- 大文件和长函数；
- Python/Shell 基础语法。

当前已知缺口：重复变量、常量、配置键和默认值多源检测尚未完整实现。该能力未补齐并得到零结果前，不得宣称代码重复问题 100% 解决。

## 9. 商用冻结

在全局代码门禁通过前，只允许只读分析、文档归档、历史代码移出 main、审计器完善、公共模块抽取、fixture 收口和不访问 JD live 的离线测试。

禁止继续叠加业务功能、恢复 HZ24、初始化正式 MySQL、开启 dual-write、publish 或 AIdeal CPS 正式同步。