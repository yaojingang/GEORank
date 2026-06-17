# 01. 1.0 当前基线

本文件用于冻结当前 1.0 系统现状，作为 2.0 迁移的验收对照。

## 当前前台页面

公开页面与功能页面位于 `dist/`：

- `/`
- `/companies`
- `/c/:path_key`
- `/diagnostic`
- `/diagnostic/reports/:id`
- `/solutions`
- `/solutions/conversations/:id`
- `/keywords`
- `/tutorial`
- `/tutorial/:path_key`
- `/login`
- `/register`
- `/submit-company`

对应静态文件：

- `dist/index.html`
- `dist/company.html`
- `dist/diagnostic.html`
- `dist/solutions.html`
- `dist/keywords.html`
- `dist/tutorial.html`
- `dist/login.html`
- `dist/register.html`
- `dist/company-submit.html`

## 当前后台页面

后台页面位于 `dist/admin/`：

- `index.html`
- `companies.html`
- `diagnostics.html`
- `solutions.html`
- `keywords.html`
- `tutorials.html`
- `tutorials-edit.html`
- `users.html`
- `settings.html`

## 当前前台业务模块

### 公司

能力：

- 公司列表
- 公司详情
- 提交公司
- 公司审核前分析页

### 诊断

能力：

- 官网 URL 诊断
- 报告历史与详情
- 公开报告展示

### 方案

能力：

- 对话式方案生成
- 历史会话
- SSE 流式输出
- 相关追问

### 拓词

能力：

- 输入关键词
- AI 识别业务画像
- 输出 8 个维度的关键词词包

### 教程

能力：

- 教程频道首页
- 教程详情页
- SSR 文本输出
- 左右侧栏目录

## 当前后端业务域

后端路由位于 `backend/app/api/routes`：

- `auth.py`
- `companies.py`
- `diagnostics.py`
- `solutions.py`
- `content.py`
- `keywords.py`
- `admin.py`
- `settings.py`

主路由汇总位于 `backend/app/api/__init__.py`。

## 当前后端基础设施

主应用：

- `backend/app/main.py`

异步与数据基础设施：

- Celery
- Postgres
- Redis
- Qdrant
- Neo4j
- MinIO
- Playwright crawler

容器编排：

- `docker-compose.yml`

## 当前数据库迁移基线

已有 Alembic 迁移：

- `001_initial.py`
- `002_conversations_user_nullable.py`
- `003_normalize_enum_labels.py`
- `004_add_content_path_keys.py`
- `005_add_company_crawl_plan_fields.py`
- `006_add_company_path_keys.py`
- `007_add_user_phone.py`

## 当前技术栈判断

前端：

- 静态 HTML/CSS/JS
- 若干 SSR 页面通过 FastAPI `web/` 路由输出

后端：

- FastAPI + SQLAlchemy + Alembic
- Celery + Redis
- OpenAI/LangChain
- Qdrant + Neo4j

## 当前 1.0 的长期问题

### 前端问题

- 缺少统一应用框架
- 缺少正式组件层
- 缺少正式 i18n 机制
- 功能页状态逻辑散落在多个 JS 文件

### 契约问题

- 虽然已有 OpenAPI 基础，但前端未真正 SDK 化
- 页面仍有大量手写请求逻辑

### 鉴权问题

- 前台登录体系已存在，但仍然偏页面脚本驱动
- 不适合长期扩展到多端、多语言和统一后台

### CLI 问题

- 目前以后台页面与脚本为主，缺少正式 CLI 入口
