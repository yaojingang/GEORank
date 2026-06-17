# GEOrank GitHub 开源推送规则

> 用途：在将 GEOrank 推送到 GitHub 或公开仓库前，统一判断哪些内容可以公开、哪些内容必须留在本地或私有仓库。后续需要执行推送时，以本文为准做检查，不直接 `git add .`。

## 1. 推送原则

GEOrank 开源时只推送“可复用的产品工程能力”，不推送“运营数据、私有内容资产、密钥、真实客户资料和本地验证产物”。

默认规则：

- 能说明系统如何运行的代码、配置模板、迁移脚本和公开文档可以推送。
- 能还原真实业务数据、客户数据、专家库、教程内容资产、API Key 或本地运行状态的内容不能推送。
- 不确定是否公开时，先归为“不能推送”，再人工确认。
- 公开仓库要能在没有私有数据的情况下启动基础页面和开发环境，私有数据通过种子样例或后台录入补充。

## 2. 可以推送

### 代码与工程结构

- `apps/web/`：Next.js 前台代码。
- `apps/admin/`：Next.js 后台代码。
- `packages/`：共享 SDK、UI、i18n、auth 等包。
- `backend/app/`：FastAPI、Celery、模型、服务层、API 路由。
- `backend/alembic/versions/`：数据库结构迁移脚本。
- `cli/`：CLI 源码。
- `infra/`：不含生产密钥的 Nginx、Traefik 等配置。
- `docker-compose.yml`：本地开发编排，前提是只引用 `.env.example` 中的模板变量。
- `package.json`、`pnpm-lock.yaml`、`pnpm-workspace.yaml`、`turbo.json`、`tsconfig.base.json`。

### 模板与说明

- `.env.example`：环境变量模板，可以保留占位值和说明，但不能包含真实 key。
- `README.md`：公开项目介绍。
- `docs/2.0/`：架构、迁移、风险、治理等工程规划文档。
- `docs/Architecture.md`、`docs/TestStrategy.md`、`docs/TechnologyDecision.md` 等不含私有数据的工程文档。
- `.github/`：CI、issue 模板、PR 模板，前提是不含私有 token。

### 可公开样例

- 脱敏后的 demo 公司数据。
- 脱敏后的 demo 诊断报告。
- 脱敏后的 demo 教程目录结构。
- 脱敏后的 demo 专家卡片。

样例数据必须满足：不包含真实手机号、邮箱、客户域名、内部报价、未公开专家资料、真实 API 返回原文、私有运营结论。

## 3. 不能推送

### 密钥与运行时配置

- `.env`
- `.env.local`
- `.env.production`
- 任意包含真实 API Key、DeepSeek/OpenAI/Embedding Key、JWT secret、数据库密码、MinIO 密钥、Neo4j 密码的文件。
- 后台系统设置表导出的真实配置。

### 数据库与运行数据

- PostgreSQL 数据卷或 dump。
- Redis 数据。
- Qdrant 向量库数据。
- Neo4j 图谱数据。
- MinIO 对象存储数据。
- Celery beat 本地调度状态。
- 本地爬虫抓取的 HTML、截图、对象存储 key、诊断原始页面。

对应路径或文件类型包括但不限于：

- `pg_data/`
- `redis_data/`
- `qdrant_data/`
- `neo4j_data/`
- `minio_data/`
- `backend/celerybeat-schedule`
- `*.db`
- `*.sqlite`
- `*.dump`
- `*.sql`
- `*.backup`

### 私有内容资产

以下内容默认不推送真实版本：

- 专家频道真实专家数据。
- 教程频道真实教程正文、案例、图表、封面图。
- 公司库真实公司数据、评分、审核状态、关联知识库。
- 问答历史、用户问题、AI 回答、推荐结果。
- 方案生成历史、客户目标、竞品、团队资源和约束。
- 拓词词包、商业指数、推荐指数和行业词库。
- 后台运营截图、验收截图、长任务过程产物。

当前需要重点注意：

- `dist/experts.html` 目前把专家画像直接写在静态 HTML 中；开源前必须替换为 demo 专家数据，或改为从公开样例 JSON 读取。
- `dist/tutorial.html`、`dist/js/tutorial.js`、`dist/images/tutorial/` 和 `docs/tutorial-wiki/` 可能包含教程频道内容资产；开源前必须决定是全部移出、替换为 demo、还是只保留少量公开样例。
- `backend/app/scripts/seed.py` 如果包含真实种子内容，开源前必须改成 demo seed。

### 本地验证与自动化产物

- `.longtask/`
- `test-results/`
- `playwright-report/`
- `coverage/`
- 本地截图、浏览器录制、调试日志。
- 临时导出文件，例如诊断报告、方案、词包、PDF/Word/Markdown 导出。

## 4. 推荐仓库分层

建议将 GEOrank 分成三类资产管理：

| 层级 | 位置 | 是否推送公开 GitHub | 说明 |
|---|---|---:|---|
| 开源代码层 | 当前仓库主代码 | 是 | 工程代码、配置模板、空数据结构、demo seed |
| 私有内容层 | 私有目录或私有仓库 | 否 | 专家库、教程库、案例、运营素材 |
| 运行数据层 | Docker volume / 数据库 / 对象存储 | 否 | 公司库、问答、诊断、向量、图谱、上传文件 |

长期建议：

