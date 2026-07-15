"""同步前台专家资料到可管理数据源

Revision ID: 012_seed_expert_profiles
Revises: 011_add_homepage_releases
Create Date: 2026-07-12
"""

from datetime import datetime
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "012_seed_expert_profiles"
down_revision = "011_add_homepage_releases"
branch_labels = None
depends_on = None


SEED_DATE = datetime(2026, 6, 17)
EXPERT_SEEDS = [
    {
        "id": uuid.UUID("2dfd3c38-5c50-4e89-8a64-6be1db151e74"),
        "slug": "yao-jingang",
        "display_name": "姚金刚",
        "avatar_initials": "姚",
        "title": "GEO 专家 / AI创业者 / AI营销",
        "category": "methodology",
        "specialty_label": "GEO 方法论",
        "summary": "GEO 专家 / AI创业者 / AI营销，第一届 GEO 大会发起者，《AI营销：从SEO到GEO》作者，GEOFlow 开源项目发起人。",
        "consultation": "\n\n".join([
            "姚金刚是国内较早系统推动 GEO 研究、开源与行业交流的实践者，发起并成功举办中国第一届 GEO 大会，创立国内第一批 GEO 公司，并推动国内早期 GEO 行业标准与方法论建设。",
            "他是 GEO 书籍《AI营销：从SEO到GEO》作者，开源 GEO 项目 GEOFlow 已获得 2.5k star，并免费开源 17 套 GEO Skill。",
            "他发布《GEO白皮书》《GEO蓝皮书》《GEO红皮书》，累计超过 40 万字，访问量超过 10 万，持续把 GEO 研究成果开放给行业。",
            "他发布 GEO 论文《From Citation Selection to Citation Absorption: A Measurement Framework for Generative Engine Optimization Across AI Search Platforms》，围绕 AI 搜索平台的引用选择与引用吸收建立测量框架。",
            "他也是 WaytoAGI 的 GEO 公开课发起者，每月免费分享 GEO 公开课，曾在知名上市公司、独角兽公司任职营销高管。",
        ]),
        "expertise": [
            "发起并成功举办中国第一届 GEO 大会",
            "GEO 书籍《AI营销：从SEO到GEO》作者",
            "开源 GEO 项目 GEOFlow，已获得 2.5k star",
            "发布《GEO白皮书》《GEO蓝皮书》《GEO红皮书》，累计超过 40 万字，访问量超 10 万",
            "免费开源 17 套 GEO Skill",
            "发布 arXiv GEO 论文，提出跨 AI 搜索平台测量框架",
            "WaytoAGI 的 GEO 公开课发起者",
            "创立国内第一批 GEO 公司",
            "曾在知名上市公司、独角兽公司任职营销高管",
        ],
        "keywords": ["GEO 大会", "GEOFlow", "GEO 开源", "GEO 文档", "AI 营销"],
        "sort_order": 1,
        "is_featured": True,
        "is_published": True,
    },
    {
        "id": uuid.UUID("6d47d829-1ab7-4664-bc10-ca617fc5e209"),
        "slug": "qiao-xiangyang",
        "display_name": "乔向阳",
        "avatar_initials": "乔",
        "title": "AI 产品经理 / AI 自媒体 / 独立开发者 / AI 营销与 GEO 实践者",
        "category": "ai-workflow",
        "specialty_label": "AI 工作流",
        "summary": "中文 AI 圈中具有代表性的实践型内容创作者，擅长把 AI 前沿信息转化为普通产品经理、创作者、创业者和营销人可理解、可上手的工具判断与工作流方案。",
        "consultation": "\n\n".join([
            "乔向阳，是中文 AI 圈中具有代表性的实践型内容创作者，核心定位是“AI 产品经理、AI 自媒体、独立开发者、AI 营销与 GEO 实践者”。他曾任字节跳动 / TikTok 商业化 AI 产品经理，也有连续创业、SEO 增长和产品实战背景，主理公众号“向阳乔木推荐看”、X 账号 @vista8、个人站 qiaomu.ai，并在 GitHub 以 @joeseesun 发布多个 AI 工作流项目。",
            "他的内容特点在于把 AI 前沿信息转化为普通产品经理、创作者、创业者和营销人可以理解、可以上手的工具判断与工作流方案。2022 年 ChatGPT 3.5 出现后，他开始密集跟踪 OpenAI、Anthropic、Google、xAI、AI Agent、AI 编程、AI 搜索等方向，并通过 X、公众号、博客和社群持续输出。",
            "乔向阳的主要内容包括 AI 工具与模型实测、AI 编程、独立开发、GEO 与 AI 营销、AI 教育和工作坊。他关注 Codex、Claude、Raycast AI、NotebookLM、Gemini、Sora、即梦、Suno 等工具，并强调工具之间如何组成高效工作流。",
            "在实践层面，他的 GitHub 项目覆盖内容处理、NotebookLM 资料生成、OpenCLI 技能、AI 海报设计、知识网站生成等方向。其中 qiaomu-anything-to-notebooklm、qiaomu-opencli-skills 等项目体现了他把 AI 工具产品化、流程化的能力。",
            "在商业化方向，他参与 GEO 白皮书、GEO 大会，并与姚金刚一起出版 GEO 书籍《AI营销：从SEO到GEO》，把传统 SEO 经验延伸到 AI 搜索时代，关注品牌如何被大模型理解、引用和推荐。",
        ]),
        "expertise": [
            "发起并成功举办中国第一届 GEO 大会",
            "GEO 书籍《AI营销：从SEO到GEO》作者",
            "曾任字节跳动 / TikTok 商业化 AI 产品经理",
            "持续跟踪 OpenAI、Anthropic、Google、xAI、AI Agent、AI 编程和 AI 搜索",
            "擅长 AI 工具实测、AI 编程、独立开发、GEO 与 AI 营销",
            "GitHub 项目覆盖内容处理、NotebookLM 资料生成、OpenCLI 技能、AI 海报设计和知识网站生成",
            "发布 GEO 白皮书并发起中国第一届GEO 大会",
        ],
        "keywords": ["AI 产品经理", "AI 工作流", "AI 营销", "GEO 实践", "独立开发"],
        "sort_order": 2,
        "is_featured": True,
        "is_published": True,
    },
    {
        "id": uuid.UUID("1c48a8fb-5d1b-408f-8f71-533c7d72f14b"),
        "slug": "fu-wei",
        "display_name": "夫唯",
        "avatar_initials": "夫",
        "title": "搜外创始人 / 搜索营销与 GEO 实操专家",
        "category": "seo-practice",
        "specialty_label": "SEO/GEO",
        "summary": "本名黄凤华，SEOWHY 搜外创始人，深耕系统化 SEO 教学，行业进入 AI 时代后转向谷歌出海 SEO 与 GEO 生成引擎优化研究。",
        "consultation": "\n\n".join([
            "夫唯，本名黄凤华，国内知名搜索营销专家、SEOWHY 搜外创始人。2008 年创办搜外平台，深耕系统化 SEO 教学，累计培育学员四万余人，大批从业者任职于各类电商与互联网企业，是国内 SEO 行业标杆级导师。",
            "行业迈入 AI 时代后，夫唯重心转向谷歌出海 SEO 与 GEO 生成引擎优化研究，独创搜外派 GEO 落地体系。",
            "该体系立足传统实业与中小工厂实际经营视角，摒弃高额投入玩法，主打低成本落地、长效稳定运营，贴合中小制造企业推广需求，现已成为制造业落地 GEO 普及率最高的实操方法论。",
            "多年行业沉淀，让其打通传统搜索与 AI 智能推荐两套流量逻辑，持续为实体工厂输出适配工业化场景的全域营销方案。",
        ]),
        "expertise": [
            "SEOWHY 搜外创始人",
            "2008 年创办搜外平台",
            "累计培育 SEO 学员四万余人",
            "独创搜外派 GEO 落地体系",
            "聚焦传统实业、中小工厂、谷歌出海 SEO 与 GEO 落地",
        ],
        "keywords": ["搜外", "出海 SEO", "中小制造", "低成本 GEO", "实操方法论"],
        "sort_order": 3,
        "is_featured": True,
        "is_published": True,
    },
    {
        "id": uuid.UUID("d64f0081-0ce7-490c-950d-3385240e9ba9"),
        "slug": "guangtou-niuge",
        "display_name": "光头牛哥",
        "avatar_initials": "牛",
        "title": "AI GEO 全域优化专家 / 搜索营销实战专家",
        "category": "traffic-growth",
        "specialty_label": "流量增长",
        "summary": "本名冷洪利，国内资深搜索营销专家、AI GEO 全域优化领军人物，长期深耕 SEO、出海电商 SEO 与豆包生态 GEO 运营。",
        "consultation": "\n\n".join([
            "光头牛哥，本名冷洪利，国内资深搜索营销专家、AI GEO 全域优化领军人物，SEO 牛人网、抖音头部 GEO IP 曝光率 GEO 创始人。",
            "2010 年创立 SEO 牛人网，依托扎实的技术功底，平台核心关键词百度 SEO 排名连续三年稳居行业第三位，成为国内早期搜索营销领域标杆平台，影响了大批行业从业者。",
            "为深耕一线实战、打磨落地方法论，他后续主导列表网、筑龙网等大型互联网平台流量搭建，成功打造百万 IP 稳定流量体系，落地 1800 万关键词排名经典案例，深度吃透传统搜索引擎流量底层逻辑。",
            "伴随 AI 浪潮全面到来，冷洪利率先布局 GEO 生成引擎优化赛道，同步深耕出海电商 SEO 与豆包生态 GEO 运营两大方向。他深度拆解 GEO 算法规则、内容架构、流量分发、品牌引用与商业投放逻辑，结合二十余年搜索营销实战积淀，重构行业投放模型。",
            "基于海量一线落地经验，他先后编撰推出《出海电商 SEO+GEO 爆量获客实操手册》《豆包 7 日获客实操手册》《豆包 GEO 百问百答》三本行业实战著作，内容摒弃空洞理论，全流程拆解落地玩法，免费对外开放分享。",
            "现阶段，冷洪利聚焦服务大型连锁企业与上市公司，围绕出海 SEO、豆包 GEO 全域布局、内容资产搭建、可信信源打造和投放策略规划，提供一体化解决方案。",
        ]),
        "expertise": [
            "2010 年创立 SEO 牛人网",
            "主导列表网、筑龙网等大型平台流量搭建",
            "打造百万 IP 稳定流量体系",
            "落地 1800 万关键词排名案例",
            "深耕出海电商 SEO 与豆包生态 GEO 运营",
            "编撰三本 GEO 与 AI 获客实操资料",
            "服务大型连锁企业与上市公司",
        ],
        "keywords": ["豆包 GEO", "出海 SEO", "全域优化", "流量体系", "企业获客"],
        "sort_order": 4,
        "is_featured": True,
        "is_published": True,
    },
    {
        "id": uuid.UUID("03fe3229-fd68-48d4-9464-e2c4d727f381"),
        "slug": "zhang-kai",
        "display_name": "张凯",
        "avatar_initials": "张",
        "title": "海外 GEO 专家 / 企业培训顾问 / AI 应用开发者",
        "category": "overseas",
        "specialty_label": "出海 GEO",
        "summary": "连续创业者、企业培训顾问、AI 应用开发者、海外 GEO 专家，曾服务多家世界 500 强企业数字营销培训项目。",
        "consultation": "\n\n".join([
            "张凯是连续创业者、企业培训顾问、AI 应用开发者、海外 GEO 专家。",
            "作为企业培训顾问期间，他曾服务过腾讯、字节、欧莱雅、蒙牛、上汽、达能等全球 500 强企业关于数字营销领域方向的培训项目。",
            "作为 AI 应用开发者，他曾大量完成各种类型的 AI 应用项目，覆盖 AI 基建、教育培训、营销领域等多个方向。",
            "作为海外 GEO 专家，他任 frevana.com 中国区负责人、flickbloom.com 合伙人、arXiv GEO 相关文章一作，参与服务多家出海企业的 GEO 相关服务，帮助合作伙伴组建 GEO 团队并赋能业务。",
        ]),
        "expertise": [
            "连续创业者",
            "企业培训顾问，服务过腾讯、字节、欧莱雅、蒙牛、上汽、达能等企业培训项目",
            "AI 应用开发者，覆盖 AI 基建、教育培训、营销等方向",
            "frevana.com 中国区负责人",
            "flickbloom.com 合伙人",
            "arXiv GEO 相关文章一作",
            "参与服务多家出海企业 GEO 项目",
        ],
        "keywords": ["海外 GEO", "企业培训", "AI 应用", "出海企业", "frevana"],
        "sort_order": 5,
        "is_featured": True,
        "is_published": True,
    },
]


