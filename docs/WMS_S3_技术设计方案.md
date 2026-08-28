# WMS S3 技术设计方案：批量打印 + 权限留痕 + 期初数据切换 + 联调验收

| 项 | 内容 |
|---|---|
| 任务 | 【P0·S3】批量打印 + 期初数据切换 + 联调验收 |
| 版本 | v1.0（评审稿） |
| 负责人 | 树头、小葵花妈妈课堂开课了 |
| 工期 | 2026-10-03 ~ 2026-10-16 |
| 前置依赖 | S2 履约链路（订单状态机 / 打包 / 出库） |
| 技术栈 | PostgreSQL 15 + FastAPI + Vue3 + Element Plus + Redis + Docker Compose |
| 对齐文档 | 《WMS全系统数据字典_字段级》《WMS页面与流程清单》《S2技术设计方案》《云途面单打印逻辑文档》 |
| 部署环境 | 服务器 81.71.14.232（内网 10.1.0.13），Docker 29.7.2 + Compose v5.5.0 |

---

## 0. 探活结论与现状基线（2026-08-28 实测）

> 本节记录 S3 开工前对部署服务器与代码仓库的实测结论，作为方案的事实基线。**不得虚构任何数据。**

### 0.1 服务器与运行环境

| 项 | 实测值 |
|---|---|
| 系统 | Ubuntu 22.04（VM-0-13-ubuntu，内核 5.15.0-181） |
| 资源 | 2 核 / 3.6G 内存 / 59G 磁盘（已用 9.6G，可用 47G） |
| Docker | 29.7.2，Docker Compose v5.5.0 |
| 运行容器 | `wms-postgres`(5433)、`wms-backend`(8000)、`wms-frontend`(5173)、`wms-redis`(6379)，全部 Up |
| 代码目录 | `/home/ubuntu/wms/`（无 Git 仓库，符合任务设定「无代码仓库」） |
| 备份 | `/home/ubuntu/ows_backup_20260828/`（旧 OWS 原型）；`~/wms_s0.tar.gz`、`~/wms_s1.tar.gz`（阶段快照） |

### 0.2 各阶段实际进度（与任务状态对齐）

| 阶段 | 任务状态 | 代码/DB 实测 | 结论 |
|---|---|---|---|
| S0 脚手架+主数据 | 待开始(claim) | **30 张表已全部建好**；sku/rules/warehouse API 已实现；importer 目录已建 | 代码层面已基本完成 |
| S1 导入引擎 | 进行中(running) | `services/importer/{parser,bom,validator,importer}.py` 已写；`api/importer.py` 已注册 | 代码已产出，联调待确认 |
| S2 履约链路 | 进行中(running) | **无任何履约 API**；仅 `models/order.py` 有 ORM 模型 | 后端逻辑未实现 |
| S3 本任务 | 进行中(running) | 尚未开始 | — |

### 0.3 探活发现的「模型与数据字典偏差」（S3 必须修正）

> 现有 `order.py` / `other_domains.py` / `system.py` 模型与《数据字典》及《S2 技术方案》存在**字段名与枚举值偏差**。S3 依赖 S2 履约链路，以下偏差若不在 S2/S3 交付前对齐，将导致打印卡点、状态机、权限留痕无法正确落地。