- 把专家数据从 HTML 中抽离到 `data/public-samples/experts.sample.json` 和私有 `data/private/experts.json` 两套来源。
- 把教程正文从代码仓库中抽离为内容包；公开仓库只保留 3-5 篇 demo 教程。
- 后台内容管理保留功能代码，但不随代码仓库发布真实内容。
- 所有真实内容通过数据库导入、私有对象存储或私有内容仓库管理。

## 5. 推送前检查流程

每次准备推送 GitHub 前，按以下顺序执行。

### 5.1 查看工作树

```bash
git status --short --branch -uall
```

规则：

- 不使用 `git add .`。
- 只添加本次确认可公开的文件。
- 看到 `.env`、`.longtask/`、数据库 dump、真实内容目录时，立即停止。

### 5.2 检查敏感词

```bash
rg -n "sk-|api[_-]?key|secret|password|token|Authorization|Bearer|MINIO|NEO4J|POSTGRES|DEEPSEEK|OPENAI" \
  --glob '!node_modules/**' \
  --glob '!.git/**' \
  --glob '!pnpm-lock.yaml'
```

规则：

- `.env.example` 中只能出现占位变量，不能出现真实值。
- 后端测试可以使用假 key，但必须明显是 dummy/test/example。
- 如果命中真实 key，不允许提交；先换 key，再清理 git 历史。

### 5.3 检查私有内容

```bash
rg -n "手机号|客户|报价|合同|内部|私有|未公开|专家|教程|案例|词包|诊断报告" \
  dist docs backend apps packages \
  --glob '!node_modules/**'
```

规则：

- 命中不一定都是问题，但专家、教程、案例、词包相关内容必须人工确认是否可公开。
- 真实教程正文不进入公开仓库。
- 真实专家资料不进入公开仓库。

### 5.4 检查大文件与数据文件

```bash
find . -type f \
  \( -name '*.db' -o -name '*.sqlite' -o -name '*.dump' -o -name '*.sql' -o -name '*.backup' -o -name '*.csv' -o -name '*.xlsx' -o -name '*.jsonl' -o -name '*.parquet' \) \
  -not -path './node_modules/*' \
  -not -path './.git/*'
```

规则：

- 默认不提交数据文件。
- 如果需要公开样例数据，必须放在明确的 `sample` / `example` 路径，并在文件名中标明 `sample`。

### 5.5 跑基础校验

```bash
pnpm i18n:check
pnpm --filter web typecheck
pnpm --filter admin typecheck
```

如果后端相关代码发生变化，再运行：

```bash
cd backend
pytest
```

如果静态前台发生变化，再至少访问：

```bash
curl -I http://localhost:3009/
curl -I http://localhost:3009/experts
curl -I http://localhost:3009/tutorial
```

## 6. 第一次开源前必须处理

第一次公开 GitHub 前，不要直接推当前工作树，先完成以下事项：

1. 确认 License。
2. 确认 README 中的项目定位、部署方式和免责声明。
3. 把真实专家频道数据替换为 demo 数据，或从公开版本移除。
4. 把真实教程频道内容替换为 demo 教程，或从公开版本移除。
5. 确认 `docs/tutorial-wiki/` 是否作为私有内容，不公开则从公开提交中排除。
6. 确认 `dist/images/tutorial/` 是否包含私有图表和案例图片，不公开则替换。
7. 确认 `backend/app/scripts/seed.py` 不含真实种子数据。
8. 确认 `.env` 没有进入 git。
9. 确认 `backend/celerybeat-schedule` 从 git 跟踪中移除。
10. 确认 `.longtask/` 不进入 git。
11. 确认所有 API Key 已轮换过，历史中曾经出现过的 key 不能继续使用。
12. 用全新 clone 跑一次公开版启动流程。

## 7. 推荐提交方式

不要一次性把现有全部改动推上去。推荐分批：

1. `chore: prepare open source guardrails`
   - `.gitignore`
   - 推送规则文档
   - README 开源说明

2. `chore: publish sanitized project skeleton`
   - monorepo 结构
   - 后端模型和 API
   - 前后台基础页面
   - demo seed

3. `feat: add public demo pages`
   - 首页
   - 诊断
   - 问答
   - 方案
   - 拓词
   - 工具
   - 专家 demo
   - 教程 demo

4. `docs: add deployment and contribution guide`
   - 本地启动
   - 环境变量说明
   - 贡献规则
   - License

## 8. 推送执行口令

后续真正需要我推送时，请明确说：

```text
按照 docs/GitHub开源推送规则.md 执行开源推送检查，并准备 GitHub 推送。
```

收到后应先做检查，不直接 push。只有检查通过并确认提交范围后，才进行 commit / push。

## 9. 当前状态备注

截至 2026-06-04：

- 本仓库仍处于私有开发状态。
- 当前工作树包含大量历史迭代改动和未跟踪产物，不能直接作为开源提交。
- 专家频道已经存在于 `dist/experts.html`，但其中的数据应视为内容资产，公开前要样例化。
- 教程频道同时涉及 `dist/tutorial.html`、`dist/js/tutorial.js`、`dist/images/tutorial/`、`docs/tutorial-wiki/` 和数据库 `contents` 表，公开前要单独做内容边界审查。
- `.env` 已在 `.gitignore` 中，但仍需推送前扫描，不能只依赖 ignore。
