"""
种子数据脚本 — 初始化示例公司、用户、公开教程
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

from app.core.database import async_session
from app.models.company import Company, PipelineStatus, PublishStatus
from app.models.user import User, UserRole
from app.models.content import Content, ContentType, ContentStatus


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
        "title": "GEO 基础检查清单",
        "slug": "geo-basic-checklist",
        "content_type": ContentType.TUTORIAL,
        "status": ContentStatus.PUBLISHED,
        "tags": ["入门"],
        "reading_time_minutes": 1,
        "markdown_body": """# GEO 基础检查清单

发布公开页面前，可以快速确认三项：

- 用一句话说明页面主题与适用对象。
- 给关键事实补充可验证的来源或更新时间。
- 检查标题、摘要与正文中的品牌名称是否一致。

完成后保存并预览页面，再从教程频道打开详情页确认排版。""",
    },
]


# ============================================================
# 执行函数
# ============================================================

async def seed():
    print("🌱 GEOrank 种子数据初始化开始...")
    print("  · 需要数据库已完成 Alembic 迁移（docker compose run --rm migrate）")

    async with async_session() as db:
        from sqlalchemy import select

        # 1. 创建用户
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

        # 2. 创建公司
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

        # 3. 创建公开教程
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