| # | 位置 | 现状（代码） | 数据字典/S2 要求 | 影响 | 处置 |
|---|---|---|---|---|---|
| 1 | `package.status` | 中文枚举 `待分配/已分配/拣货中/已复核/已打包/已出库` | 英文 `unassigned/assigned/picking/checked/packed/outbound/intercepted/manual_review/shortage_hold` | 状态机校验、前端路由、打印卡点判定全部依赖 | **S3 联调前必须统一为英文枚举** |
| 2 | `package` 字段 | `logistics_method` / `paid_at` / `is_supplement` | `logistics_channel` / `pay_time` / `is_resend` | 字段映射不一致 | 对齐数据字典命名 |
| 3 | `outbound` 表 | **缺 `label_printed` 字段**（仅 `package_id/outbound_at`） | 需 `label_printed TINYINT`（未打印不允许出库）+ `status` + `outbound_no` + `shipped_at` | **S3 打印硬卡点无法实现** | 补字段 + Alembic 迁移 |
| 4 | `print_queue` | 状态用中文 `待打印/已打印/失败`，缺 `printed_at`、`template_id` 为可空 | 英文 `queued/printing/success/failed` + `printed_at` | 打印队列状态机与重打逻辑 | 对齐枚举 |
| 5 | `operation_log` | 字段 `operator/action/target_type/target_id` | 需 `user_id/module/action/ref_type/ref_id/detail/ip/created_at` | 权限留痕口径不一致 | 对齐数据字典 |
| 6 | `role` 表 | 仅 `code/name`，**无 `permissions` JSON 字段** | 需 `permissions JSON`（8 角色页面级权限矩阵） | **T3.2 权限矩阵无法落地** | 补 `permissions` 字段 |
| 7 | `user` 表 | 有 `role_id`（单一角色） | 数据字典同（单一 role_id） | 无 | 无需改动 |

> **结论**：S3 的 T3.1（打印卡点依赖 `outbound.label_printed`）、T3.2（权限依赖 `role.permissions` + `operation_log` 字段）都需要先做一轮**数据模型对齐迁移**。建议在 S2 交付验收时一并修正，或在 S3 开头作为 T3.0「对齐修正」先行落地。

### 0.4 期初数据文件基线（已下载至本地并验证）

| 文件 | 本地路径 | 实测结构 | 用途 |
|---|---|---|---|
| 文件A 库存台账 | `文件A_库存台账.xlsx` | 2052 行（2 行表头+2050 数据）× 6 列 | SKU 主数据 + 期初库存 + 库位 |
| 文件B 组合BOM | `文件B_BOM.xlsx` | 188 行（2 行表头+186 数据）× 7 列（含"包含子SKU"） | 组合 BOM |
| 订单样本 | `订单样本.xlsx` | 799 行（1 行表头+798 数据）× 8 列 | 联调测试数据 |

> 三份文件均为两行表头（文件A/B）或单行表头（订单），与交接文档、核验记录完全一致。文件 A/B 第 1 行为分组标题（仓库信息/商品信息），第 2 行为字段名，导入须跳过第 1 行。

---

## 1. 目标与范围

### 1.1 目标

在 S2 履约链路（订单状态机 + 打包 + 出库）就绪后，S3 完成四件事，达成 P0「端到端可上线」：

1. **T3.1 批量打印**：三种包裹类型自动识别、打印队列 + 失败重打、云途面单 API 打印、未打印不允许出库的硬卡点。
2. **T3.2 权限与留痕**：8 角色页面级权限矩阵落地，`operation_log` 全量留痕。
3. **T3.3 期初数据切换**：导入文件 A（2050 SKU + 期初库存 3930 件 + 库位）、文件 B（186 BOM）、配置规则、补录任务。
4. **T3.4 联调验收**：端到端 `导入 → 分配 → 拣货 → 复核 → 打包 → 打印 → 出库` 走通，AC 清单回归，期初数据与核验记录一致。

### 1.2 验收标准（任务既定）

> PRD AC-01~12 + 履约链路全通；期初数据与核验记录一致。

### 1.3 子模块与数据字典表映射

| 子模块 | 内容 | 涉及表 |
|---|---|---|
| T3.0 对齐修正 | 修正模型与数据字典偏差（见 §0.3） | package/outbound/print_queue/operation_log/role |
| T3.1 批量打印 | 三类型识别、打印队列、云途面单、重打、打印卡点 | print_template、print_queue、outbound、package |
| T3.2 权限留痕 | 8 角色权限矩阵、operation_log 全量留痕 | role、user、operation_log |
| T3.3 期初切换 | 文件A/B 导入、规则配置、补录任务 | sku、bom、stock、location、virtual_rule、import_batch |
| T3.4 联调验收 | 端到端链路 + AC 回归 | 全链路 |

---

## 2. T3.0 数据模型对齐修正（前置，必须先行）

