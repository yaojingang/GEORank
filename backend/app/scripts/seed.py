"""
种子数据脚本 — 初始化示例公司、用户、Wiki 文章
运行方式: python -m app.scripts.seed
数据基于真实的 GEO 领域公司信息整理而来
"""
import asyncio
import sys
import os
import secrets
import string

# 确保可以 import app 模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import date, datetime
import bcrypt

from app.core.database import engine, Base, async_session
from app.models.company import Company, PipelineStatus, PublishStatus
from app.models.user import User, UserRole
from app.models.content import Content, ContentType, ContentStatus
import app.models  # noqa: F401 确保所有模型加载


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _random_seed_password(length: int = 18) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


ADMIN_SEED_PASSWORD = os.getenv("GEORANK_SEED_ADMIN_PASSWORD") or _random_seed_password()
DEMO_SEED_PASSWORD = os.getenv("GEORANK_SEED_DEMO_PASSWORD") or _random_seed_password()
TEST_SEED_PASSWORD = os.getenv("GEORANK_SEED_TEST_PASSWORD") or _random_seed_password()


# ============================================================
# 种子数据定义
# ============================================================

SEED_USERS = [
    {
        "email": "admin@georank.com",
        "username": "admin",
        "password": ADMIN_SEED_PASSWORD,
        "role": UserRole.ADMIN,
        "is_active": True,
        "is_verified": True,
    },
    {
        "email": "demo@neuralpath.ai",
        "username": "zhang_yuanhang",
        "password": DEMO_SEED_PASSWORD,
        "role": UserRole.ENTERPRISE,
        "is_active": True,
        "is_verified": True,
    },
    {
        "email": "test@georank.com",
        "username": "test_user",
        "password": TEST_SEED_PASSWORD,
        "role": UserRole.USER,
        "is_active": True,
        "is_verified": False,
    },
]

