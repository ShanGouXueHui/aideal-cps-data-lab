# 商用化状态快照 — 2026-06-19

## 1. 总结

```text
HZ23“全部商品”完整观察：通过
HZ23 1-67 页完整轮次：通过
成功探针：2
观察时长：68.88 小时
当前商用候选：3304
候选重复 SKU：0
候选 payload hash mismatch：0
候选完整性：通过
HZ20 历史污染：已隔离，当前 0
HZ24 专题 Tab 测重：通过
HZ24 真实增量队列：221
HZ24 已成功领链：72
HZ24 已抢光样本：5
HZ24 旧报告 pending：149
Data Lab MySQL：尚未初始化
AIdeal CPS 正式同步：尚未启用
全仓工程审计：255 文件，390 blocker
商用状态：尚未正式发布
```

## 2. HZ23 权威事实

权威报告：

```text
reports/hz23_round_latest.json
```

结果：

```text
round_id=20260615_100135
commercial_segment_complete=true
completed_pages=1..67
unfinished_pages=[]
stop_page=null
stop_reason=null
scanned_total=4020
last_known_sku_count=3357
```

其中：

- `4020` 是扫描卡片位总数，不是唯一 SKU；
- 完整轮次可见唯一 SKU 为 3665；
- catalog index 为 3698；
- 可信推广链接 SKU 为 3357。

## 3. 3304 条商用候选

权威 manifest：

```text
data/export/aideal_cps_products_commercial_candidate_manifest.json
```

结果：

```text
row_count=3304
eligible_sku_count=3304
duplicate_sku_count=0
candidate_integrity_ready=true
successful_probes=2
observation_ready=true
gate_failures=[]
commercial_enabled=false
```

拒绝项：

```text
missing_title=53
missing_image_url=1
unsafe_hz20=0
untrusted_promotion_url=0
```

3304 是当前冻结的 HZ23 商用候选基线，不包含 HZ24 尚未完成的专题增量。

## 4. HZ24 专题 Tab 扩展

已确认页面 Tab：

```text
超补爆品
限量高佣
秒杀专区
定向高佣
粉丝爱买
全部商品
```

5 个专题 Tab 均通过滚动稳定性单页确认，每个 50 个 SKU。

权威测重报告：

```text
reports/hz24_tab_overlap_analysis_latest.json
```

结果：

```text
membership_count=250
union_sku_count=239
cross_tab_duplicate_membership_count=11
overlap_with_3304_candidate=18
increment_queue=221
```

去重已经覆盖：

1. 专题 Tab 之间按 SKU 去重；
2. 与 3304 条候选去重；
3. 与已有可信推广链接去重；
4. 断点续跑时与已成功 HZ24 结果再次去重。

## 5. HZ24 增量采集现状

权威报告：

```text
reports/hz24_increment_collection_latest.json
```

当前结果：

```text
queue_count=221
success_count=72
pending_count=149
batch_success=2
batch_fail=5
stop_reason=item_fail_fuse
risk=[]
```

5 个失败样本均明确显示：

```text
已抢光
card-disabled
```

因此本次停止不是风控、验证或重复抓取，而是状态模型缺失：旧采集器没有把 sold-out 商品识别为不可推广终态。

正确处理：

```text
linked=72
unavailable_sold_out=5
可行动 pending 预计约 144
```

在 HZ24 v2 完成并验证前，不恢复增量采集，不把 HZ24 数据合并进 3304 条基线。

## 6. 工程审计状态

权威报告：

```text
reports/project_engineering_audit_latest.json
```

结果：

```text
files_scanned=255
blocker_count=390
```

主要类别：

- 重复定义和跨文件重复实现；
- 硬编码 URL、IP、端口、路径、Tab、selector 和参数；
- Python/Shell 大文件；
- 长函数；
- 历史 HZ11-HZ22 多版本脚本并存。

大量 blocker 来自历史实验代码，但当前必须先完成活跃主线与历史归档分类，再修复活跃路径。不能简单删除未经确认的历史证据，也不能继续向大文件叠加新业务逻辑。

## 7. MySQL 状态

已经准备：

- schema/DDL；
- Repository 抽象；
- staging V2；
- JSONL -> MySQL 幂等回填；
- 候选校验；
- post-migration 结构检查；
- 逐行 canonical hash 校验；
- AIdeal CPS 同步预检设计。

尚未执行：

```text
Data Lab MySQL 初始化
3304+ 候选回填
dual-write
publish version
AIdeal CPS dry-run sync
灰度和正式商用
```

所有商用开关继续为 false。

## 8. 风险

1. 工程审计 blocker 未清零；
2. HZ24 旧采集器不能正确分类 sold-out；
3. HZ24 72 条成功数据必须保留并防重复；
4. 历史脚本存在重复实现和硬编码；
5. Data Lab MySQL 尚未实际部署；
6. AIdeal CPS 仍未消费 Data Lab 发布版本；
7. 京东页面 DOM、Tab 商品池和推广资格会动态变化；
8. 任何真实验证必须继续安全停止，不允许绕过。

## 9. 下一步计划

按顺序执行：

1. 冻结 HZ24 增量采集，保留 72 条成功；
2. 将工程审计结果分为活跃主线和历史归档；
3. 修复活跃 HZ23/HZ24/MySQL 路径重复定义、硬编码、大文件和长函数；
4. 完成 HZ24 v2 `linked/unavailable/pending` 状态模型；
5. 将 5 个 sold-out 样本迁移为 unavailable，验证不再触发失败熔断；
6. 恢复单账号串行采集约 144 条可行动 pending；
7. 完成 221 条队列全终态校验；
8. 生成 HZ24 独立候选版本并与 HZ23 基线原子合并；
9. 初始化 Data Lab MySQL，执行幂等回填和一致性验证；
10. 开启 dual-write，连续稳定运行 7 天；
11. 第 8 天生成 publish version；
12. AIdeal CPS dry-run、灰度和正式商用。

## 10. 商用判定

当前判定：

```text
HZ23 observation_ready=true
HZ23 candidate_integrity_ready=true
HZ24 increment_complete=false
engineering_blockers_cleared=false
mysql_initialized=false
dual_write_stable_7d=false
published=false
commercial_enabled=false
```

因此当前不能宣布正式商用。