### 2.1 需要新增/修正的字段（Alembic 迁移）

```python
# package —— 状态枚举统一为英文（对齐数据字典/S2）
status: unassigned/assigned/picking/checked/packed/outbound/intercepted/manual_review/shortage_hold

# package —— 字段重命名对齐
logistics_method → logistics_channel
paid_at → pay_time
is_supplement → is_resend

# outbound —— 补齐打印卡点与出库单字段
status: pending/shipped/cancelled（默认 pending）
outbound_no: VARCHAR(64) UNIQUE
label_printed: TINYINT（默认 0，未打印不允许出库）★ S3 硬卡点
shipped_at: DATETIME

# print_queue —— 状态枚举对齐 + 补时间字段
status: queued/printing/success/failed（原中文待打印/已打印/失败）
printed_at: DATETIME（成功打印时间）
retry_count: INT（已有）

# operation_log —— 字段对齐
operator → user_id；target_type → ref_type；target_id → ref_id
新增 module、ip；action 语义对齐

# role —— 补权限集
permissions: JSON（8 角色页面级权限矩阵，见 §4）
```

### 2.2 状态机英文枚举映射（前端+后端统一）

| 中文 | 英文枚举（权威） |
|---|---|
| 待分配 | unassigned |
| 已分配 | assigned |
| 拣货中 | picking |
| 已复核 | checked |
| 已打包 | packed |
| 已出库 | outbound |
| 拦截 | intercepted |
| 待人工复核 | manual_review |
| 缺货挂起 | shortage_hold |

---

## 3. T3.1 批量打印（核心）

### 3.1 三种包裹类型自动识别

> 依据《云途面单打印逻辑文档》与数据字典 §8.2，同 SKU 汇总后打印。

| 类型 | 判定规则 | 打印内容 |
|---|---|---|
| 单品单件 | 包裹内 1 个 SKU，qty = 1 | 单条标签：包裹号 + SKU + 数量 1 + 运单号 |
| 单品多件 | 包裹内 1 个 SKU，qty > 1 | 单条标签：包裹号 + SKU + 数量 n + 运单号 |
| 重复多品 | 包裹内多个 SKU（或多条明细） | 多条标签，**同 SKU 汇总数量**后逐条打印 |

识别入口：以 `package_item`（`package_id + sku_id` 唯一）聚合，`virtual`(YUN) 与 `marker` 明细**不参与打印**（YUN 免面单）。

```python
def classify_package(package_id) -> str:
    items = package_item 中该 package 的非 virtual、非 marker 明细
    distinct_skus = len(set(item.sku_id for item in items))
    total_qty = sum(item.qty for item in items)
    if distinct_skus == 1 and total_qty == 1:
        return "single_single"   # 单品单件
    if distinct_skus == 1:
        return "single_multi"    # 单品多件
    return "multi_sku"           # 重复多品
```

### 3.2 打印流程与队列

#### 3.2.1 包裹标签打印（内部标签，无需云途）

```
打包完成(packed) → 生成 print_queue(queued) → 打印(printing) → success
                                                  └→ failed → 重试(retry_count++)
```

- 打印队列状态机：`queued → printing → success`，失败 `failed → printing`（重试，`retry_count` 递增）。
- **失败重打**：`print_queue.status=failed` 的包裹支持手动「重打」，重新入队。
- 标签内容：包裹号 + SKU 明细 + 数量 + 运单号（对齐页面清单「打包作业」）。

#### 3.2.2 云途面单打印（凭运单号，P0 主链路）

依据《云途面单打印逻辑文档》§2-3，直接复用已验证的 OMS 模式设计：

```
勾选包裹(最多100单) → POST /api/print/labels/pdf
  → 取 tracking_no → yuntuClient 批量调云途（20单/批 + 失败单逐个兜底）
  → 逐单下载面单 PDF（20s超时，单张≤5MB）
  → pdf-lib 合并（每单取第1页，保留10×10cm原始尺寸，不缩放）
  → 返回合并 PDF + X-Label-OK / X-Label-Failed
  → 用户确认打印成功 → POST /api/print/labels/mark-printed
  → outbound.label_printed=1 + label_url 缓存 + print_queue.status=success
```

