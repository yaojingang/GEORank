# 02. 2.0 目标架构

## 总体方向

GEOrank 2.0 采用：

- 前端应用层重构
- 后端业务核心保留
- 契约层与会话层重构
- 多语言与 CLI 能力前置设计

## 最终技术栈

### 前端

- Next.js App Router
- TypeScript
- React Server Components
- next-intl

### 后端

- FastAPI
- Celery
- SQLAlchemy
- Alembic

### 数据与基础设施

- Postgres
- Redis
- Qdrant
- Neo4j
- MinIO
- Playwright

### 契约与工具

- OpenAPI
- TypeScript SDK 生成
- Typer CLI
- pnpm workspace
- Turborepo

## 新目录结构

```text
GEOrank/
  apps/
    web/
    admin/
  packages/
    ui/
    api-sdk/
    i18n/
    auth/
  cli/
    georank_cli/
  backend/
  docs/
```

## 边界

### `apps/web`

负责：

- 前台公开页面
- 前台登录后功能页
- locale 路由
- SSR/SEO/GEO 输出

### `apps/admin`

负责：

- 后台管理台
- 后台鉴权页面
- 后台模块页

### `packages/ui`

负责：

- 前后台共享组件
- 页面壳
- 卡片、表单、图表、布局组件

### `packages/api-sdk`

负责：

- 基于 OpenAPI 生成的 TS SDK
- 统一请求 client
- 统一错误包装

### `packages/i18n`

负责：

- locale 路由规则
- 语言字典
- 多语言 metadata 工具

### `packages/auth`

负责：

- 会话读取
- 页面 guard
- 浏览器绑定规则

### `cli/georank_cli`

负责：

- 运维命令
- 批量业务命令
- 内容/数据修复命令

## 渐进迁移策略

1. 新前台与旧前台并行
2. 新后台与旧后台并行
3. SDK 先于页面迁移
4. 旧 URL 必须兼容
5. 新页面通过后再切换流量入口
