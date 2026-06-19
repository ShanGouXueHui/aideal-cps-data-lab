# 代码变更门禁实施说明

更新日期：2026-06-19

## 1. 当前有效入口

唯一仓库级扫描入口：

```text
scripts/engineering_scan_full.py
```

服务器包装入口：

```text
scripts/run_engineering_scan_and_publish.sh
```

CI 入口：

```text
.github/workflows/engineering-audit.yml
```

旧 `scripts/engineering_scan.py` 已被 path-independent 全量入口取代，不再作为有效扫描入口。

## 2. 路径解析

扫描入口必须从自身文件位置解析仓库根目录，不依赖：

```text
当前 Shell 工作目录
HOME
固定服务器路径
特定 Linux 用户
```

服务器包装脚本同样从 `scripts/` 自身位置解析仓库根目录。`project_directory_missing` 的旧固定路径问题已经修正。

## 3. 当前配置与实现

```text
config/engineering-audit.toml
src/aideal_cps_data_lab/engineering_audit/models.py
src/aideal_cps_data_lab/engineering_audit/limits.py
src/aideal_cps_data_lab/engineering_audit/common.py
src/aideal_cps_data_lab/engineering_audit/python_scan.py
src/aideal_cps_data_lab/engineering_audit/shell_scan.py
src/aideal_cps_data_lab/engineering_audit/service.py
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

## 4. 当前报告

```text
reports/project_engineering_audit_latest.json
```

2026-06-19 基线：

```text
files_scanned=255
blocker_count=390
```

blocker 包括：

- 同文件重复定义；
- 跨文件重复实现；
- 硬编码 URL/IP/端口/路径/参数；
- 大文件；
- 长函数；
- 多版本历史实验脚本并存。

## 5. 报告解释

审计返回非零不一定表示扫描器失败：

```text
报告成功生成 + blocker_count>0 -> 审计成功，但工程门禁失败
报告未生成/编译失败 -> 扫描器执行失败
```

CI 会上传报告 artifact，并在 blocker 存在时使检查失败。

## 6. 治理顺序

不得机械地一次性重写所有历史代码。固定顺序：

```text
识别生产活跃路径
-> 标记只读历史归档
-> 修复活跃路径重复定义
-> 抽取重复实现
-> 配置收口
-> 拆分大文件和长函数
-> 运行单元测试
-> 全量复扫
```

历史实验脚本只有在满足以下条件后才可从活跃 blocker 中排除：

1. 不被 systemd、当前脚本、测试或 import 引用；
2. 有明确归档目录或清单；
3. 不作为当前业务实现被调用；
4. 归档动作保留 Git 历史和审计记录。

## 7. 修改前门禁

任何文件修改前必须检查：

```text
重复定义
相邻模块已有实现
跨文件重复实现
硬编码
文件行数
函数行数
配置单一来源
```

未完成预扫描，不得开始修改；发现目标文件已超阈值，必须先拆分。

## 8. 与商用切换关系

当前 HZ23/HZ24/MySQL 活跃主线 blocker 未处理前：

```text
禁止继续叠加大功能
禁止初始化正式 MySQL
禁止开启 dual-write
禁止 publish
禁止 AIdeal CPS 正式同步
```

允许执行：

- 只读分析；
- 文档归档；
- blocker 分类；
- 公共模块抽取；
- 离线单元测试；
- 不访问 JD live 的静态检查。