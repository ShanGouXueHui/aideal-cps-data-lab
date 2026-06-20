# 代码变更门禁实施说明

更新日期：2026-06-20

## 1. 当前有效入口

唯一仓库级全量扫描入口：

```text
scripts/engineering_scan_full.py
```

离线质量入口：

```text
scripts/run_offline_quality.py
```

CI Bridge 执行入口：

```text
scripts/ops/run_data_lab_ci_bridge.sh
```

GitHub Actions 可作为补充验证，但新加坡 `datalab` 是当前主要离线验证替代节点。

旧 `scripts/engineering_scan.py` 不再作为有效扫描入口。

## 2. 执行环境

### 新加坡 CI Bridge

```text
43.106.55.255 / datalab
/home/datalab/projects/aideal-cps-data-lab
```

只运行：

- 编译；
- Offline Quality；
- Engineering Audit；
- 无 JD live 单元测试；
- 脱敏报告回写。

用户可先登录杭州 `121.41.111.36 / cpsdata`，再 SSH 进入新加坡 `datalab`。执行仍发生在新加坡。

## 3. 路径解析

所有扫描和验证脚本必须从自身位置解析仓库根目录，不依赖：

```text
当前 Shell 工作目录
HOME
固定服务器路径
特定 Linux 用户
```

环境差异必须进入版本化配置或环境变量。Secret 不进入 GitHub。

## 4. 当前配置与模块

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

扫描范围包括：

```text
src/
run/
scripts/
config/
tests/
SQL/YAML/systemd/前端工程文件
```

运行数据、Secret、虚拟环境、浏览器 Profile 和构建缓存必须排除。

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
- `full_gate_blocker_count` 全局门禁。

## 6. 已知能力缺口

当前扫描器尚未完整覆盖：

1. Python 模块、类和函数作用域重复变量赋值；
2. Python 模块常量被后定义静默覆盖；
3. Shell 配置变量或默认值重复赋值；
4. TOML/YAML/JSON/INI 同对象重复配置键；
5. 相同默认值由多个配置入口维护；
6. 跨语言重复状态枚举和路径合同。

这意味着：即使 `duplicate_definition=0`，也不能自动推出“重复变量/常量 100% 清零”。下一阶段第一项代码任务是补齐上述扫描能力，并为每类增加单元测试。

建议新 finding category：

```text
duplicate_assignment
duplicate_constant_assignment
duplicate_config_key
duplicate_default_source
```

允许的可变状态赋值应通过显式 allowlist 或状态机语义识别，不能简单把所有二次赋值都判为 blocker。

## 7. 全局门禁

扫描结果必须使用：

```text
full_gate_blocker_count = blocker_count
```

只有全局 blocker 为 0 才返回 PASS。不允许：

- 只检查 active + compatibility；
- 将历史 blocker 降级后宣称完成；
- 扩大 excluded directory 隐藏问题；
- 通过 `continue-on-error` 假装门禁通过。

历史代码应保留在 Git 历史或只读快照分支，并从 main 删除。

## 8. 最新已发布报告

### Engineering Audit

```text
git_head=07b8db89274addd4d85c1308bc41a89a0352abab
generated_at=2026-06-20T13:24:06
files_scanned=298
status=FAIL
blocker_count=210
full_gate_blocker_count=210
active_blocker_count=0
compatibility_blocker_count=0
historical_blocker_count=195
support_blocker_count=15
warning_count=635
```

blocker 分类：

```text
hardcoded_absolute_path=3
hardcoded_ip=42
hardcoded_parameter=107
hardcoded_url=58
```

该报告已落后于当前 main，不能放行后续阶段。

### Offline Quality

```text
git_head=07b8db89274addd4d85c1308bc41a89a0352abab
status=PASS
tests_run=63
failures=0
errors=0
jd_live_called=false
```

同样必须对当前 main 重跑。

## 9. 历史归档状态

```text
历史快照分支：history-snapshot-20260620
```

已移除部分 HZ11-HZ21 Python collector，但最新报告仍列出：

```text
historical blocker=195
historical blocker files=54
support blocker=15
support blocker files=6
```

下一步应将剩余历史 Shell 从 main 移除，不在历史脚本上继续修补生产质量。

## 10. 修改前门禁

任何文件修改前必须检查：

```text
重复函数/类/方法/Shell 函数
重复变量/常量/配置键
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
→ report git_head == current main
→ publish sanitized reports
```

自动化验证必须设置 offline mode，并确认：

```text
jd_live_called=false
```

工程审计存在 blocker 时返回非零是正确行为：报告生成成功，但门禁失败。

## 12. 与商用切换关系

在以下条件全部满足前：

```text
global blocker=0
duplicate definition=0
duplicate assignment=0
duplicate implementation=0
large file=0
long function=0
offline quality=PASS
current HEAD validated=true
```

禁止：

- 继续叠加业务功能；
- 恢复 HZ24；
- 初始化正式 MySQL；
- 开启 dual-write；
- publish；
- AIdeal CPS 正式同步。

允许：

- 只读分析；
- 文档归档；
- 审计器完善；
- 历史代码移出 main；
- 公共模块抽取；
- 测试 fixture 收口；
- 离线单元测试；
- 不访问 JD live 的静态检查。