SEED_COMPANIES = [
    {
        "name": "Perplexity AI",
        "url": "https://www.perplexity.ai",
        "short_description": "对话式 AI 搜索引擎，直接生成答案并附带实时引用来源，是 GEO 从业者的核心目标平台之一。",
        "description": """Perplexity AI 是一家基于大型语言模型的对话式搜索引擎公司，成立于 2022 年，总部位于美国旧金山。
其核心产品能够将用户的自然语言问题转化为结构化答案，并实时引用网络权威来源。
对于 GEO 从业者而言，Perplexity 是除 ChatGPT 之外最重要的内容曝光渠道，其引用逻辑偏向权威性强、结构化清晰的内容页面。
Perplexity 的 Pro 版本（$20/月）支持文件上传、图像生成和 API 访问，已获得红杉资本、英伟达、贝佐斯等知名机构的投资。""",
        "category": "AI搜索",
        "tags": ["AI搜索", "LLM", "GEO目标平台", "引用优化"],
        "funding_stage": "C轮",
        "geo_score": 96.5,
        "geo_details": {
            "schema": 95,
            "content": 97,
            "meta": 96,
            "citation": 98,
        },
        "tech_level": "L5 级语义映射",
        "is_geo_certified": True,
        "founded_date": date(2022, 8, 1),
        "headquarters": "美国·旧金山",
        "employee_count": "200-500人",
        "pipeline_status": PipelineStatus.COMPLETED,
        "publish_status": PublishStatus.PUBLISHED,
        "upvotes": 342,
        "tech_stack": ["GPT-4o", "Claude 3.5", "Mistral", "Bing Index", "SerpAPI"],
        "team_members": [
            {"name": "Aravind Srinivas", "role": "CEO & Co-founder", "bg": "OpenAI / DeepMind"},
            {"name": "Denis Yarats", "role": "CTO & Co-founder", "bg": "Facebook AI Research"},
        ],
    },
    {
        "name": "BrightEdge",
        "url": "https://www.brightedge.com",
        "short_description": "企业级 SEO 与 GEO 数据智能平台，提供 AI 搜索可见度监控与内容优化建议。",
        "description": """BrightEdge 成立于 2007 年，是全球领先的 SEO 数据智能平台，近年来率先将 GEO（生成式引擎优化）纳入核心能力体系。
其 DataCube 引擎每天处理超过 10 亿关键词的搜索数据，并通过 AI 分析帮助企业发现内容在 ChatGPT、Perplexity、Gemini 等 AI 搜索中的曝光缺口。
平台的 Generative Parser™ 能够追踪品牌在 LLM 生成答案中的引用频率，是目前市场上 GEO 监控能力最完整的商业工具之一。
服务客户包括微软、麦当劳、Capital One 等全球 500 强企业。""",
        "category": "GEO工具",
        "tags": ["GEO监控", "SEO平台", "内容优化", "企业级"],
        "funding_stage": "已盈利",
        "geo_score": 88.2,
        "geo_details": {
            "schema": 91,
            "content": 87,
            "meta": 89,
            "citation": 86,
        },
        "tech_level": "L4 级结构化数据",
        "is_geo_certified": True,
        "founded_date": date(2007, 3, 1),
        "headquarters": "美国·圣马特奥",
        "employee_count": "500-1000人",
        "pipeline_status": PipelineStatus.COMPLETED,
        "publish_status": PublishStatus.PUBLISHED,
        "upvotes": 218,
        "tech_stack": ["DataCube", "Generative Parser", "S3", "Elasticsearch"],
        "team_members": [
            {"name": "Jim Yu", "role": "CEO & Co-founder"},
            {"name": "Brad Mattick", "role": "VP of Marketing"},
        ],
    },
    {
        "name": "Conductor",
        "url": "https://www.conductor.com",
        "short_description": "面向营销团队的内容智能平台，新增 GEO 可见度追踪功能，监测品牌在 AI 答案中的出现频率。",
        "description": """Conductor 是一家以内容营销为核心的智能平台，2023 年被 WeWork 剥离后独立运营，并在 2024 年快速布局 GEO 能力。
其 Lighthouse 功能能够追踪品牌关键词在 ChatGPT、Gemini、Perplexity 等主要 AI 搜索引擎中的引用情况，并提供竞品对比分析。
平台内置超过 200 个 SEO/GEO 指标模板，支持与 Google Search Console、HubSpot、Salesforce 等工具深度集成。
适合中大型企业的内容团队和 SEO 从业者使用。""",
        "category": "GEO工具",
        "tags": ["内容营销", "GEO监控", "AI可见度", "B2B"],
        "funding_stage": "独立运营",
        "geo_score": 79.4,
        "geo_details": {
            "schema": 78,
            "content": 82,
            "meta": 77,
            "citation": 81,
        },
        "tech_level": "L3 级语义增强",
        "is_geo_certified": False,
        "founded_date": date(2010, 1, 1),
        "headquarters": "美国·纽约",
        "employee_count": "200-500人",
        "pipeline_status": PipelineStatus.COMPLETED,
        "publish_status": PublishStatus.PUBLISHED,
        "upvotes": 143,
        "tech_stack": ["Lighthouse Engine", "NLP Pipeline", "Google GSC API"],
        "team_members": [
            {"name": "Seth Besmertnik", "role": "CEO"},
        ],
    },
    {
        "name": "Goodie",
        "url": "https://goodie.ai",
        "short_description": "专注于品牌在 AI 搜索答案中的知名度提升，通过结构化内容优化帮助网站被 LLM 引用。",
        "description": """Goodie 是 2024 年成立的 GEO 原生创业公司，专注于帮助品牌优化其内容被 AI 生成引擎引用的概率。
其核心方法论基于「Answer Engine Optimization（AEO）」框架：
1. 分析目标关键词在 ChatGPT/Perplexity 中的典型答案结构
2. 重构客户网站内容以匹配 LLM 的引用偏好（FAQ 结构、权威来源链接、Schema 标记）
3. 监测引用率变化并持续迭代
Goodie 已服务超过 150 家 DTC 品牌和 SaaS 公司，平均在 90 天内将品牌 AI 可见度提升 3-5 倍。""",
        "category": "GEO咨询",
        "tags": ["AEO", "品牌AI可见度", "内容重构", "初创"],
        "funding_stage": "天使轮",
        "geo_score": 72.1,
        "geo_details": {
            "schema": 68,
            "content": 75,
            "meta": 71,
            "citation": 74,
        },
        "tech_level": "L3 级语义增强",
        "is_geo_certified": False,
        "founded_date": date(2024, 3, 1),
        "headquarters": "美国·旧金山",
        "employee_count": "10-50人",
        "pipeline_status": PipelineStatus.COMPLETED,
        "publish_status": PublishStatus.PUBLISHED,
        "upvotes": 89,
        "tech_stack": ["OpenAI API", "Firecrawl", "Ahrefs API"],
        "team_members": [],
    },
    {
        "name": "Narrato",
        "url": "https://narrato.io",
        "short_description": "AI 内容工作流平台，内置 GEO 优化建议，帮助内容团队生产更易被 AI 引擎引用的结构化文章。",
        "description": """Narrato 是一个面向内容团队的 AI 写作与工作流协作平台，2024 年新增 GEO Score 功能。
用户在撰写文章时，平台实时分析内容与 LLM 引用偏好的匹配度，并给出具体的优化建议：
- 是否需要增加 FAQ 部分
- H2/H3 标题是否覆盖了目标关键词的语义变体
- 外链权威性是否达标
- 开头段落是否直接回答了核心问题（Answer Box 优化）
Narrato 目前在 G2 内容营销工具类别中排名前三，月活跃团队超过 2000 个。""",
        "category": "AI写作",
        "tags": ["AI写作", "内容工作流", "GEO Score", "团队协作"],
        "funding_stage": "种子轮",
        "geo_score": 65.8,
        "geo_details": {
            "schema": 60,
            "content": 70,
            "meta": 65,
            "citation": 69,
        },
        "tech_level": "L2 级内容丰富",
        "is_geo_certified": False,
        "founded_date": date(2020, 6, 1),
        "headquarters": "印度·班加罗尔",
        "employee_count": "50-200人",
        "pipeline_status": PipelineStatus.COMPLETED,
        "publish_status": PublishStatus.PUBLISHED,
        "upvotes": 67,
        "tech_stack": ["GPT-4o", "Claude", "Grammarly API", "Notion API"],
        "team_members": [
            {"name": "Asavari Sharma", "role": "Co-founder & CEO"},
        ],
    },
    {
        "name": "Aily Labs",
        "url": "https://www.ailylabs.com",
        "short_description": "企业 AI 决策智能平台，通过知识图谱构建和语义化数据层优化企业内容在 LLM 中的可发现性。",
        "description": """Aily Labs 成立于 2022 年，总部位于德国慕尼黑，专注于为大型企业构建 AI 决策智能层。
其核心产品通过构建企业专属知识图谱，将非结构化的内部数据（报告、手册、产品规格）转化为结构化语义层，
从而使企业内容在 LLM 查询中具备更强的可检索性和引用置信度。
这与 GEO 的核心目标高度对齐：让 AI 引擎「认识」并「信任」你的品牌知识体系。
已服务宝马、西门子等 DAX 上市公司，B 轮融资 4500 万欧元。""",
        "category": "知识图谱",
        "tags": ["知识图谱", "企业AI", "语义数据", "GEO基础设施"],
        "funding_stage": "B轮",
        "geo_score": 83.7,
        "geo_details": {
            "schema": 88,
            "content": 82,
            "meta": 80,
            "citation": 85,
        },
        "tech_level": "L4 级结构化数据",
        "is_geo_certified": True,
        "founded_date": date(2022, 1, 1),
        "headquarters": "德国·慕尼黑",
        "employee_count": "50-200人",
        "pipeline_status": PipelineStatus.COMPLETED,
        "publish_status": PublishStatus.PUBLISHED,
        "upvotes": 156,
        "tech_stack": ["Neo4j", "GPT-4o", "Databricks", "Azure OpenAI"],
        "team_members": [
            {"name": "Alexander Filipov", "role": "CEO & Co-founder"},
            {"name": "Iliya Valchev", "role": "CTO & Co-founder"},
        ],
    },
]

