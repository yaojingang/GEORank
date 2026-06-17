# 05. 鉴权与会话设计

## 目标

建立一个适合长期扩展的统一会话体系，覆盖：

- 前台
- 后台
- 浏览器绑定
- 多语言
- 后续 CLI 与自动化

## 登录方式

第一阶段继续保留：

- 手机号 + 密码

## 会话设计

### Access Token

- 短时效
- 用于 API 访问

### Refresh Token

- `httpOnly`
- `secure`
- `sameSite=lax`
- 服务端可撤销

### 浏览器绑定

规则：

- 一个浏览器默认绑定一个手机号
- 注册后绑定
- 后续登录如果使用不同手机号则提示阻止

## 后端需要新增

- `auth_devices`
- `auth_sessions`

## 前端需要新增

- session provider
- route guard
- auth modal
- login/register page

## 后台统一

后台不再使用独立逻辑拼接 token，而是共享 2.0 认证体系。
