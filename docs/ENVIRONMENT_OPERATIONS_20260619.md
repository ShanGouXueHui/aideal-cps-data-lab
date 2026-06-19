# DL2 环境与操作模型 — 2026-06-19

> 状态：当前权威环境说明。运行态、数据库状态和开关状态必须以服务器和最新报告核验。

## 1. 杭州采集机

- IP：`121.41.111.36`
- 用户：`cpsdata`
- 项目：`/home/cpsdata/projects/aideal-cps-data-lab`
- GitHub：`ShanGouXueHui/aideal-cps-data-lab`
- 分支：`main`
- Chrome CDP：`127.0.0.1:19228`
- systemd：`aideal-hz23-observer.service`
- noVNC：`http://121.41.111.36:18772/vnc.html?autoconnect=true&resize=scale`
- x11vnc：`59072`
- 角色：京东联盟人工登录、授权采集、标准化、验证、候选发布、Data Lab MySQL（如已初始化）。

禁止提交或复制：联盟密码、Cookie、session、二维码、HAR、HTML、原始账户页面、敏感日志。

## 2. 杭州生产机

- IP：`8.136.28.6`
- 用户：`deploy`
- 项目：`/home/deploy/projects/aideal-cps`
- GitHub：`ShanGouXueHui/aideal-cps`
- 分支：`main`
- 本地 MySQL：`aideal_cps`
- 角色：生产服务、Data Lab artifact/view 校验、dry-run、同步/import、landed validation、rollback。

禁止：运行联盟浏览器自动化、登录联盟账号、复用采集机 Cookie/session、让生产请求实时读取 Data Lab。

## 3. 新加坡开发机

- IP：`43.106.55.255`
- 用户：`cpsdev`
- 角色：`aideal-cps` 开发和非生产测试。
- 不作为当前 DL2 采集双主，不维护独立商业数据事实源。

## 4. Data Lab MySQL 目标

- 数据库：`aideal_cps_data_lab`
- 表：`commission_products`、`commission_refresh_runs`、`commission_product_history`、`commission_publish_versions`
- 视图：`v_published_commission_products`
- 监听：`127.0.0.1:3306`
- 公网 3306：禁止开放

默认开关：

- `DATA_LAB_DB_WRITE_ENABLED=false`
- `DATA_LAB_DB_DUAL_WRITE_ENABLED=false`
- `DATA_LAB_PUBLISH_ENABLED=false`
- `DATA_LAB_SYNC_ENABLED=false`

上述是设计默认值。实际数据库、账号、migration、开关和数据行数必须在进入 Phase E 前现场核验。

## 5. AIdeal CPS 同步

短生命周期 Tunnel 约定：

- 本地：生产机 `127.0.0.1:13306`
- SSH：`cpsdata@121.41.111.36`
- 远端：Data Lab `127.0.0.1:3306`
- Key：服务器 Secret 文件，不进入 GitHub
- DB user/password：服务器 Secret，不进入 GitHub

同步任务结束立即关闭 Tunnel。用户请求始终读取 AIdeal CPS 本地 MySQL。

也允许 validated artifact/importer 路线。Tunnel sync 和 artifact import 均必须遵守同一 manifest/hash、dry-run、幂等、landed validation 和 rollback 门禁。

## 6. GitHub-first 操作模式

- 设计、代码、配置、测试、文档由 ChatGPT 直接在 GitHub 修改；
- 每次写入后使用 `fetch_file`、`fetch_commit` 或服务器 `git log` 二次确认；
- 详细运行结果提交到 `reports/`，必要调试归档到 `docs/debug/`；
- 用户不复制大段日志和文件内容，只返回最终 SUMMARY；
- 无法从 GitHub 判断的实时状态必须标记“待现场验证”。

## 7. 用户执行命令规则

仅当任务必须访问人工浏览器会话、systemd、服务器进程、Secret 或本地数据库时，才让用户执行命令。

命令要求：

- 可直接 copy-paste；
- 不使用 `set -e`；
- 分小步；
- 不切换或退出当前用户；
- 日志写入 `logs/`、`reports/` 或 `run/`；
- 屏幕只显示关键 Summary 或 tail 80–180 行；
- 一次只处理一个问题。

## 8. 浏览器和风控

- 联盟账号只允许人工登录；
- 自动化使用已授权会话；
- 出现验证码、滑块、风险页、登录失效或页面身份不确定立即停止；
- 不绕过验证；
- 生成机器可读 STOP_REQUIRED；
- supervisor 不得对风险状态无限自动重启；
- 自动化测试不得调用 JD live。

## 9. 运维状态等级

- **GitHub 已验证**：代码、配置、报告、manifest、CI 可证明；
- **现场已验证**：服务器 Summary/日志已提交 GitHub；
- **代码已实现但未现场验证**：不得宣称运行成功；
- **设计目标**：不得宣称已部署；
- **风险/假设**：必须附验证步骤。
