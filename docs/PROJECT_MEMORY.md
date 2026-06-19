# AIdeal CPS / 智省优选 — DL2 项目记忆

> 最后更新：2026-06-19  
> 权威范围：`ShanGouXueHui/aideal-cps-data-lab` 的项目定位、环境边界、协作方式与安全约束。  
> 新对话必须先读本文，再读 `CURRENT_PROGRESS.md` 和 `NEXT_DIALOG_HANDOFF.md`。

## 1. 项目定位

- 产品：AIdeal CPS / 智省优选。
- 业务形态：微信公众号/服务号入口的 AI 导购 + 京东联盟 CPS 返佣系统；不是自营电商平台。
- Data Lab 角色：在京东联盟 API 配额或覆盖不足时，通过**已授权、人工登录的京东联盟网页会话**采集候选商品与推广链接，形成可验证、可审计、可重复导入的数据产品。
- DL2 输出用途：
  1. 商品候选池补充；
  2. 推广短链及相关商业字段补充；
  3. 生成 JSONL、manifest、validation report；
  4. 经 dry-run 和质量门禁后，由受控 importer 提供给生产系统。
- Data Lab 不承担：面向用户的对话、推荐排序、会员、支付、返佣结算或生产数据库在线服务。

## 2. GitHub 仓库边界

| 仓库 | 角色 | 主分支原则 |
|---|---|---|
| `ShanGouXueHui/aideal-cps-data-lab` | 京东联盟授权采集、标准化、验证、导出与导入前门禁 | `main` 为唯一主流分支 |
| `ShanGouXueHui/aideal-cps` | AIdeal CPS 后端与生产业务系统 | 以该仓库自身交接文档为准 |
| `ShanGouXueHui/aideal-site` | 品牌官网、备案站点 | 以该仓库自身交接文档为准 |

本仓库不得反向承载生产业务逻辑。跨仓库交付必须通过版本化数据合同或受控 importer，不得依赖复制脚本、共享工作目录或直接连生产库。

## 3. 环境事实

### 3.1 杭州采集机：DL2 主执行环境

- 公网 IP：`121.41.111.36`
- Linux 用户：`cpsdata`
- 项目路径：`/home/cpsdata/projects/aideal-cps-data-lab`
- 规格：2C / 4G / 50G
- Chrome CDP：`127.0.0.1:19228`
- noVNC：`18772`
- x11vnc：`59072`
- 允许：人工登录京东联盟、授权页面采集、生成 Data Lab 报告和导出。
- 禁止：把账号密码、Cookie、session、二维码截图、原始账户页面、HAR、HTML 或敏感日志提交 GitHub。

### 3.2 杭州生产机：生产运行环境

- 公网 IP：`8.136.28.6`
- Linux 用户：`deploy`
- 后端项目路径：`/home/deploy/projects/aideal-cps`
- 允许：运行生产服务、执行经过审批的 dry-run/importer、读取已验证数据制品。
- 禁止：运行浏览器自动化、登录京东联盟、复用采集机 Cookie/session、直接运行 Data Lab 页面采集器。

### 3.3 新加坡机器

- 公网 IP：`43.106.55.255`
- Linux 用户：`cpsdev`
- 对 `aideal-cps` 可作为开发环境使用。
- 对 DL2 网页采集：旧采集方案已暂停，不再作为当前主执行环境；不得与杭州采集机形成双主或两套并行数据源。

## 4. 数据库与模型边界

### 4.1 数据库

- 生产业务数据库为 MySQL；具体地址、账号和密码不得写入本文、代码、日志或 GitHub。
- Data Lab 默认只生成文件制品和验证结果，不直接写生产 MySQL。
- 生产导入顺序固定为：候选文件校验 → manifest/hash 校验 → dry-run → landed validation → 显式批准 → 幂等批量写入 → 导入后核验。
- 任何“采集成功”都不等于“允许商用导入”。只有验证报告和导入门禁共同通过，才可进入生产候选流程。

### 4.2 AI 模型

- Data Lab 核心链路应保持确定性：页面识别、字段解析、数据合同、哈希、去重、验证和导入门禁不依赖大模型判断。
- 面向用户的 AI 推荐与模型 Provider 属于 `aideal-cps`，不在本仓库维护 Provider 密钥或路由策略。
- ZenMux 已排除，不应在后续 Provider 推荐中默认恢复。

## 5. 人机交互与协作习惯

- 使用中文，职业化、直接、结构化。
- 默认由 ChatGPT **直接读取和修改 GitHub**；不要让用户复制超长文件修改命令。
- 不使用 Codex CLI。
- 需要用户在服务器执行时，命令必须：
  - 可直接 copy-paste；
  - 分小步；
  - 不使用 `set -e`；
  - 每一步包含路径确认、`git status`、最小改动、静态检查、smoke/E2E、日志路径；
  - 日志写入 `logs/` 或 `run/`，屏幕只显示关键 80–180 行。
- 排障时一次只推进一个问题，不把登录、采集、转链、导入、生产发布混在同一补丁中。
- GitHub 是长期上下文与事实源；运行日志、报告和状态优先从 GitHub 已提交制品查询。无法由 GitHub确认的运行态必须明确标为“待现场验证”。

## 6. 安全与风控硬规则

- 京东联盟账号只允许人工登录；账号密码不得进入脚本、配置、日志、聊天或 GitHub。
- 出现验证码、滑块、风险页、登录失效或页面身份不确定时：
  1. 立即停止自动化；
  2. 不尝试绕过验证；
  3. 生成 STOP 状态/报告；
  4. 等待人工恢复合法会话后再继续。
- 不承诺通过话术修复价格、佣金或链接准确性；必须通过字段来源、校验、哈希、时间戳、幂等和 landed validation 提高准确性。
- 不直接修改生产数据库；任何生产导入必须另行 dry-run 和显式批准。

## 7. 当前主线命名

- 当前特殊频道增量项目代号：HZ24。
- 特殊频道：`超补爆品`、`限量高佣`、`秒杀专区`、`定向高佣`、`粉丝爱买`。
- 当前增量队列：`data/export/hz24_special_tab_increment_latest.jsonl`。
- 当前链接结果：`data/import/hz24_special_tab_links_latest.jsonl`。
- 当前不可推广结果：`data/import/hz24_special_tab_unavailable_latest.jsonl`。
- 当前采集报告：`reports/hz24_increment_collection_latest.json`。
- 当前验证报告目标：`reports/hz24_increment_validation_latest.json`。

## 8. 事实等级

后续文档和答复必须区分：

- **已验证事实**：来自 GitHub 代码、版本化报告、manifest 或现场日志。
- **代码已实现但未现场验证**：静态代码存在，尚未在杭州采集机用当前会话完成 smoke/E2E。
- **设计决策**：已确定应实现，但代码或运行验证尚未完成。
- **风险/假设**：必须给出验证方式，不得包装成已完成。