SEED_CONTENTS = [
    {
        "title": "什么是 GEO？生成式引擎优化完全指南",
        "slug": "what-is-geo",
        "content_type": ContentType.TUTORIAL,
        "status": ContentStatus.PUBLISHED,
        "tags": ["核心概念"],
        "reading_time_minutes": 8,
        "markdown_body": """# 什么是 GEO？生成式引擎优化完全指南

## 定义

**GEO（Generative Engine Optimization，生成式引擎优化）** 是指通过优化网站内容、结构和权威性，使品牌和产品更容易出现在 AI 生成的答案中的系列方法论。

与传统 SEO 优化「在搜索结果页排名靠前」不同，GEO 的目标是让 AI 引擎（如 ChatGPT、Perplexity、Gemini、SearchGPT）在回答用户问题时**主动引用和推荐**你的品牌。

## 为什么 GEO 越来越重要？

- **AI 搜索流量爆炸式增长**：Perplexity 月活已突破 1 亿，ChatGPT 每天处理超过 1 亿次对话中有大量搜索意图
- **零点击搜索加剧**：AI 直接在答案中解决问题，用户不再点击蓝色链接
- **传统 SEO 失效区间扩大**：Google 的 AI Overview 让 Top 10 排名的流量价值大幅缩水

## GEO 的五大核心维度

### 1. Schema 结构化数据

AI 引擎偏爱语义明确的内容。通过添加 `ld+json` 格式的 Schema.org 标记，可以帮助 LLM 理解你的内容类型。

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "什么是 GEO？",
  "author": {"@type": "Person", "name": "GEOrank 编辑团队"},
  "datePublished": "2026-04-07"
}
</script>
```

### 2. 权威引用密度

在内容中引用权威来源（学术论文、行业报告、政府数据）可以显著提高 LLM 的引用置信度。

### 3. FAQ 结构

大多数 LLM 在生成答案时会优先参考 FAQ 格式的内容，因为它直接匹配问答模式。

### 4. 开篇直接回答（BLUF 原则）

Bottom Line Up Front：开篇段落直接给出核心答案，避免铺垫。

### 5. 实体丰富度

在内容中明确提及相关的人物、产品、公司、地点实体，有助于 LLM 建立知识关联。

## 与 SEO 的核心区别

| 维度 | SEO | GEO |
|------|-----|-----|
| 目标 | 搜索结果页排名 | AI 答案中被引用 |
| 核心信号 | 链接权重 / 关键词密度 | 内容权威性 / 结构化程度 |
| 评估工具 | Google Search Console | AI 可见度监控工具 |
| 优化周期 | 3-6 个月 | 2-8 周 |

## 如何开始实施 GEO？

1. **诊断现状**：使用 GEOrank 诊断工具分析你的网站 GEO 健康度
2. **优先处理 Schema**：这是见效最快的优化项
3. **重构核心页面**：将产品页、About 页改写为 FAQ + 结构化格式
4. **监控引用率**：追踪品牌关键词在主要 AI 引擎中的出现频率
""",
    },
    {
        "title": "Schema.org 实战：让 AI 读懂你的网站",
        "slug": "schema-org-guide",
        "content_type": ContentType.TUTORIAL,
        "status": ContentStatus.PUBLISHED,
        "tags": ["核心概念"],
        "reading_time_minutes": 6,
        "markdown_body": """# Schema.org 实战：让 AI 读懂你的网站

## 为什么 Schema 对 GEO 至关重要？

LLM 在爬取和理解网页时，会优先解析 `<head>` 中的结构化数据。Schema.org 提供了一套标准词汇表，
帮助 AI 引擎准确理解你的内容类型、作者、发布时间和核心主张。

## 最重要的 5 种 Schema 类型

### 1. Article / BlogPosting

适用于所有内容型页面：

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "文章标题",
  "description": "一句话摘要（150字以内）",
  "author": {
    "@type": "Person",
    "name": "作者名",
    "url": "https://example.com/author"
  },
  "publisher": {
    "@type": "Organization",
    "name": "发布机构"
  },
  "datePublished": "2026-04-07",
  "dateModified": "2026-04-07"
}
```

### 2. FAQPage

FAQ Schema 是 GEO 优化中最有价值的标记，直接对应 LLM 的问答引用模式：

```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "什么是 GEO？",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "GEO 是指优化网站内容使其出现在 AI 生成答案中的方法论。"
      }
    }
  ]
}
```

### 3. Organization

适用于公司首页和 About 页：

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "公司名称",
  "url": "https://example.com",
  "description": "公司一句话描述",
  "foundingDate": "2022",
  "sameAs": [
    "https://www.linkedin.com/company/xxx",
    "https://twitter.com/xxx"
  ]
}
```

## 验证工具

- **Google Rich Results Test**：验证 Schema 语法正确性
- **Schema.org Validator**：完整性校验
- **GEOrank 诊断工具**：评估 Schema 对 GEO 的贡献度

## 常见错误

1. `datePublished` 缺失（LLM 无法判断内容时效性）
2. `author` 只写名字不提供 URL（降低权威性信号）
3. FAQ 答案超过 300 字（LLM 引用时会截断）
""",
    },
    {
        "title": "GEO 内容写作框架：让 AI 优先引用你的内容",
        "slug": "geo-content-writing-framework",
        "content_type": ContentType.TUTORIAL,
        "status": ContentStatus.PUBLISHED,
        "tags": ["内容优化"],
        "reading_time_minutes": 10,
        "markdown_body": """# GEO 内容写作框架：让 AI 优先引用你的内容

## 核心原则：像 AI 一样思考内容结构

LLM 在生成答案时遵循一套可预测的内容偏好模式。理解这些模式，就能有针对性地重构你的内容。

## CLEAR 框架

**C - Concise（精炼）**：开篇段直接给出核心答案，不超过 3 句话

**L - Linked（关联权威）**：每个重要论点引用至少一个外部权威来源

**E - Evidence-based（证据支撑）**：用数据、案例、研究替代主观判断

**A - Answer-first（答案优先）**：每个 H2 段落的第一句即为本段核心结论

**R - Rich（语义丰富）**：段落中包含相关实体（人名、品牌、地点、日期）

## 内容结构模板

```
# [核心问题/关键词]

[开篇：2-3 句话直接回答核心问题]

## 核心定义

[定义 + 与相关概念的区别]

## 为什么重要（数据支撑）

- 数据点 1（来源：XXX 报告，2026年）
- 数据点 2
- 数据点 3

## 实施步骤

### 步骤一：[动作]

[具体说明，100-200字]

### 步骤二：[动作]

...

## 常见问题 FAQ

**Q: [问题1]?**
A: [直接回答，50-100字]

**Q: [问题2]?**
A: [直接回答，50-100字]

## 延伸阅读

- [权威来源1]
- [权威来源2]
```

## 针对不同 AI 引擎的优化差异

| AI 引擎 | 内容偏好 | 特别注意 |
|--------|---------|---------|
| Perplexity | 实时性强、来源透明 | 确保 `dateModified` 是近期 |
| ChatGPT | 深度解释、示例丰富 | 代码块和结构化列表效果好 |
| Gemini | Google 生态内容 | 与 Google Search Console 数据保持一致 |
| Claude | 平衡性、多角度 | 避免过度宣传语气 |
""",
    },
    {
        "title": "如何监测品牌在 AI 搜索中的可见度？",
        "slug": "monitor-ai-visibility",
        "content_type": ContentType.TUTORIAL,
        "status": ContentStatus.PUBLISHED,
        "tags": ["工具与监测"],
        "reading_time_minutes": 5,
        "markdown_body": """# 如何监测品牌在 AI 搜索中的可见度？

## GEO 监测的核心指标

与传统 SEO 使用「排名」和「流量」不同，GEO 监测关注以下核心指标：

### 1. AI 引用频率（Citation Rate）
在目标关键词触发的 AI 答案中，你的品牌被引用的百分比。

### 2. 引用位置（Citation Position）
在 AI 答案中，你的内容被引用在第几位（越靠前越好）。

### 3. 答案覆盖率（Answer Coverage）
你的内容覆盖了目标关键词所有问题变体的比例。

### 4. 实体提及率（Entity Mention Rate）
在不含引用链接的纯文字 AI 回答中，你的品牌名被主动提及的频率。

## 主流监测工具

### 商业工具（付费）

| 工具 | 特点 | 适合 |
|------|------|------|
| BrightEdge | 数据最全，追踪 5 个主流 AI 引擎 | 大型企业 |
| Conductor | 与 SEO 工作流深度集成 | 中型企业内容团队 |
| Semrush AI Toolkit | 价格适中，功能快速迭代 | 中小型企业 |

### 自建监测方案（低成本）

1. 创建 Google Sheet，列出 50-100 个核心关键词
2. 每周在 Perplexity / ChatGPT 中手动查询
3. 记录是否引用你的网站、引用位置、引用文字
4. 用趋势图追踪变化

## 建立监测基线

在实施任何 GEO 优化之前，先建立 **28 天基线数据**：
- 选择 30 个最重要的目标关键词
- 记录当前 AI 引用频率
- 记录竞品的引用频率
- 确定优先优化方向（差距最大的领域）

这样才能在优化后用数据证明 GEO 投入的价值。
""",
    },
]


