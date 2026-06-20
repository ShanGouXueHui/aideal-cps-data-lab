# 代码变更强制门禁

更新日期：2026-06-20

详细实施见 `CODE_CHANGE_GUARDRAILS_IMPLEMENTATION.md`。

## 硬规则

- 修改前扫描重复函数、类、方法、Shell 函数、变量、常量、配置键、默认值多源和跨文件重复实现；
- 配置与环境分离，默认值只有一个 typed settings/config 来源；
- browser、application、domain、persistence、contracts、configuration、ops、tests 分层解耦；
- selector 只在浏览器适配层或集中配置；
- 数据库层不得依赖浏览器对象；
- 正式能力必须是通用商用实现，不为单 SKU 或临时 DOM 写死；
- Python/Shell 文件超过 300 行、函数超过 80 行、运行入口超过 120 行必须拆分；
- 正式代码只有一个 main；历史和证据分支不能成为第二代码主线；
- 运行报告不得提交到 main；
- 自动测试禁止 JD live；
- 不提交密码、Token、Cookie、Profile、私钥和数据库密码。

## 全局验收

```text
global/full/active/compatibility/historical/support blocker=0
duplicate definition/assignment/constant/config/default/implementation=0
large file=0
long function=0
python/shell/config syntax=PASS
offline quality=PASS
jd_live_called=false
audit git_head=current main
offline git_head=current main
```

当前扫描器已经完整覆盖上述重复检测。旧版本中的“重复变量、常量、配置键和默认值多源尚未实现”结论已失效。

不得通过降低 severity、扩大排除目录、只看 active scope 或复用旧报告伪造通过。

## 交付规则

复杂操作先提交为仓库脚本；用户只执行单一 `.sh` 入口；不使用 `set -e`；日志写文件，终端只输出 Summary；生产写入必须有 dry-run、备份、校验、原子提交和回滚。

在正式报告绑定和数据门禁完成前，禁止恢复 HZ24、初始化 MySQL、开启 dual-write、publish 或 AIdeal CPS 正式同步。
