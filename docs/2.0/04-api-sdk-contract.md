# 04. API 契约与 SDK

## 原则

FastAPI 是 2.0 的唯一契约源。

所有调用方：

- `apps/web`
- `apps/admin`
- `cli`

都应基于统一契约工作。

## 后端要求

### 路由规范

- `operationId` 唯一且稳定
- `response_model` 明确
- 错误结构统一
- 分页结构统一

### 契约冻结范围

优先冻结：

- auth
- companies
- diagnostics
- solutions
- content
- keywords
- admin
- settings

## SDK 生成

流程：

1. 导出 `/openapi.json`
2. 保存到 `packages/api-sdk/openapi.json`
3. 使用 `@hey-api/openapi-ts` 生成
4. 在 `packages/api-sdk/src/client.ts` 包装统一 client

## 统一 client 规范

client 必须支持：

- base URL
- locale header
- auth header / cookie
- 错误规范化
- SSR 请求和浏览器请求分层

## 禁止项

2.0 页面中禁止：

- 页面内部直接硬编码 API URL
- 页面内部散落大量手写 fetch
- 页面内部自行解析各种不统一错误结构
