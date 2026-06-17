# 06. 多语言数据模型

## 原则

多语言不能只做前端文案翻译，必须从内容模型开始设计。

## 路由规则

统一使用 locale 路由：

- `/zh-CN/...`
- `/en-US/...`

## 数据表建议

### `locales`

- `code`
- `name`
- `is_default`

### `content_translations`

- `content_id`
- `locale`
- `title`
- `slug`
- `summary`
- `markdown_body`
- `html_body`
- `seo_title`
- `seo_description`

### `company_translations`

- `company_id`
- `locale`
- `name`
- `short_description`
- `description`
- `seo_title`
- `seo_description`

## slug 规则

- slug 在 locale 维度唯一
- 不做全局唯一
- 公开详情页按 locale 输出 canonical

## SEO 规则

每个 locale 独立输出：

- title
- description
- open graph
- `hreflang`
- localized schema