**云途 API 关键参数（OMS 模式，已实测可用）**：

| 项 | 值 |
|---|---|
| 接口 | `POST http://oms.api.yunexpress.com/api/Label/Print` |
| 鉴权 | `Authorization: Basic Base64("CN5834&oHRl28wOmQo=")` |
| 请求体 | `["YT...","YT..."]`（运单号数组） |
| 成功判定 | `Code === "0000"` 且 `Item[].Url` 有值 |
| 面单地址 | `Item[].Url` |

> ⚠️ 密钥 `CN5834` / `oHRl28wOmQo=` 属敏感信息，仅存服务器环境变量 `.env`，**不得提交 Git / 外发文档**。S3 实现时走 `.env.production` 注入。

#### 3.2.3 打印卡点（未打印不允许出库）

```python
# 出库接口前置校验（对齐 S2 技术方案 §8.1）
if outbound.label_printed == 0:
    raise HTTPException(409, "面单未打印，禁止出库")
```

- 硬卡点字段：`outbound.label_printed`（T3.0 已补）。
- 打印成功（`mark-printed`）后才置 1；出库校验 `label_printed == 1` 且 `package.status == packed`。

### 3.3 打印接口清单（FastAPI）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/print/queue` | 打印队列查询（按状态筛选） |
| POST | `/api/print/labels/pdf` | 批量面单 PDF（云途，≤100 单，返回合并 PDF） |
| POST | `/api/print/labels/mark-printed` | 标记已打印（写 label_printed=1 + label_url 缓存） |
| POST | `/api/print/queue/{id}/retry` | 失败重打 |
| POST | `/api/print/classify` | 三类型识别（调试/预览用） |

---

## 4. T3.2 权限与留痕

### 4.1 8 角色权限矩阵（页面级，对齐《页面流程清单》§五）

`role.permissions`（JSON）按「页面路由 → 权限」结构存储，权限粒度：`●`(写) / `○`(读) / `-`(无)。

| 页面 | receiver | putaway | picker | checker | packer | shipper | purchaser | admin |
|---|---|---|---|---|---|---|---|---|
| 订单列表 | ○ | ○ | ● | ● | ● | ● | ○ | ● |
| 订单导入 | - | - | - | - | - | - | - | ● |
| 人工复核队列 | - | - | - | ● | - | - | - | ● |
| 异常队列 | - | - | - | ● | - | - | - | ● |
| 拣货任务 | - | - | ● | - | - | - | - | ○ |
| 复核作业 | - | - | - | ● | - | - | - | ○ |
| 打包作业 | - | - | - | - | ● | - | - | ○ |
| 出库管理 | - | - | - | - | - | ● | - | ● |
| 面单打印 | - | - | - | - | ● | ● | - | ● |
| 库存台账 | - | - | ○ | - | - | - | ○ | ● |
| 库存流水 | - | - | - | - | - | - | - | ● |
| 库位管理 | - | ● | - | - | - | - | - | ● |
| 库存调整 | - | - | - | - | - | - | - | ● |
| 批次效期 | - | - | - | - | - | - | - | ● |
| 预警中心 | - | - | - | - | - | - | ○ | ● |
| 采购单管理 | - | - | - | - | - | - | ● | ● |
| 补货建议 | - | - | - | - | - | - | ● | ● |
| 到货签收 | ● | - | - | - | - | - | ○ | ● |
| 上架任务 | - | ● | - | - | - | - | - | ○ |
| 快进快出直分 | ● | - | - | - | - | - | - | ● |
| SKU 主数据 | - | - | - | - | - | - | ○ | ● |
| 期初库存导入 | - | - | - | - | - | - | - | ● |
| 供应商管理 | - | - | - | - | - | - | ● | ● |
| 规则配置 | - | - | - | - | - | - | - | ● |
| 用户与角色 | - | - | - | - | - | - | - | ● |
| 操作日志 | - | - | - | - | - | - | - | ● |
| 盘点管理 | - | - | - | - | - | - | - | ● |

