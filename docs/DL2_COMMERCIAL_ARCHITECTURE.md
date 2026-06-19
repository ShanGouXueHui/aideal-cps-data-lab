# DL2 通用商用架构

> 最后更新：2026-06-19  
> 目标：将授权网页采集从一次性脚本演进为可配置、可恢复、可验证、可审计、可安全导入的通用商业数据链路。

## 1. 系统边界

```text
人工登录京东联盟
        │
        ▼
杭州采集机浏览器/CDP
        │
        ▼
页面适配层 ── 风控检测/频道切换/卡片识别/精确 SKU 定位
        │
        ▼
采集应用层 ── 队列/批次/熔断/恢复/结果分类
        │
        ├── linked: 已生成可信推广链接
        ├── unavailable: 已抢光/下架/不可推广
        └── retryable failure: 页面或交互临时失败
        │
        ▼
JSONL + manifest + state + validation report
        │
        ▼
受控 importer: dry-run → landed validation → 显式批准
        │
        ▼
杭州生产 MySQL / AIdeal CPS
```

## 2. 分层职责

### 2.1 入口层

- `run/hz24_collect_increment_links.py`
- `run/hz24_collect_increment_links_v2.py`
- `scripts/hz24_validate_increment_links.py`
- `scripts/hz24_validate_increment_outcomes.py`

规则：入口只解析启动语义并调用应用服务；不得重复实现采集、解析、持久化和校验逻辑。兼容入口可以保留，但必须委托同一个 canonical service。

### 2.2 配置层

- `config/hz24-domain.toml`：频道和终态原因。
- `config/hz24-browser.toml`：CDP、host、scheme、timeout、risk markers。
- `config/hz24-collection.toml`：批次、等待、熔断、链接生命周期。
- `config/hz24-contracts.toml`：文件路径、schema、worker、service 名称。
- `config/hz24-audit.toml`：只读结构审计与候选池分析。
- `config/hz24-validation.toml`：验证字段、manifest schema 和遗留来源标识。

规则：业务代码不得重新硬编码同一 host、port、URL、路径、等待时间、频道、schema 或 systemd service 名称。

### 2.3 页面适配层

主要模块：

- `browser_contract.py`：DOM 文本、正则、JS selector contract。
- `jd_page.py`：连接 CDP、选择页面、频道点击、卡片采集、modal 解析、可信短链判断。
- HZ21 adapter：当前复用已验证的精确 SKU 点击能力；属于临时兼容依赖，不应继续扩散。

页面层只回答“页面上看到了什么、是否安全、点击和解析结果是什么”，不决定业务终态或写文件。

### 2.4 应用编排层

主要模块：

- `application.py`：装载设置、队列完整性检查、启动 session、形成最终报告。
- `session.py`：浏览器生命周期和频道级编排。
- `tab_runner.py`：单频道批处理。
- `outcome_service.py`：linked/unavailable/retryable failure 分类。
- `link_service.py`：一键领链、modal 等待、可信短链校验。
- `batch.py`：计数、连续失败熔断、停止原因。

应用层不得依赖生产数据库，不得绕过 repository 直接修改 JSONL。

### 2.5 数据与状态层

主要模块：

- `repository.py`：JSON/JSONL 读取、原子写入、按 SKU 幂等 upsert。
- `records.py`：linked/unavailable 记录构造和稳定哈希。
- `state_store.py`：队列校验、checkpoint、collection report。

关键要求：

- 所有写入使用临时文件 + 原子替换。
- SKU 级幂等，重复运行不产生重复行。
- linked 和 unavailable 必须互斥。
- queue、输出和 manifest 使用 SHA-256 绑定。
- 时间字段、schema version、worker、source tab、source tabs、structure hash 必须可追溯。

### 2.6 验证层

主要模块：

- `validation_io.py`：带错误计数的 JSONL 读取与 SKU 索引。
- `validation_rules.py`：可信 URL、必填字段、hash、频道、遗留来源、不可推广原因。
- `validation_service.py`：全量 accounting、overlap、extra、duplicate 和 manifest/report 输出。

验证层必须是纯文件校验；不得连接京东页面或生产数据库。当前若存在为了复用 URL 判断而实例化页面适配器的实现，应在后续改为纯函数/纯配置 validator。

