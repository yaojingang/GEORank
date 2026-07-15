# GEOrank 2.0 规划文档

本目录用于承载 GEOrank 2.0 的整体重构方案、基线冻结、迁移编排、验收规则与风险控制。

目标不是一次性推倒重写，而是以“不破坏现有 UI 和业务逻辑”为前提，完成一轮长期可维护的架构升级。

文档索引：

1. `00-principles.md`
   重构原则、边界、默认执行规则。
2. `01-current-baseline.md`
   1.0 当前基线：页面、路由、业务域、数据层、任务层。
3. `02-target-architecture.md`
   2.0 目标架构、技术栈、目录结构与边界。
4. `03-ui-parity-and-acceptance.md`
   UI 保真规则、模块映射和验收标准。
5. `04-api-sdk-contract.md`
   FastAPI/OpenAPI 契约冻结与 SDK 生成规则。
6. `05-auth-and-session.md`
   2.0 鉴权、会话、浏览器绑定和后台统一登录方案。
7. `06-i18n-data-model.md`
   多语言数据模型、slug 规则、SEO 规则。
8. `07-cli-design.md`
   CLI 命令树与边界。
9. `08-migration-workstreams.md`
   分阶段迁移路线、目录改动范围、默认执行顺序。
10. `09-risk-rollback-and-governance.md`
    风险、回滚、切换条件与治理规则。

推荐阅读顺序：

1. `00-principles.md`
2. `01-current-baseline.md`
3. `02-target-architecture.md`
4. `08-migration-workstreams.md`
