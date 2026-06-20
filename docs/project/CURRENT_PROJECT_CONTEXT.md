# AIdeal CPS Data Lab 当前项目上下文

更新日期：2026-06-20

## 1. 项目边界

Data Lab 负责京东联盟授权浏览器采集、商品与推广资格解析、可信短链、终态维护、质量门禁、版本化发布和未来 Data Lab MySQL。

AIdeal CPS 负责微信/H5、搜索推荐、点击归因、订单和返佣。终端请求只访问 AIdeal CPS 本地 MySQL，不实时依赖 Data Lab 浏览器、远程 MySQL 或 SSH Tunnel。

## 2. 环境角色

```text
杭州 Data Lab：121.41.111.36 / cpsdata
目录：/home/cpsdata/projects/aideal-cps-data-lab

新加坡 CI Bridge：43.106.55.255 / datalab
目录：/home/datalab/projects/aideal-cps-data-lab
SSH 别名：sg-aideal-datalab

杭州 AIdeal CPS：8.136.28.6 / deploy
目录：/home/deploy/projects/aideal-cps
```

杭州是唯一允许真实 JD、HZ23/HZ24 和 Data Lab MySQL 的环境。新加坡只运行离线编译、测试和审计。AIdeal CPS 只消费已发布版本。

杭州到新加坡无密码 SSH 已验证。正确用户是 `datalab`，不是 `cpsdev`；`datalab` 不在 sudoers。

## 3. 工程治理

已验证代码树：258 个文件，global/full 和全部 scope blocker 为 0，重复定义/赋值/常量/配置键/默认值/实现为 0，大文件和长函数为 0，语法 PASS。

Offline Quality：69 项，0 failure，0 error，`jd_live_called=false`。

```text
CODE_GOVERNANCE_LOGIC_COMPLETE=true
CODE_GOVERNANCE_FORMAL_ACCEPTANCE=false
```

正式验收未完成的唯一工程原因：运行报告仍可能由新加坡旧任务提交到 main，导致权威报告与当前 HEAD 不一致。

## 4. 报告分支

```text
main              唯一代码主线
quality-reports   工程审计与 Offline Quality
runtime-evidence  HZ23/HZ24/MySQL readiness 脱敏证据
```

`runtime-evidence` 尚未完成代码迁移。任何运行报告不得继续写入 main。

## 5. HZ23

```text
last-known-good round=20260615_100135
candidate_rows=3304
data_sha256=509d5b09bc9843d2e083ecd29fa2cfc83569c4cf877ced7a13d37a1e820d457a
current latest rows=0
candidate_integrity_ready=false
observation_ready=false
```

只读审计代码已经进入 main，但尚未在杭州执行。执行前必须先修复其报告发布目标。

## 6. HZ24

```text
queue=221
old_linked=72
sold_out=5
old_pending=149
expected_actionable_pending=144
```

无杭州生产证据证明迁移落地，继续暂停。

## 7. MySQL 和同步

Data Lab MySQL 初始化、两次幂等回填、dual-write 7 天、publish version 和 AIdeal CPS dry-run/灰度/正式同步均未执行。所有开关保持 false。

## 8. 当前严格下一步

1. 新加坡定位并停止旧工程审计发布任务；
2. 将所有运行证据迁移到 `runtime-evidence`；
3. 对 current main 重跑 Full Audit 和 Offline Quality；
4. 确认报告绑定 current main 且 main 不再被报告推进；
5. 杭州执行 HZ23 3304 只读盘点；
6. 再设计原子恢复、HZ24、MySQL 和商用链。