## 3. 数据合同

### 3.1 队列记录

最少包含：

- `sku`
- `source_tabs`
- `structure_sha256`
- 可追溯到结构分析和候选池的来源字段

队列 manifest 最少包含：row count、data SHA-256、source tabs、source/structure file、commercial enabled 标识。

### 3.2 linked 记录

最少包含：

- `schema_version`, `status=ok`
- `sku`, `title`, `item_url`, `image_url`
- `price`, `commission_rate`, `estimated_income`
- `short_url`, `long_url`
- `source_tab`, `source_tabs`
- `link_created_at`, `link_expire_at`, `refresh_due_at`
- `structure_sha256`, `record_sha256`

可信短链必须满足配置中的 scheme 和 host，不能只检查字符串前缀。

### 3.3 unavailable 记录

允许的终态原因：

- `sold_out`
- `delisted`
- `not_promotable`

最少包含：SKU、标题、商品 URL、频道、观测时间、结构 hash、记录 hash。终态记录不应继续进入重试队列，除非未来定义了独立的周期性复查策略。

### 3.4 retryable failure

包括但不限于：

- 频道未找到；
- 卡片未匹配；
- 点击目标被遮挡但未能确认终态；
- modal 超时；
- 可信短链缺失；
- 临时浏览器异常。

retryable failure 只写报告/状态，不伪造 linked 或 unavailable 结果。

## 4. 风控状态机

```text
READY
  ├─ 页面安全 → COLLECTING
  ├─ 浏览器页缺失 → PAUSED
  └─ 验证码/滑块/风险页/登录失效 → STOP_REQUIRED

COLLECTING
  ├─ 成功/终态 → checkpoint → 继续
  ├─ 可重试失败 → 计数/熔断
  ├─ 连续失败达到阈值 → PAUSED
  └─ 任何风险标记 → STOP_REQUIRED
```

`STOP_REQUIRED` 必须写入机器可读文件和报告，返回稳定退出码，并禁止 supervisor 无限重启。人工恢复会话后，必须先做只读 session smoke，再恢复采集。

## 5. 单主流实现原则

- `main` 是唯一主流分支。
- 每个业务能力只有一个 canonical module/service。
- `v2/v3/...` 文件只可作为短期兼容入口，内部必须委托 canonical service；完成迁移后删除。
- 不允许同时维护两套采集算法、两套配置或两套数据合同并称为“备份”。
- 备份使用：Git tag、GitHub Release、不可变 artifact、数据库备份或受控归档；不使用长期并行代码分支。

## 6. 商用质量门禁

从采集到生产必须依次通过：

1. **Session gate**：人工会话有效，无风控标记。
2. **Queue gate**：队列存在、非空、row count/hash 与 manifest 一致。
3. **Collection gate**：批次可恢复、linked/unavailable 互斥、无未解释的 SKU 丢失。
4. **Validation gate**：JSONL 合法、URL 可信、必填字段完整、hash 正确、无 extra/duplicate/overlap。
5. **Commercial candidate gate**：`commercial_enabled` 由显式发布动作设置，采集脚本不得自行打开。
6. **Dry-run importer gate**：展示 insert/update/skip/reject 数量和样本，不写库。
7. **Landed validation gate**：写库后按 SKU、payload hash、source round、时间和商业字段核验。
8. **Rollback gate**：批次可按 source run/round 撤销或恢复，不依赖手工 SQL 猜测。

## 7. 可观测性

每次运行至少产生：

- JSON 结构化日志；
- 当前 state/checkpoint；
- collection report；
- validation report；
- output manifest；
- 明确 exit code；
- STOP_REQUIRED 时的机器可读原因。

日志不得记录 Cookie、账号信息、二维码、完整账户页面或敏感响应。

## 8. 通用商业版本要求

- 配置驱动，不绑定单一账号、单一机器或单一浏览器窗口。
- 数据合同版本化，向后兼容策略明确。
- 采集、验证、导入三个阶段可独立执行和重放。
- 不将页面文案当作唯一事实；终态识别应组合 DOM 状态、文本和点击结果。
- 价格、佣金、链接必须携带来源和采集时间；过期链接按配置进入 refresh queue。
- 商业导入默认关闭，只有质量门禁通过后显式开启。
