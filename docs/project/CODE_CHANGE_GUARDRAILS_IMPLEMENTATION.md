# 代码变更门禁实施说明

更新日期：2026-06-18

本文件修正 `CODE_CHANGE_GUARDRAILS.md` 第 6 节中的实施路径。

当前有效入口：

```text
scripts/engineering_scan.py
scripts/run_engineering_scan_and_publish.sh
```

当前配置与实现：

```text
config/engineering-audit.toml
src/aideal_cps_data_lab/engineering_audit/
```

当前报告：

```text
reports/project_engineering_audit_latest.json
```

在旧文档中的命令或报告路径与本文件不一致时，以本文件为准。
