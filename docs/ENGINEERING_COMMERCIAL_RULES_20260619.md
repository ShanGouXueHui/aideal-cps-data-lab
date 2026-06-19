# DL2 工程与商用规则 — 2026-06-19

> 状态：强制规则。与旧文档冲突时，以本文及 `COMMERCIALIZATION_HANDOFF_20260619.md` 为准。

## 1. 修改前必须扫描

修改任何代码、脚本、配置、DDL 或测试前必须：

1. 扫描目标作用域是否存在同名重复定义；
2. 扫描相邻模块和全仓是否已有相同能力；
3. 扫描复制实现、重复常量、重复配置和长期 v2/v3 平行实现；
4. 扫描 host、port、scheme、URL、路径、timeout、sleep、batch、频道、risk、selector、schema、service、数据库名等硬编码；
5. 检查目标文件和函数规模；
6. 确认复用或抽取方案后再做最小修改。

未完成扫描不得修改。发现重复定义或主线硬编码时，先修复结构问题，不继续叠加业务逻辑。

## 2. 分层

固定职责：

- `browser/collector`：CDP、DOM、selector、真实点击、modal、风险识别；
- `application/service`：用例、批次、会话、生命周期、状态机；
- `domain`：SKU、商品、佣金、链接、状态、结果分类；
- `persistence/repository`：JSONL/MySQL、事务、原子写、互斥、历史；
- `contracts/schema`：schema、枚举、manifest、跨系统合同；
- `configuration`：TOML、typed settings、env/secret；
- `ops`：systemd、timer、lock、备份、发布、回滚、状态命令；
- `tests`：fixture、unit、contract、offline smoke；
- `importer/sync`：生产 dry-run、幂等导入、landed validation。

入口只负责参数、调用、退出码和紧凑 SUMMARY。selector 不得散落到业务层。validator 不得依赖浏览器会话。

## 3. 文件和函数规模

- Python/Shell 单文件超过约 300 行：禁止继续堆叠业务逻辑，先按职责拆分；
- 单函数超过约 80 行：拆分职责；
- 入口建议 20–40 行；
- 同一函数同时包含浏览器操作、业务判断、持久化和发布时必须拆分；
- 拆分以业务职责为边界，不做机械分片或循环 import。

## 4. 配置和 Secret

必须配置化：

- host、port、scheme、URL、路径；
- timeout、sleep、batch、时间窗口、熔断阈值；
- 频道、selector、risk marker；
- service、database、table/view、schema；
- 文件合同、状态文件、报告路径；
- write、dual-write、publish、sync 开关。

非敏感默认值只能在一个配置入口定义。环境差异使用 env。密码、Token、Cookie、session、私钥、数据库 Secret 不进入 GitHub。

## 5. 数据规则

- SKU 是唯一业务键；
- 金额使用 Decimal/DECIMAL；
- 写入必须幂等；
- 文件使用原子替换；数据库使用事务、唯一约束和版本化 migration；
- linked 与 unavailable 必须互斥；
- 未变化记录只更新观察时间；业务字段变化才写 history；
- 商品不物理删除；连续完整成功轮次缺失后才 inactive；
- queue、record、manifest 和 publish version 都有 hash；
- 数据一致性必须可重放、可验证、可回滚。

## 6. 测试和真实流量

- 自动化测试禁止访问 JD live API 或真实京东联盟页面；
- 页面真实流量仅用于明确的人工授权 smoke/E2E；
- 风险、验证码、滑块、登录失效必须 fail closed；
- 禁止绕过验证；
- 当前 HEAD compile/unit/contract 未通过时，不进入 live smoke；
- live smoke 未通过时，不进入全量 accounting；
- validation 未通过时，不进入数据库发布或生产同步。

## 7. Git、备份和发布

- `main` 是唯一主流分支；
- 同一能力只有一个 canonical implementation；
- 兼容入口只委托 canonical service，并制定删除时间；
- 不维护长期业务分支或 v2/v3/backup 双主；
- 备份使用 tag、release、artifact、归档包、数据库快照；
- 正式切换必须有备份、审计、回滚和一致性报告；
- 每次 GitHub 写入必须通过 `fetch_file`、`fetch_commit` 或服务器 `git log` 二次确认。

## 8. 商用门禁

完整顺序：

1. current HEAD static baseline；
2. authorized minimal smoke；
3. complete accounting；
4. validation pass；
5. candidate/artifact freeze；
6. Data Lab MySQL 或 importer dry-run；
7. explicit approval；
8. idempotent sync/import；
9. landed validation；
10. rollback rehearsal；
11. one-week stability；
12. explicit commercial enablement。

任何单一步骤成功都不等于整个系统已商用。
