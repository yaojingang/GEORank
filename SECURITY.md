# Security Policy

请不要在公开 issue、discussion 或 Pull Request 中提交 API Key、数据库密码、用户数据、客户资料、诊断报告、问答记录或其他敏感信息。

安全问题、经核验的权利或隐私请求以及相关敏感证据，请提交到 [GitHub Private Vulnerability Reporting](https://github.com/yaojingang/GEORank/security/advisories/new)。仓库正式发布前必须启用 Private Vulnerability Reporting。公开 issue 只能填写受影响的 slug 或仓库路径与非敏感摘要，不得附上身份证明、私人联系方式或其他敏感证据。

维护者会先限制受影响内容的公开分发，再核验、修复并发布更新。涉及公开专家数据时，完整处理流程见 [DATA_LICENSE.md](DATA_LICENSE.md)。公开披露前，请给维护者合理时间确认、修复和发布更新。

公开仓库不包含生产密钥和真实运行数据。你在自托管 GEOrank 时，需要自行保护：

- `.env` 和后台系统设置中的密钥。
- 数据库、向量库、图谱数据库和对象存储。
- 用户上传文件和自定义首页资源。
- 第三方模型 API 的调用权限、额度和合规设置。
