# DL2 MySQL 稳定期与 AIdeal CPS 切换

更新日期：2026-06-16

## 固定架构

Data Lab MySQL `aideal_cps_data_lab` 是权威源库。AIdeal CPS 不在用户请求链路实时访问远程 Data Lab；同步任务通过短生命周期 SSH Tunnel 读取发布视图，并写入 AIdeal CPS 本地 MySQL。用户请求只读本地库。

## 数据库迁移前门禁

必须同时满足：两个成功探针、观察不少于 48 小时、完整 1-67 页成功、扫描不少于 3900、候选 SKU 无重复、HZ20 unsafe 为 0、推广链接可信、候选 checksum/schema/hash 通过，以及 `observation_ready=true`、`mysql_initialization_allowed=true`。

## 初始化顺序

1. 备份候选 JSONL、manifest、catalog、state 和 DDL checksum。
2. 初始化 `aideal_cps_data_lab` 和四张正式表。
3. 创建 `v_published_commission_products`。
4. 使用 staging V2 单事务回填候选商品。
5. 校验行数、唯一 SKU、价格、佣金、推广链接和 payload hash。
6. 重复回填必须得到 inserted=0、updated=0。
7. 保持所有商品未发布，并完成回滚演练。

## 连续七天稳定期

稳定期从首次回填完成并开启 JSONL/MySQL dual-write 开始计算。期间：

- Data Lab 写入与 dual-write 开启；
- publish 关闭；
- AIdeal CPS 正式 sync 关闭；
- 每次刷新后 JSONL/MySQL 唯一 SKU 数、payload hash、推广链接和状态必须一致；
- duplicate SKU、unsafe HZ20、untrusted URL、部分事务写入均必须为 0；
- 任意未解释差异会使七天稳定期重新计时。

稳定期内同时完成 AIdeal CPS Tunnel、Alembic、本地 staging、幂等同步和回滚 dry-run。

## 第八天切换

七天全部通过后生成正式 publish version，将合格商品设为 published，核对视图行数与版本行数一致，开启 AIdeal CPS 同步。AIdeal CPS 将发布视图同步至本地 `aideal_cps.products`，先灰度、再全量。失败时保留并读取本地上一发布版本。
