# Contributing to GEOrank

感谢你关注 GEOrank。这个项目仍处于早期开源阶段，欢迎围绕 GEO 诊断规则、前台体验、后台管理、AI 工具、部署文档和 demo 数据提交改进。

Canonical repository: <https://github.com/yaojingang/GEORank>

提交前请确认：

- 不包含真实 API Key、token、密码或生产配置。
- 不包含真实客户数据、用户问答、诊断记录、方案历史或数据库导出。
- 不包含未经授权的专家资料、教程正文、图片、案例或商业数据。
- 新增功能尽量提供可复现说明或测试。

建议流程：

1. Fork 仓库。
2. 创建功能分支。
3. 提交改动并说明问题背景。
4. 运行相关检查。
5. 发起 Pull Request。

常用检查：

```bash
pnpm i18n:check
pnpm --filter @georank/web typecheck
pnpm --filter @georank/admin typecheck
```

如果修改后端，请补充运行：

```bash
cd backend
python -m tests.run
```
