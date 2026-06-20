# 环境、周边系统与协作规则

更新日期：2026-06-20

## 1. 环境角色

### 杭州 Data Lab 生产

```text
地址：121.41.111.36
用户：cpsdata
目录：/home/cpsdata/projects/aideal-cps-data-lab
角色：唯一 Data Lab 生产环境
```

允许真实 JD 登录、浏览器 Profile、HZ23/HZ24、生产状态、未来 Data Lab MySQL、dual-write 和正式发布。

### 新加坡 CI Bridge

```text
地址：43.106.55.255
用户：datalab
目录：/home/datalab/projects/aideal-cps-data-lab
SSH 别名：sg-aideal-datalab
角色：离线验证节点
```

只允许 Git 拉取、编译、Offline Quality、Engineering Audit、无 JD live 测试和脱敏报告处理。

`datalab` 与 `cpsdev` 必须隔离。正确 Data Lab 用户是 `datalab`；`cpsdev` 属于其他项目。`datalab` 不在 sudoers，运维命令不得假设 sudo 可用。

### 杭州 AIdeal CPS 生产

```text
地址：8.136.28.6
用户：deploy
目录：/home/deploy/projects/aideal-cps
数据库：aideal_cps
```

该环境只消费已发布版本，不承担京东采集。

## 2. SSH 事实

新加坡 sshd 一直正常运行。此前登录失败不是 SSH 服务未启动，而是 `datalab` 的 `authorized_keys` 缺少杭州 bridge 公钥。

已完成：

- 杭州专用 bridge 密钥存在；
- 新加坡公钥安装到 `/home/datalab/.ssh/authorized_keys`；
- 权限由 `datalab` 自己维护，不使用 sudo；
- `BatchMode=yes` 无密码登录成功。

固定入口：

```text
ssh -o BatchMode=yes sg-aideal-datalab
```

验证结果：

```text
USER=datalab
HOST=iZt4n62qkjefjya5xa097pZ
HOME=/home/datalab
```

SSH 只用于人员进入和命令执行，不复制 Cookie、Profile、生产 JSONL、数据库备份、Token、私钥或数据库密码。

## 3. 系统边界

Data Lab 负责授权浏览器采集、SKU/价格/佣金/推广资格、短链、终态、质量门禁、源数据、发布版本和未来 Data Lab MySQL。

AIdeal CPS 负责微信/H5、搜索推荐、点击归因、订单返佣、AI 推荐字段和本地业务数据库。

用户请求不得实时依赖 Data Lab 浏览器、SSH Tunnel 或远程数据库。

## 4. MySQL 与模型

- Data Lab MySQL 只监听本机，不开放公网；
- AIdeal CPS 后续使用短生命周期 SSH Tunnel 和只读数据库用户；
- 用户请求始终读取 AIdeal CPS 本地 MySQL；
- Data Lab 的价格、佣金、链接、状态和质量判断不依赖大模型；
- AI 不决定价格、佣金和链接真实性；
- Data Lab 同步不能覆盖 AI 字段。

## 5. 交互习惯

1. 中文、职业化、直接、结构化。
2. 优先直接读取和修改 GitHub。
3. 长代码、复杂脚本和文档直接提交 GitHub。
4. 用户只执行仓库内审核过的单一 `.sh` 入口。
5. GitHub 写入后必须二次确认。
6. 日志写入 `logs/`、`reports/` 或 `docs/debug/`，用户只返回 Summary。
7. 定位问题一问一答。
8. 不使用 Codex CLI。
9. 状态、设计、任务和下一步以 GitHub 文档为连续性载体。

## 6. 命令与脚本

- 不使用 `set -e`；
- 复杂操作封装为仓库脚本；
- 脚本从自身位置解析仓库根目录；
- 大日志写文件，屏幕只输出 Summary；
- 生产写入先 dry-run、备份、校验，再原子切换；
- 不让用户粘贴容易截断的长文件修改命令。

## 7. Git 与报告

- 正式代码只有一个 `main`；
- 历史快照和证据分支不得成为第二代码主线；
- 运行报告不得提交到 main；
- `quality-reports` 保存工程质量报告；
- `runtime-evidence` 保存脱敏运行证据；
- 每个报告必须记录代码 HEAD、生成时间、schema 和 checksum；
- push 后必须确认 remote HEAD 和文件内容。

## 8. 当前环境遗留

新加坡可能仍存在旧 checkout、cron、systemd user timer 或残留命令，继续提交工程审计 baseline。下一步必须先只读定位并停止该任务，再运行 current main 的 CI Bridge。
