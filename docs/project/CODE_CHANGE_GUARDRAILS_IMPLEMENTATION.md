# 代码变更门禁实施说明

更新日期：2026-06-20

## 1. 有效入口

```text
全量工程审计：scripts/engineering_scan_full.py
离线质量：scripts/run_offline_quality.py
CI Bridge：scripts/ops/run_data_lab_ci_bridge.sh
杭州统一入口：scripts/ops/run_ci_bridge_from_hangzhou.sh
```

CI Bridge 当前职责是离线验证，不再发布质量报告。

## 2. 已实现审计能力

- Python 函数、异步函数、类和方法重复定义；
- Shell 函数重复定义；
- Python/Shell 重复赋值；
- 模块和类常量重复定义；
- TOML、YAML、JSON、INI 重复键；
- 环境变量、配置和 CLI 默认值多源；
- 跨文件函数实现指纹；
- 大文件和长函数；
- Python、Shell 和配置语法；
- finding scope 分类；
- 全局 blocker 门禁；
- `git_head` 绑定。

旧文档中列出的 `duplicate_assignment`、`duplicate_constant_assignment`、`duplicate_config_key` 和 `duplicate_default_source` 能力缺口已经补齐。

## 3. 已验证基线

```text
files_scanned=258
global/full/active/compatibility/historical/support blocker=0
duplicate definition/assignment/constant/config/default/implementation=0
large_file=0
long_function=0
python/shell/config syntax=PASS
offline tests=69
failure=0
error=0
jd_live_called=false
```

72 条 repeated literal 为 warning，不是 blocker。

## 4. 当前未闭环项

```text
CODE_GOVERNANCE_LOGIC_COMPLETE=true
CODE_GOVERNANCE_FORMAL_ACCEPTANCE=false
CURRENT_HEAD_VALIDATED=false
```

代码治理逻辑已经完成，但旧运行任务仍可能把工程审计报告提交到 main。报告提交推进 main 后，原质量报告立即陈旧。

## 5. 报告实现规则

```text
main              代码与 pointer
quality-reports   Full Audit 与 Offline Quality
runtime-evidence  HZ23/HZ24/MySQL readiness
```

- Active Audit 只作为 workflow artifact；
- CI Bridge 只做编译、测试、审计和报告校验；
- 运行报告不得提交到 main；
- 报告必须记录代码 HEAD、生成时间、schema、round_id 和 checksum；
- 通用发布器必须拒绝质量报告和运行证据写 main。

## 6. 验证顺序

```text
compile
→ focused unit tests
→ full Offline Quality
→ full Engineering Audit
→ audit/offline git_head == current main
→ 发布到权威证据分支
→ 再确认 main 未被报告推进
```

自动化验证必须处于 offline mode，并确认 `jd_live_called=false`。

## 7. 当前下一步

1. 在新加坡定位旧 audit publisher；
2. 停止旧 checkout、cron、systemd user timer 或残留命令；
3. 建立并验证 `runtime-evidence` 发布路径；
4. 对 current main 重跑完整门禁；
5. 正式关闭代码治理门禁；
6. 再执行杭州 HZ23 只读核验。

## 8. 商用冻结

在正式报告绑定、HZ23 last-known-good、HZ24 终态和最终候选门禁完成前，禁止恢复 HZ24、初始化 MySQL、开启 dual-write、publish 或 AIdeal CPS 正式同步。
