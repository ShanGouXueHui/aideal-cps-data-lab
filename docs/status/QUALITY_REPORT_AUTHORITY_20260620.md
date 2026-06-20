# Quality Report Authority

更新日期：2026-06-20

## 权威规则

- `main` 只保存代码、配置、文档和质量报告指针。
- Full Engineering Audit 与 Offline Quality 的运行报告只保存到 `quality-reports` 分支。
- Active Engineering Audit 仅作为 workflow artifact，不得提交到 `main`。
- 新加坡 CI Bridge 只执行编译、离线测试和报告校验，不再发布质量报告。
- 任何权威报告都必须满足 `git_head == 当前 main HEAD`。

## 当前生产限制

在 HZ23 last-known-good 3304 候选完成只读核验前：

- 不恢复 HZ24；
- 不初始化或写入 MySQL；
- 不执行商品 publish；
- 不同步 AIdeal CPS；
- 不调用 JD live。
