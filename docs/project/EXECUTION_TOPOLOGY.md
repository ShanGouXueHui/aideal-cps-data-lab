# Data Lab 执行拓扑

更新日期：2026-06-20

## 1. 杭州 Data Lab 生产环境

```text
服务器名称：Ubuntu-datacollection
公网 IP：121.41.111.36
区域：华东1（杭州）
规格：2 核 / 4 GiB / 50 GiB
Linux 用户：cpsdata
项目目录：/home/cpsdata/projects/aideal-cps-data-lab
角色：Data Lab 唯一生产执行环境
```

允许执行：

- 京东联盟人工登录和真实浏览器会话；
- HZ23/HZ24 真实采集与断点恢复；
- linked、unavailable、pending 生产状态维护；
- Data Lab MySQL 初始化、回填和 dual-write；
- 生产 systemd、Chrome、CDP、X11、noVNC；
- 经门禁批准后的商用数据发布。

生产 Secret、Cookie、浏览器 Profile、Token、私钥和数据库密码只保存在该服务器的 Secret 区域，不进入 GitHub，也不复制到新加坡。

## 2. 新加坡 CI Bridge

```text
服务器名称：Ubuntu-Oris-OpenClaw
公网 IP：43.106.55.255
区域：新加坡
规格：2 核 / 2 GiB / 40 GiB
隔离 Linux 用户：datalab
项目目录：/home/datalab/projects/aideal-cps-data-lab
角色：GitHub Actions 的离线验证替代节点
```

只允许执行：

- 从 GitHub 拉取代码；
- Python 编译和静态检查；
- Offline Quality；
- Engineering Audit；
- 无 JD live 的单元测试；
- 将脱敏测试报告和审计报告回写 GitHub。

明确禁止：

- 真实 JD 登录、浏览器 Profile、Cookie 或账号资料；
- HZ23/HZ24 真实采集；
- 生产 linked/unavailable/pending 数据写入；
- Data Lab MySQL 初始化或生产写入；
- AIdeal CPS 商用同步；
- 作为 Data Lab 生产故障切换节点。

新加坡 `cpsdev` 继续服务其他开发项目；Data Lab 验证统一使用隔离用户 `datalab`，两者不共享工作目录、虚拟环境、SSH 私钥和运行数据。

## 3. 运维登录与 SSH 方向

允许杭州 Data Lab 生产服务器作为统一运维登录入口：

```text
121.41.111.36 / cpsdata
        ↓ SSH
43.106.55.255 / datalab
```

固定规则：

- 运维人员只需先登录杭州 `cpsdata`，再 SSH 进入新加坡 `datalab`；
- 编译、离线测试和工程审计命令在 SSH 后的新加坡 Shell 中执行；
- 杭州服务器不得代替新加坡执行 CI Bridge 任务；
- SSH 仅用于人员操作和命令进入，不作为生产数据同步通道；
- 不通过该 SSH 链路复制 Cookie、浏览器 Profile、生产 JSONL、数据库备份、Token、私钥或数据库密码；
- 新加坡不得反向控制杭州生产服务；
- 代码输入和报告输出仍以 GitHub commit 与脱敏报告为准。

该 SSH 便利通道不会改变两台服务器的角色：杭州仍是 Data Lab 生产，新加坡仍只是离线验证桥。

## 4. 杭州 AIdeal CPS 生产环境

```text
公网 IP：8.136.28.6
Linux 用户：deploy
项目目录：/home/deploy/projects/aideal-cps
角色：AIdeal CPS 商用应用生产环境
```

该环境与 `121.41.111.36` 的 Data Lab 生产环境是两台不同服务器，不承担京东联盟浏览器采集。

## 5. 正确交付链

```text
ChatGPT 修改 GitHub
        ↓
运维人员登录杭州 cpsdata，并 SSH 进入新加坡 datalab
        ↓
新加坡 datalab 拉取代码并执行离线验证
        ↓
验证报告回写 GitHub
        ↓
报告满足全部工程和离线门禁
        ↓
杭州 cpsdata 拉取已验证 commit
        ↓
杭州 Data Lab 生产执行
        ↓
达到 MySQL 和 dual-write 门禁后，AIdeal CPS 再同步商用数据
```

杭州到新加坡的 SSH 只减少人工切换服务器，不替代 GitHub 的代码和报告交接，也不形成生产数据链路。

## 6. 门禁

在以下条件全部满足前，杭州 `cpsdata` 不得恢复 HZ24、初始化 MySQL 或开启商用同步：

```text
compile=PASS
offline_quality=PASS
jd_live_called=false
global_blocker_count=0
duplicate_definition=0
duplicate_implementation=0
large_file=0
long_function=0
```

新加坡验证通过不等于生产自动执行；真实生产动作仍需在杭州 `cpsdata` 环境按生产门禁显式执行。
