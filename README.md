# WMS 仓储管理系统

自建 WMS 仓储管理系统（P0 核心链路）。技术栈：PostgreSQL 15 + FastAPI + Vue3 + Element Plus + Redis + Docker Compose。

## 项目概述

面向跨境电商自建仓的仓储管理系统，覆盖从 SKU/库位主数据、Excel 订单导入、库存记账，到订单履约（分配→拣货→复核→打包→打印→出库）的核心链路。

- **期初数据**：2236 SKU（base 2047 / combo 186 / marker 3）+ 500 库存行（3930 件）+ 376 BOM + 146 库位
- **核心能力**：订单状态机、BOM 组合展开、库存守恒记账、出库打印卡点、虚拟/标记 SKU 规则引擎

## 目录结构

```
wms/
├── docker-compose.yml        # 一键启动 postgres + redis + backend + frontend
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── main.py           # 应用入口（45 条路由）
│   │   ├── core/             # 配置、数据库、状态机、异常
│   │   ├── models/           # SQLAlchemy 模型（30 表，对齐数据字典）
│   │   ├── schemas/          # Pydantic 模型
│   │   ├── api/              # 路由（S0~S2 全部模块）
│   │   ├── services/         # 业务逻辑（库存记账/分配/拣货/出库/上架/导入引擎）
│   │   ├── init_db.py        # 建表 + 种子数据
│   │   └── init_switch.py    # 期初数据切换（文件A/B导入）
│   ├── tests/                # pytest 单元测试（37 项）
│   ├── seed_demo.py          # 端到端演示数据
│   ├── e2e_verify.py         # 端到端联调验证（20 项断言）
│   └── alembic/              # 数据库迁移
├── frontend/                 # Vue3 + Vite 前端（主数据/导入/规则）
├── frontend-s2/              # S2 履约前端（CDN 单页，订单分配/拣货/复核打包/出库/库存/库位上架）
└── docs/                     # 项目文档
    ├── 数据字典.md           # 权威数据字典（30 表字段级定义）
    ├── S2技术方案.md         # S2 履约链路技术方案
    ├── WMS_S3_技术设计方案.md # S3 技术方案（打印/权限/期初/验收）
    ├── 云途面单.md           # 云途面单打印逻辑
    └── ...
```

## 快速开始

```bash
cd wms
cp .env.example .env   # 配置 POSTGRES_PASSWORD
docker compose up -d --build
```

- 后端 API 文档：http://localhost:8000/docs
- 前端：http://localhost:5173

## 期初数据初始化

```bash
# 1. 建表 + 种子数据（仓库 + 4 条虚拟/标记规则）
docker exec wms-backend python -m app.init_db

# 2. 期初数据切换（导入 文件A_库存台账.xlsx / 文件B_BOM.xlsx）
#    需先将两个文件放到 backend/ 目录（挂载为容器内 /app）
docker exec wms-backend python -m app.init_switch
```

## 端到端联调

```bash
# 准备演示数据（重置业务表并造 2 个订单：正常链路 + 缺货链路）
docker exec wms-backend python seed_demo.py

# 跑完整链路验证（20 项断言）
docker exec wms-backend python e2e_verify.py

# 单元测试
docker exec wms-backend python -m pytest -q
```

## 数据库

- 数据库：`wms`，用户 `wms`，默认密码 `wms_dev_password`（通过 `POSTGRES_PASSWORD` 环境变量覆盖）
- 迁移工具：Alembic
- 30 张表全部对齐《数据字典》（英文枚举 + 标准审计字段 `id/created_at/updated_at/created_by/updated_by/deleted`）

## 核心设计

### 订单状态机

```
unassigned → assigned → picking → checked → packed → outbound
                ├─ intercepted（拦截）
                ├─ manual_review（待人工复核）
                └─ shortage_hold（缺货挂起）
```

### 库存守恒

- 所有库存变动只通过 `stock_service`（唯一入口），强制写 `stock_transaction` 留痕
- 分配阶段 `available_qty → allocated_qty`，出库阶段扣 `allocated_qty`（不二次扣减）

### BOM 展开

- 组合 SKU 递归展开到 base 子件，子件用量相乘
- 解析用「最后一个 `*`」切分数量（避免 SKU 名内含 `*` 的陷阱）

### 出库打印卡点

- `outbound.label_printed == 0` 时出库返回 409（可配置 `REQUIRE_LABEL_PRINTED`）