> ● = 写权限；○ = 只读；- = 无权限

### 4.2 权限校验实现

- 后端：FastAPI 依赖注入 `require_permission(route)`，从 JWT 解析 user → role → permissions，无权限返回 403。
- 前端：路由守卫按 `role.permissions` 控制菜单/页面可见性与操作按钮。
- 8 个角色 `code`：`receiver/putaway/picker/checker/packer/shipper/purchaser/admin`。

### 4.3 operation_log 全量留痕

| 字段（对齐数据字典 §9.3） | 说明 |
|---|---|
| user_id | 操作人 |
| module | 模块（订单/库存/打印/主数据/系统…） |
| action | 动作（create_sku/allocate/print/mark_printed/outbound/adjust…） |
| ref_type | 关联类型（package/outbound/stock/sku…） |
| ref_id | 关联 id |
| detail | 详情 JSON（变更前后值） |
| ip | 来源 IP |
| created_at | 操作时间 |

**留痕规则**：所有写操作（导入、分配、拣货、复核、打包、打印、出库、库存调整、规则配置、权限变更）必须在同一事务内写一条 `operation_log`。打印与出库为**强制留痕点**（对账需要）。

---

## 5. T3.3 期初数据切换

### 5.1 切换步骤（对齐交接文档 §六、页面清单 §3.5）

```
① 导入文件A → SKU 主数据(2050) + 期初库存(真实3930件，剔除3标记SKU) + 库位绑定(751 SKU 有位)
② 导入文件B → 186 条组合 BOM（按「最后一个 *」切分数量）
③ 配置规则 → YUN=虚拟 / CS99=拦截 / CS00=强制复核 / CS000=采购跳过
④ 补录任务 → 149 无库位正库存 SKU 上架 / 批次补录 / 空名称补录 / 8 处数量不一致人工核对
```

### 5.2 文件 A 导入（SKU + 期初库存 + 库位）

| 步骤 | 规则 |
|---|---|
| 表头 | 跳过第 1 行（分组标题），字段在第 2 行 |
| SKU 建档 | 2050 个 SKU，`sku_code` 保留空格与 `*`（不 trim），`sku_name` 6 行空暂置空 |
| 标记 SKU 剔除 | `CS99-No!!!`(99999)、`CS00-Check!!!`(99740)、`CS000-ignore`(382) **不计入真实库存**，sku_type=marker |
| 期初库存 | 真实库存 **3930 件** = 名义 204051 − 三个标记 SKU 占位值；503 个正库存 SKU |
| 库位绑定 | 751 个 SKU 有位（36.6%），三段式 `货架-列-层`；145 个唯一库位 |
| 初始 stock 行 | `location_id` 有库位则绑库位；无库位正库存 SKU（149 个）暂入「暂存区库位」，待补上架 |

### 5.3 文件 B 导入（组合 BOM）

| 步骤 | 规则 |
|---|---|
| 表头 | 跳过第 1 行，字段在第 2 行（含"包含子SKU"列） |
| BOM 解析 | 格式 `子SKU*数量;子SKU*数量;`，**必须按「最后一个 `*`」切分数量**（`段.rfind('*')`） |
| 陷阱 | 误用「第一个 `*`」会产生 16 处残断（`CS190-*` 系列 8 + `CS28-100 inches(...)` 系列 8），必须规避 |
| 关系 | 186 组合 SKU 全部 sku_type=combo，不设实物库存；179 个子 SKU 100% 落在文件 A |
| 结果 | 186 条 bom（combo_sku_id + component_sku_id + qty），单层无嵌套 |

### 5.4 规则配置（virtual_rule）

| 规则 | match_type | match_value | action |
|---|---|---|---|
| YUN=虚拟 | exact | `YUN` | skip（免拣/免库存/免面单） |
| CS99=拦截 | prefix | `CS99` | intercept |
| CS00=强制复核 | prefix | `CS00` | manual_review |
| CS000=采购跳过 | prefix | `CS000` | ignore |

