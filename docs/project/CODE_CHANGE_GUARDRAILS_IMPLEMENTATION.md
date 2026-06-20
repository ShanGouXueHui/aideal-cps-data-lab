# 代码变更门禁实施说明

更新日期：2026-06-20

## 1. 当前有效入口

```text
全量工程审计：scripts/engineering_scan_full.py
离线质量：scripts/run_offline_quality.py
CI Bridge：scripts/ops/run_data_lab_ci_bridge.sh
杭州统一入口：scripts/ops/run_ci_bridge_from_hangzhou.sh
```

GitHub Actions 只作为补充验证；新加坡 `datalab` 是当前主要离线验证替代节点。

## 2. 执行环境

```text
杭州 Data Lab 生产：121.41.111.36 / cpsdata
新加坡 CI Bridge：43.106.55.255 / datalab
```

运维人员从杭州 `cpsdata` SSH 进入新加坡 `datalab`。编译、测试和审计仍在新加坡执行；杭州只是真实生产环境，不代跑 CI Bridge。

新加坡只运行：

- 编译和静态检查；
- Offline Quality；
- Engineering Audit；
- 无 JD live 单元测试；
- 脱敏报告回写。

## 3. 路径与配置规则

所有扫描和验证脚本必须从自身位置解析仓库根目录，不依赖当前工作目录、HOME、固定服务器路径或特定 Linux 用户。

环境差异进入环境变量；非敏感参数进入版本化配置；Secret 不进入 GitHub。默认值只能有一个 typed settings/config 来源。

## 4. 当前审计模块

```text
config/engineering-audit.toml
src/aideal_cps_data_lab/engineering_audit/models.py
src/aideal_cps_data_lab/engineering_audit/limits.py
src/aideal_cps_data_lab/engineering_audit/common.py
src/aideal_cps_data_lab/engineering_audit/python_definitions.py
src/aideal_cps_data_lab/engineering_audit/python_scan.py
src/aideal_cps_data_lab/engineering_audit/shell_scan.py
src/aideal_cps_data_lab/engineering_audit/service.py
src/aideal_cps_data_lab/engineering_audit/inventory.py
```

扫描范围包括 `src/`、`run/`、`scripts/`、`config/`、`tests/` 及 SQL/YAML/systemd/前端工程文件。运行数据、Secret、虚拟环境、浏览器 Profile 和构建缓存必须排除。

## 5. 当前已实现能力

- Python 同作用域重复函数、异步函数、类和方法检测；
- Shell 同文件重复函数检测；
- 跨文件函数 AST 指纹重复实现检测；
- Python/Shell 大文件检测；
- Python 长函数检测；
- 硬编码 URL、IP、绝对路径和命名参数检测；
- 重复字符串提示；
- Python/Shell 基础语法检查；
- finding scope 分类；
- blocker 文件完整清单；
- `git_head` 绑定；
- `full_gate_blocker_count = blocker_count` 全局门禁。

## 6. 尚未完整实现的能力

下一阶段第一项代码任务：补齐以下检测和单元测试。

```text
duplicate_assignment
duplicate_constant_assignment
duplicate_config_key
duplicate_default_source
```

必须覆盖：

1. Python 模块、类和函数作用域重复变量赋值；
2. Python 模块常量被后定义静默覆盖；
3. Shell 配置变量或默认值重复赋值；
4. TOML/YAML/JSON/INI 同对象重复配置键；
5. 相同默认值由多个配置入口维护；
6. 跨语言重复状态枚举和路径合同。

允许的可变状态赋值必须通过状态机语义或精确 allowlist 识别，不能简单把所有二次赋值判为 blocker，也不能使用路径级豁免隐藏问题。

即使 `duplicate_definition=0`，也不能自动推出重复变量和常量已 100% 清零。

## 7. 全局门禁

```text
full_gate_blocker_count = blocker_count
```

只有全局 blocker 为 0 才返回 PASS。不允许：

- 只检查 active + compatibility；
- 将 historical/support blocker 降级后宣称完成；
- 扩大 excluded directory 隐藏问题；
- 通过 `continue-on-error` 假装门禁通过。

历史代码应保留在 Git 历史或只读快照分支，并从 main 删除。

## 8. 最新已提交报告

### Engineering Audit

```text
files_scanned=306
status=FAIL
blocker_count=210
full_gate_blocker_count=210
active_blocker_count=0
compatibility_blocker_count=0
historical_blocker_count=195
support_blocker_count=15
```

当前 blocker 主要是 main 中剩余 HZ12-HZ21 历史 Shell 的硬编码，以及少量 support fixture。该报告必须与当前 main HEAD 对齐后才可用于门禁。

### Offline Quality

```text
git_head=2bf6842a60205eb32916bbad5b193f26fbb9ffde
status=PASS
tests_run=66
failures=0
errors=0
jd_live_called=false
```

该报告只证明上述 commit，必须对当前 main 重跑。

## 9. 历史归档状态

```text
历史快照分支：history-snapshot-20260620
```

已移除部分 HZ11-HZ21 Python collector。下一步应将剩余历史 Shell 从 main 移除，不在历史实验脚本上继续修补生产质量。

## 10. 修改前门禁

任何文件修改前必须检查：

```text
重复函数、类、方法和 Shell 函数
重复变量、常量、配置键和默认值来源
相邻模块已有实现
跨文件重复实现
硬编码
文件行数
函数行数
配置单一来源
当前报告是否绑定当前 main
```

目标文件已超阈值时，先拆分再修改。

## 11. 验证顺序

```text
compile
→ focused unit tests
→ full Offline Quality
→ full Engineering Audit
→ audit/offline git_head == current main
→ publish sanitized reports
```

自动化验证必须设置 offline mode，并确认 `jd_live_called=false`。

工程审计存在 blocker 时返回非零是正确行为：报告生成成功，但门禁失败。

## 12. 商用冻结条件

在以下条件全部满足前：

```text
global blocker=0
full gate blocker=0
duplicate definition=0
duplicate assignment=0
duplicate constant assignment=0
duplicate config key=0
duplicate default source=0
duplicate implementation=0
large file=0
long function=0
offline quality=PASS
current HEAD validated=true
```

禁止继续叠加业务功能、恢复 HZ24、初始化正式 MySQL、开启 dual-write、publish 或 AIdeal CPS 正式同步。