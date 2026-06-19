# AIdeal CPS Data Lab

AIdeal CPS / 智省优选的授权数据采集、标准化、验证和生产导入前门禁仓库。本仓库与生产 `aideal-cps` 隔离。

## 当前状态

- 当前主线：HZ24 特殊频道增量采集。
- 已形成 221 SKU 增量队列。
- 最近已提交结果：72 linked、149 pending，尚未完成全量 accounting。
- 当前代码已完成主要分层和配置化，但仍需在杭州采集机用当前 GitHub HEAD 完成授权 smoke/E2E。
- 当前未达到生产商用导入条件。

## 权威文档

新对话按顺序读取：

1. [`docs/PROJECT_MEMORY.md`](docs/PROJECT_MEMORY.md)
2. [`docs/CURRENT_PROGRESS.md`](docs/CURRENT_PROGRESS.md)
3. [`docs/DL2_COMMERCIAL_ARCHITECTURE.md`](docs/DL2_COMMERCIAL_ARCHITECTURE.md)
4. [`docs/ENGINEERING_STANDARDS.md`](docs/ENGINEERING_STANDARDS.md)
5. [`docs/ENVIRONMENT_AND_OPERATIONS.md`](docs/ENVIRONMENT_AND_OPERATIONS.md)
6. [`docs/NEXT_DIALOG_HANDOFF.md`](docs/NEXT_DIALOG_HANDOFF.md)

## 仓库边界

用途：

- 通过人工授权的京东联盟网页会话采集候选商品和推广链接；
- 标准化为 JSONL；
- 生成 manifest、hash、state、collection report 和 validation report；
- 向生产 importer 交付 validated artifact。

硬规则：

- 浏览器自动化只在杭州采集机运行，不在杭州生产机运行。
- 不提交凭证、Cookie、session、二维码、HAR、HTML 或原始账户页面。
- 出现验证码、滑块、风险页或登录失效立即停止，不绕过验证。
- Data Lab 不直接修改生产数据库。
- `main` 是唯一主流分支；同一能力只有一个 canonical implementation。
- host、port、URL、路径、timeout、频道和 schema 必须配置化。

## HZ24 主要入口

- `run/hz24_collect_increment_links.py`
- `scripts/hz24_build_increment_queue.py`
- `scripts/hz24_validate_increment_outcomes.py`
- `scripts/hz24_run_one_increment_batch.sh`

兼容入口必须委托同一 canonical service。

## 生产交付顺序

validated files → manifest/hash check → importer dry-run → explicit approval → idempotent import → landed validation/rollback evidence。

采集成功不等于允许商用导入；必须以 validation report 和 importer gate 为准。