### 5.5 补录任务清单（切换后待办）

| # | 任务 | 数量/口径 | 状态 |
|---|---|---|---|
| ① | 无库位正库存 SKU 上架 | 149 个（503 正库存 − 354 有库位） | 待补 |
| ② | 正库存 SKU 批次补录 | 文件 A 无批次/效期列，需人工补录 | 待补 |
| ③ | 空名称 SKU 补录 | **实测 6 个**（CS455-F/E/D/C/B/A）+ 空图片 4 个（CS202-Blue、CS125-C5 non polarized、CS125-C5 polarized、CS125-X7 camo polarzied）| 待补 |
| ④ | 8 处数量不一致包裹核对 | 8 行 sku_count=2 且 total∈{4,6} | 待人工核对 |

> ⚠️ 注意：交接文档原写「17 个空名称 SKU」，但核验记录实测为 **6 个空名称 + 4 个空图片**。「17」疑为笔误，S3 切换按实测 **6 个空名称 SKU** 执行，差异已提交用户确认。

### 5.6 期初切换验收口径

切换完成后，必须满足：
- SKU 总数 = 2050（文件A）+ 186（文件B，combo）+ YUN（virtual，订单导入时自动建）= 2237
- 真实期初库存 = **3930 件**，与核验记录一致
- 标记 SKU 3 个，不进真实库存
- 组合 BOM 186 条，179 子 SKU 全部可匹配主数据
- 库位 145 个，751 SKU 有位

---

## 6. T3.4 联调验收

### 6.1 端到端链路

```
导入订单样本(798行) → 分配(unassigned→assigned) → 拣货(→picking→checked)
  → 复核(→checked) → 打包(→packed) → 批量打印(label_printed=1) → 出库(→outbound)
```

### 6.2 验收用例（对齐任务标准 + AC 回归）

| # | 用例 | 期望结果 |
|---|---|---|
| 1 | 端到端走通 unassigned→outbound | 状态机全链路无阻塞 |
| 2 | 出库后库存正确扣减 | `allocated_qty` 扣减、`available_qty` 不变（分配阶段已扣）、`stock_transaction` 全程留痕且 before/after 守恒 |
| 3 | 组合 SKU 按 BOM 展开 | 子件锁定，子件不足整单挂起 |
| 4 | 未打印面单出库 | 返回 409 拦截 |
| 5 | 含 CS99/CS00 标记 SKU | 分别进 intercepted / manual_review |
| 6 | 三种包裹类型识别 | 单品单件/单品多件/重复多品正确分类，同 SKU 汇总 |
| 7 | 打印失败重打 | failed → 重试 → success，retry_count 递增 |
| 8 | YUN 虚拟品 | 免拣货/免库存/免面单，单独视图 |
| 9 | 期初数据一致性 | 3930 件、2050 SKU、186 BOM、145 库位与核验记录一致 |
| 10 | 8 角色权限矩阵 | 越权访问返回 403 |
| 11 | operation_log 留痕 | 打印/出库等写操作全程留痕可查 |
| 12 | AC-01~12 回归 | PRD §9 全部通过 |

### 6.3 交付物

1. T3.0 对齐修正的 Alembic 迁移脚本
2. T3.1 打印服务（`PrintService` / `YuntuClient`）+ 打印队列 + 云途面单接口
3. T3.2 权限矩阵（`role.permissions`）+ 权限校验依赖 + operation_log 全量留痕
4. T3.3 期初切换脚本（文件A/B 导入 + 规则配置 + 补录任务清单）
5. T3.4 端到端联调 + AC 回归报告

---

## 7. 关键风险与待确认项

