# Data Lab 执行拓扑

更新日期：2026-06-20

## 环境

```text
杭州 Data Lab：121.41.111.36 / cpsdata
新加坡 CI Bridge：43.106.55.255 / datalab
杭州 AIdeal CPS：8.136.28.6 / deploy
```

杭州是唯一允许真实 JD、HZ23/HZ24、生产状态和未来 Data Lab MySQL 的环境。新加坡只运行离线编译、测试和审计。AIdeal CPS 只消费已发布版本。

## SSH 方向

```text
杭州 cpsdata
    ↓ ssh -o BatchMode=yes sg-aideal-datalab
新加坡 datalab
```

该链路已经验证成功：

```text
USER=datalab
HOST=iZt4n62qkjefjya5xa097pZ
HOME=/home/datalab
```

正确用户是 `datalab`，不是 `cpsdev`。`datalab` 不在 sudoers，后续脚本不得假设 sudo 可用。

SSH 只用于人员进入和命令执行，不复制 Cookie、Profile、生产 JSONL、数据库备份、Token、私钥或数据库密码。

## 正确交付链

```text
ChatGPT 修改 GitHub
→ 新加坡 datalab 拉取 current main
→ 编译、Offline Quality、Engineering Audit
→ quality-reports 保存工程质量报告
→ 杭州 cpsdata 拉取已验证代码
→ 杭州执行只读或生产动作
→ runtime-evidence 保存脱敏运行证据
→ 数据门禁完成后进入 MySQL 和 AIdeal CPS 同步
```

## 报告边界

- `main` 只保存代码、配置、合同、测试、文档和 pointer；
- `quality-reports` 保存工程质量报告；
- `runtime-evidence` 保存 HZ23/HZ24/MySQL readiness 证据；
- CI Bridge 只验证，不直接推进 main；
- 任何报告必须绑定代码 HEAD；
- 当前 `runtime-evidence` 迁移尚未完成。

## 当前阻断

新加坡可能仍有旧 checkout、cron、systemd user timer 或残留命令，继续提交工程审计 baseline。必须先停止该任务，再对 current main 运行统一门禁。