# ============================================================
# 执行函数
# ============================================================

async def seed():
    print("🌱 GEOrank 种子数据初始化开始...")

    # 1. 建表（幂等）
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  ✓ 数据库表结构就绪")

    async with async_session() as db:
        from sqlalchemy import select

        # 2. 创建用户
        admin_user = None
        for user_data in SEED_USERS:
            result = await db.execute(select(User).where(User.email == user_data["email"]))
            existing = result.scalar_one_or_none()
            if existing:
                if user_data["role"] == UserRole.ADMIN:
                    admin_user = existing
                print(f"  · 用户已存在，跳过: {user_data['email']}")
                continue

            user = User(
                email=user_data["email"],
                username=user_data["username"],
                hashed_password=_hash(user_data["password"]),
                role=user_data["role"],
                is_active=user_data["is_active"],
                is_verified=user_data["is_verified"],
            )
            db.add(user)
            await db.flush()
            if user_data["role"] == UserRole.ADMIN:
                admin_user = user
            print(f"  ✓ 创建用户: {user_data['email']} [{user_data['role'].value}]")

        await db.commit()

        # 3. 创建公司
        for company_data in SEED_COMPANIES:
            result = await db.execute(select(Company).where(Company.url == company_data["url"]))
            if result.scalar_one_or_none():
                print(f"  · 公司已存在，跳过: {company_data['name']}")
                continue

            company = Company(
                name=company_data["name"],
                url=company_data["url"],
                short_description=company_data["short_description"],
                description=company_data["description"],
                category=company_data["category"],
                tags=company_data["tags"],
                funding_stage=company_data["funding_stage"],
                geo_score=company_data["geo_score"],
                geo_details=company_data["geo_details"],
                tech_level=company_data["tech_level"],
                is_geo_certified=company_data["is_geo_certified"],
                founded_date=company_data["founded_date"],
                headquarters=company_data["headquarters"],
                employee_count=company_data["employee_count"],
                pipeline_status=company_data["pipeline_status"],
                publish_status=company_data["publish_status"],
                upvotes=company_data["upvotes"],
                tech_stack=company_data.get("tech_stack", []),
                team_members=company_data.get("team_members", []),
                submitted_by=admin_user.id if admin_user else None,
            )
            db.add(company)
            print(f"  ✓ 创建公司: {company_data['name']} (GEO评分: {company_data['geo_score']})")

        await db.commit()

        # 4. 创建 Wiki 文章
        for content_data in SEED_CONTENTS:
            result = await db.execute(select(Content).where(Content.slug == content_data["slug"]))
            if result.scalar_one_or_none():
                print(f"  · 文章已存在，跳过: {content_data['slug']}")
                continue

            article = Content(
                title=content_data["title"],
                slug=content_data["slug"],
                content_type=content_data["content_type"],
                status=content_data["status"],
                markdown_body=content_data["markdown_body"],
                tags=content_data["tags"],
                reading_time_minutes=content_data["reading_time_minutes"],
                author_id=admin_user.id if admin_user else None,
            )
            db.add(article)
            print(f"  ✓ 创建文章: {content_data['title']}")

        await db.commit()

    print("\n✅ 种子数据初始化完成！")
    print("提示: 下方密码仅在首次创建用户时有效；如用户已存在，请使用现有密码或在后台重置。")
    print("\n管理员账号:")
    print("  邮箱: admin@georank.com")
    print(f"  密码: {ADMIN_SEED_PASSWORD}")
    print("\n演示账号:")
    print("  邮箱: demo@neuralpath.ai")
    print(f"  密码: {DEMO_SEED_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed())