| # | 风险 / 待确认 | 影响 | 建议 |
|---|---|---|---|
| 1 | **S2 履约链路未实现**（探活实测无履约 API） | S3 打印卡点、联调验收均依赖 S2 出库 | S3 排期前必须先完成 S2；或 S3 开头先补 T3.0 对齐修正 + 协助 S2 |
| 2 | **模型与数据字典偏差**（§0.3 共 6 处） | 状态机/打印卡点/权限矩阵无法落地 | T3.0 先行修正（Alembic 迁移） |
| 3 | **期初数据文件不在服务器**（实测 `/tmp` 仅订单样本） | T3.3 切换需先把文件 A/B 上传服务器 | S3 开工时上传三份 xlsx |
| 4 | 云途密钥敏感 | 泄露风险 | 仅存 `.env.production`，不提交 Git/外发文档 |
| 5 | 空名称 SKU「17 vs 6」口径 | 补录范围不确定 | 按实测 6 个执行，已提交用户确认 |
| 6 | 打印卡点字段 `outbound.label_printed` 缺失 | 出库强校验无法实现 | T3.0 补字段 |

---

## 8. 结论

S3 是 P0 的收尾阶段，目标是让系统达到「可上线」状态。探活表明：**基础设施与 S0 已完成，S1 进行中，S2 履约链路尚未实现，且现有模型存在 6 处与数据字典的偏差需先行修正**。S3 建议按以下顺序推进：

```
T3.0 对齐修正 →（依赖 S2 完成）→ T3.1 打印 + T3.2 权限留痕 → T3.3 期初切换 → T3.4 联调验收
```

其中 **T3.3 期初切换相对独立**（数据文件已就绪，sku/stock/bom 表已建），可在 S2 未完成时先行落地，为联调验收预置数据。

---

## 附录：T3.0 数据模型对齐重构（2026-08-28 已落地）

> 本节记录 S3 阶段执行「表结构对齐数据字典」重构的完整结论，作为后续 T3.1~T3.4 的事实基线。

### 背景与决策

S2 履约代码交付后，实测发现服务器上 S0/S1 代码建的表结构**系统性偏离《数据字典》**（中文枚举「基础/组合」「空/占用」「待分配」，字段名 `name`/`available`/`logistics_method` 等），而 S2 履约代码严格按字典编写（英文枚举 `base/combo`/`empty/occupied`/`unassigned`，字段 `sku_name`/`available_qty`/`logistics_channel`，含 `label_printed` 打印卡点字段）。

**决策：以《数据字典》为唯一权威，重构生产库表结构 + 统一模型层。**

### 重构内容

| 层 | 改动 |
|---|---|
| 模型层 | 重写 `app/models/`，统一 30 张表对齐字典：标准审计字段（`id` BIGINT/`created_at`/`updated_at`/`created_by`/`updated_by`/`deleted`）+ 英文枚举 |
| 履约域 | 直接采用 S2 定义（sku/shelf/location/bom/putaway_task/stock/stock_transaction/allocation/package/package_item/picking_task/packing/outbound） |
| 其余域 | 补齐字典字段：warehouse(+address)、supplier(+phone)、采购3张、快进快出(+sku_id/match_qty)、盘点3张、导入4张(virtual_rule 改 rule_type/match_type/match_value/action)、打印2张、系统3张(role+permissions) |
| 适配 S0/S1 | importer/sku/rules/warehouse API + 导入引擎 + init_switch 全部适配新字段名/英文枚举 |
| 修复 S2 bug | picking_service 的 `db.query()`(2.0 移除)、putaway `recommend` 改 GET、`pack` 补 packer_id、PutawayTask 导入路径 |

### 验收结果

| 验证项 | 结果 |
|---|---|
| 期初数据切换 | 2236 SKU（base 2047/combo 186/marker 3）+ 500 库存行（3930 件）+ 376 BOM + 146 库位 |
| 端到端联调 e2e | **20/20 通过**（分配→拣货→复核→打包→出库卡点→出库，含出库硬卡点 409） |
| 单元测试 pytest | **37/37 通过** |
| 后端健康 | `/health` 正常，45 条路由（S0/S1 4 模块 + S2 6 模块 + health） |

### 数据库备份

- 重构前完整备份：`~/wms/backups/wms_backup_20260828_222540.dump`（232KB，32 张表）
- 旧代码备份：`~/wms/backend/app_backup_20260828_223346/`