def _expert_profiles_table():
    return sa.table(
        "expert_profiles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("slug", sa.String(length=120)),
        sa.column("display_name", sa.String(length=120)),
        sa.column("avatar_initials", sa.String(length=12)),
        sa.column("title", sa.String(length=160)),
        sa.column("category", sa.String(length=50)),
        sa.column("specialty_label", sa.String(length=50)),
        sa.column("summary", sa.Text()),
        sa.column("expertise", postgresql.JSONB()),
        sa.column("consultation", sa.Text()),
        sa.column("keywords", postgresql.JSONB()),
        sa.column("sort_order", sa.Integer()),
        sa.column("is_featured", sa.Boolean()),
        sa.column("is_published", sa.Boolean()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )


def upgrade() -> None:
    op.add_column("expert_profiles", sa.Column("slug", sa.String(length=120), nullable=True))
    op.create_unique_constraint("uq_expert_profiles_slug", "expert_profiles", ["slug"])

    expert_profiles = _expert_profiles_table()
    connection = op.get_bind()
    for seed in EXPERT_SEEDS:
        values = {**seed, "created_at": SEED_DATE, "updated_at": SEED_DATE}
        statement = postgresql.insert(expert_profiles).values(**values)
        connection.execute(statement.on_conflict_do_nothing(index_elements=["slug"]))


def downgrade() -> None:
    expert_profiles = _expert_profiles_table()
    seeded_rows = [
        sa.and_(
            expert_profiles.c.id == seed["id"],
            expert_profiles.c.slug == seed["slug"],
        )
        for seed in EXPERT_SEEDS
    ]
    op.get_bind().execute(
        expert_profiles.delete().where(sa.or_(*seeded_rows))
    )
    op.drop_constraint("uq_expert_profiles_slug", "expert_profiles", type_="unique")
    op.drop_column("expert_profiles", "slug")
