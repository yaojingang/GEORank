# GEOrank 2.0 前台切换状态

## 当前目标

把 2.0 前台逐步接管当前公开站点，不改变现有业务逻辑，不破坏公开 URL 和 SEO/GEO 输出。

## 已完成

### 公开页面

- 首页：`apps/web/app/[locale]/page.tsx`
- 教程频道：`apps/web/app/[locale]/tutorial/page.tsx`
- 教程详情：`apps/web/app/[locale]/tutorial/[slug]/page.tsx`
- 公司详情：`apps/web/app/[locale]/companies/[slug]/page.tsx`
- 登录：`apps/web/app/[locale]/login/page.tsx`
- 注册：`apps/web/app/[locale]/register/page.tsx`
- 诊断工具页：`apps/web/app/[locale]/diagnostic/page.tsx`
- 诊断报告详情：`apps/web/app/[locale]/diagnostic/reports/[id]/page.tsx`
- 方案页：`apps/web/app/[locale]/solutions/page.tsx`
- 方案会话详情：`apps/web/app/[locale]/solutions/conversations/[id]/page.tsx`
- 拓词页：`apps/web/app/[locale]/keywords/page.tsx`

### 路由与链接层

- 默认中文 locale 改为无前缀输出。
- 非默认 locale 继续保留显式前缀。
- 公共站内链接统一改为 `localizeHref()` 生成。
- canonical 与 OpenGraph URL 已对齐默认中文无前缀规则。

### 组件与页面保真

- 2.0 教程页保留频道树、上下篇导航、SSR 正文输出。
- 2.0 公司详情保留企业快照、信号矩阵、相似公司等结构化模块。
- 2.0 诊断、方案、拓词工作台已接入真实现有能力，不再是静态占位。

## 当前切换策略

不是一次性把旧前台删掉，而是按以下顺序切换：

1. 先让 2.0 页面具备完整公开路由能力。
2. 再让默认中文路径和旧站路径保持一致。
3. 再逐页把旧 Nginx/静态入口切到新 `apps/web`。
4. 保留旧路径兼容层，保证外链、SEO 与历史页面不失效。

## 下一步切换顺序

### 第一批

- `/`
- `/tutorial`
- `/tutorial/:slug`
- `/c/:slug` 或公司详情正式短链
- `/login`
- `/register`

### 第二批

- `/diagnostic`
- `/diagnostic/reports/:id`
- `/solutions`
- `/solutions/conversations/:id`
- `/keywords`

## 当前阻塞点

- 旧前台仍由静态 `dist/` + Nginx 主导。
- 新前台已具备页面和路由能力，但还没有接管生产入口。
- 公司短链与 2.0 Next 路由还需要统一一层正式映射。

## 切换验收标准

### 页面保真

- 现有 UI 的信息结构和核心视觉不明显走样。

### 业务保真

- 登录、诊断、方案、拓词、教程、公司详情的原有业务行为保持一致。

### SEO/GEO 保真

- SSR 正文继续输出。
- canonical 正确。
- 默认中文不再带 locale 前缀。
- 非默认语言保留独立路径。

### 回滚保真

- 切换后如果发现公开页异常，能快速切回旧静态入口。
