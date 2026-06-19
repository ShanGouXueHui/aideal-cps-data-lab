# AIdeal CPS Data Lab

AIdeal CPS / 智省优选的授权数据采集、标准化、验证和生产导入前门禁仓库。本仓库与生产 `aideal-cps` 隔离。

## 当前状态

- 当前主线：HZ24 特殊频道增量采集与商用收口。
- HZ23 已形成 3304 SKU 可信商业候选基线；该数字不等于页面约 4000 条商品全部已生成推广链接，也不等于已经写入生产 MySQL。
- HZ24 已形成 221 SKU 增量队列；最近已提交结果为 72 linked、149 pending、`complete=false`。
- 当前代码已完成主要分层、配置化、终态分类、文件制品和验证骨架。
- 归档核验时的 `main` HEAD 为 `3fadceaa21e46c560df60659b2183b0ccca0d046`；GitHub connector 未返回该提交的 status context 或 PR-triggered workflow run，因此只能判定 **CI 未证明**，不能判定通过或失败。
- 当前代码尚未在杭州采集机完成新版本授权 smoke/E2E，也没有可证明通过的 HZ24 validation report。
- 当前商业状态：`NOT_READY`。

## 权威文档

新对话按顺序读取：

1. [`docs/COMMERCIALIZATION_HANDOFF_20260619.md`](docs/COMMERCIALIZATION_HANDOFF_20260619.md)
2. [`docs/PROJECT_MEMORY.md`](docs/PROJECT_MEMORY.md)
3. [`docs/CONVERSATION_ARCHIVE_2026-06-19.md`](docs/CONVERSATION_ARCHIVE_2026-06-19.md)
4. [`docs/CURRENT_PROGRESS.md`](docs/CURRENT_PROGRESS.md)
5. [`docs/DL2_COMMERCIAL_ARCHITECTURE.md`](docs/DL2_COMMERCIAL_ARCHITECTURE.md)
6. [`docs/ENGINEERING_STANDARDS.md`](docs/ENGINEERING_STANDARDS.md)
7. [`docs/ENVIRONMENT_AND_OPERATIONS.md`](docs/ENVIRONMENT_AND_OPERATIONS.md)
8. [`docs/NEXT_DIALOG_HANDOFF.md`](docs/NEXT_DIALOG_HANDOFF.md)

发生冲突时，按以下优先级裁决：当前 GitHub 代码/配置/manifest/report/CI 与脱敏现场日志 > `COMMERCIALIZATION_HANDOFF_20260619.md` > 其余设计和历史文档。任何无法由证据确认的运行态必须标记为“待现场验证”。

## 仓库边界

用途：

- 通过人工授权的京东联盟网页会话采集候选商品和推广链接；
- 标准化为 JSONL 或受控 Data Lab 数据产品；
- 生成 manifest、hash、state、collection report 和 validation report；
- 向生产 importer 交付 validated artifact，或通过受控 published view/短生命周期 Tunnel 同步；
- 所有生产交付均须经过 dry-run、显式批准、幂等写入、landed validation 和回滚门禁。

硬规则：

- 浏览器自动化只在杭州采集机运行，不在杭州生产机运行。
- 不提交凭证、Cookie、session、二维码、HAR、HTML 或原始账户页面。
- 出现验证码、滑块、风险页或登录失效立即停止，不绕过验证。
- Data Lab 不绕过 importer/同步门禁直接修改生产数据库。
- `main` 是唯一主流分支；同一能力只有一个 canonical implementation。
- host、port、scheme、URL、路径、timeout、频道和 schema 必须配置化。
- 备份使用 tag、release、artifact 或快照，不维护长期平行版本主线。

## HZ24 主要入口

- `run/hz24_collect_increment_links.py`
- `scripts/hz24_build_increment_queue.py`
- `scripts/hz24_validate_increment_outcomes.py`
- `scripts/hz24_run_one_increment_batch.sh`

兼容入口必须委托同一 canonical service。

## 生产交付顺序

validated files/published view → manifest/hash check → importer/sync dry-run → explicit approval → idempotent import → landed validation → rollback evidence。

采集成功不等于允许商用导入；必须以 validation report 和 importer/sync gate 为准。
