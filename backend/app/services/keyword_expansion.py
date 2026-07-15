"""
拓词服务
- 先推断关键词背后的业务画像
- 再按画像生成 8 维拓词结果
- AI 失败或输出不匹配时回退到画像化模板
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import re

from app.services.ai_client import ai_client

DIMENSIONS = [
    {"key": "semantic", "name": "语义拓展", "icon": "hub", "description": "同义词、相关术语、长尾变体"},
    {"key": "scenario", "name": "场景覆盖", "icon": "category", "description": "使用场景、上下文、应用情境"},
    {"key": "commercial", "name": "商业意图", "icon": "shopping_cart", "description": "购买信号、比较、定价查询"},
    {"key": "ranking", "name": "推荐榜单", "icon": "emoji_events", "description": "最佳、推荐、Top 类查询"},
    {"key": "review", "name": "产品评测", "icon": "rate_review", "description": "评测、对比、优缺点查询"},
    {"key": "brand", "name": "品牌关联", "icon": "business", "description": "品牌名、产品名、替代方案"},
    {"key": "question", "name": "问答长尾", "icon": "help", "description": "如何、怎么、为什么类查询"},
    {"key": "technical", "name": "技术方案", "icon": "engineering", "description": "部署、集成、API、架构类查询"},
]

DIMENSION_MAP = {item["key"]: item for item in DIMENSIONS}

PROFILE_LIBRARY = {
    "enterprise_service": {
        "name": "企业服务",
        "company_hint": "提供“{seed}”相关软件、咨询或服务的企业",
        "business_model": "偏 B2B / 企业服务 / 解决方案导向",
        "target_users": ["企业负责人", "市场团队", "增长团队", "内容团队"],
        "keyword_strategy": "优先覆盖服务采购、方案对比、团队场景和实施决策。",
        "blocked_terms": [],
        "templates": {
            "semantic": ["{s}", "{s}平台", "{s}工具", "{s}解决方案", "智能{s}", "企业级{s}", "{s}优化", "{s}系统", "{s}服务", "{s}引擎"],
            "scenario": ["B2B {s}", "企业 {s}", "品牌 {s}", "SaaS {s}", "增长场景 {s}", "AI 搜索场景 {s}", "内容团队 {s}", "市场部 {s}", "官网 {s}", "咨询场景 {s}"],
            "commercial": ["{s}价格", "{s}服务报价", "{s}多少钱", "{s}采购指南", "{s}试用", "{s}哪个好", "{s}对比价格", "{s}实施费用", "{s}方案报价", "{s}预算"],
            "ranking": ["最佳{s}", "{s}推荐", "{s}排行榜", "{s}Top10", "{s}服务商推荐", "国产{s}推荐", "{s}榜单", "{s}哪家好", "{s}头部厂商", "{s}优选"],
            "review": ["{s}评测", "{s}对比", "{s}优缺点", "{s}测评", "{s}案例分析", "{s}实测", "{s}口碑", "{s}选型", "{s}体验", "{s}使用感受"],
            "brand": ["{s}品牌", "{s}服务商", "{s}厂商", "{s}公司", "{s}竞品", "{s}替代方案", "{s}官网", "{s}产品矩阵", "{s}合作伙伴", "{s}生态"],
            "question": ["什么是{s}", "如何做{s}", "{s}怎么用", "为什么要做{s}", "{s}有效吗", "{s}适合谁", "{s}有哪些步骤", "{s}如何落地", "{s}有哪些误区", "{s}怎么评估"],
            "technical": ["{s} API", "{s}部署方案", "{s}集成", "{s}技术架构", "{s}数据结构", "{s}工作流", "{s}自动化", "{s}系统设计", "{s}对接", "{s}实施方案"],
        },
    },
    "consumer_education": {
        "name": "教育培训",
        "company_hint": "提供“{seed}”相关课程、辅导或教学服务的教育机构",
        "business_model": "偏 C 端教育服务 / 课程销售 / 家长决策",
        "target_users": ["学生", "家长", "老师", "教培机构运营者"],
        "keyword_strategy": "优先覆盖提分场景、家长决策、课程对比和机构口碑。",
        "blocked_terms": ["b2b", "saas", "市场部", "内容团队", "增长团队", "企业级"],
        "templates": {
            "semantic": ["{s}", "在线{s}", "一对一{s}", "{s}课程", "{s}机构", "{s}老师", "{s}培训", "{s}提分", "{s}家教", "{s}班"],
            "scenario": ["学生 {s}", "家长找{s}", "线上{s}", "小初高 {s}", "培优场景 {s}", "提分场景 {s}", "考前冲刺 {s}", "寒暑假 {s}", "升学场景 {s}", "校内同步 {s}"],
            "commercial": ["{s}价格", "{s}收费", "{s}哪家好", "{s}机构推荐", "{s}老师推荐", "{s}试听", "{s}课程报价", "{s}报名", "{s}怎么选", "{s}排名"],
            "ranking": ["最佳{s}", "{s}机构推荐", "{s}老师推荐", "{s}平台推荐", "口碑好的{s}", "{s}排行榜", "本地{s}推荐", "线上{s}推荐", "{s}优选", "{s}哪家强"],
            "review": ["{s}机构评测", "{s}平台对比", "{s}课程测评", "{s}优缺点", "{s}体验", "{s}口碑", "{s}家长评价", "{s}实测", "{s}效果怎么样", "{s}值不值"],
            "brand": ["{s}机构", "{s}老师", "{s}课程品牌", "{s}培训机构", "{s}学习平台", "{s}替代课程", "{s}品牌", "{s}官网", "{s}名师", "{s}教材"],
            "question": ["什么是{s}", "{s}适合谁", "{s}怎么选", "{s}怎么上课", "{s}有效吗", "{s}多少钱", "{s}和家教区别", "{s}有哪些方式", "{s}如何提分", "{s}多久见效"],
            "technical": ["{s}课程体系", "{s}教学方案", "{s}题库", "{s}学习计划", "{s}直播课", "{s}录播课", "{s}课后练习", "{s}测评系统", "{s}班型设计", "{s}教学工具"],
        },
    },
    "local_service": {
        "name": "本地服务",
        "company_hint": "提供“{seed}”相关上门、到店或同城服务的本地商家",
        "business_model": "偏本地线索转化 / 到店或上门服务",
        "target_users": ["本地居民", "家庭用户", "附近需求用户"],
        "keyword_strategy": "优先覆盖同城、附近、预约、价格和门店口碑。",
        "blocked_terms": ["b2b", "saas", "市场部", "内容团队", "增长团队"],
        "templates": {
            "semantic": ["{s}", "同城{s}", "上门{s}", "{s}服务", "{s}预约", "{s}方案", "{s}门店", "{s}师傅", "{s}公司", "{s}平台"],
            "scenario": ["附近{s}", "家庭 {s}", "同城 {s}", "周末 {s}", "急单 {s}", "预约 {s}", "到店 {s}", "上门场景 {s}", "本地生活 {s}", "门店 {s}"],
            "commercial": ["{s}价格", "{s}收费", "{s}多少钱", "{s}预约", "{s}报价", "{s}哪家好", "{s}服务电话", "{s}优惠", "{s}套餐", "{s}附近推荐"],
            "ranking": ["同城{s}推荐", "{s}排行榜", "附近{s}哪家好", "{s}优选", "{s}口碑榜", "{s}门店推荐", "{s}服务商推荐", "{s}品牌推荐", "{s}Top10", "本地{s}推荐"],
            "review": ["{s}测评", "{s}对比", "{s}口碑", "{s}评价", "{s}体验", "{s}值不值", "{s}优缺点", "{s}实测", "{s}案例", "{s}避坑"],
            "brand": ["{s}门店", "{s}公司", "{s}品牌", "{s}服务商", "{s}官网", "{s}预约平台", "{s}替代商家", "{s}附近门店", "{s}加盟", "{s}联系电话"],
            "question": ["{s}怎么预约", "{s}多少钱", "{s}多久上门", "{s}适合谁", "{s}怎么选", "{s}有哪些流程", "{s}靠谱吗", "{s}注意什么", "{s}有哪些坑", "{s}哪里找"],
            "technical": ["{s}流程", "{s}服务标准", "{s}预约系统", "{s}门店管理", "{s}工单", "{s}售后方案", "{s}服务清单", "{s}操作规范", "{s}服务时效", "{s}实施步骤"],
        },
    },
    "ecommerce_brand": {
        "name": "电商品牌",
        "company_hint": "围绕“{seed}”进行销售或种草转化的品牌与电商业务",
        "business_model": "偏品牌电商 / 渠道转化 / 内容种草",
        "target_users": ["消费者", "品牌团队", "电商运营"],
        "keyword_strategy": "优先覆盖种草、转化、比价、榜单和平台场景。",
        "blocked_terms": ["b2b", "市场部", "内容团队"],
        "templates": {
            "semantic": ["{s}", "{s}品牌", "{s}产品", "{s}套装", "{s}旗舰店", "{s}好物", "{s}平替", "{s}推荐", "{s}测评", "{s}使用感受"],
            "scenario": ["电商 {s}", "直播间 {s}", "小红书 {s}", "抖音 {s}", "新品 {s}", "种草场景 {s}", "礼物场景 {s}", "节日场景 {s}", "复购场景 {s}", "达人推荐 {s}"],
            "commercial": ["{s}价格", "{s}多少钱", "{s}优惠", "{s}折扣", "{s}购买渠道", "{s}旗舰店", "{s}哪家便宜", "{s}怎么选", "{s}礼盒", "{s}返场"],
            "ranking": ["{s}推荐", "{s}排行榜", "最佳{s}", "{s}哪款好", "{s}榜单", "{s}平替推荐", "{s}热门款", "{s}Top10", "{s}口碑榜", "{s}优选"],
            "review": ["{s}评测", "{s}测评", "{s}开箱", "{s}对比", "{s}使用体验", "{s}真实评价", "{s}值不值", "{s}优缺点", "{s}效果", "{s}购买建议"],
            "brand": ["{s}品牌", "{s}旗舰店", "{s}官网", "{s}系列", "{s}竞品", "{s}替代款", "{s}联名", "{s}口碑", "{s}品牌故事", "{s}热卖款"],
            "question": ["{s}值得买吗", "{s}适合谁", "{s}怎么选", "{s}和竞品区别", "{s}哪个系列好", "{s}在哪里买", "{s}怎么用", "{s}会回购吗", "{s}适合什么场景", "{s}有哪些坑"],
            "technical": ["{s}成分", "{s}规格", "{s}材质", "{s}使用方法", "{s}搭配方案", "{s}开箱", "{s}渠道策略", "{s}内容打法", "{s}商品结构", "{s}评价体系"],
        },
    },
    "content_media": {
        "name": "内容媒体",
        "company_hint": "围绕“{seed}”做内容创作、分发或知识付费的媒体或个人 IP",
        "business_model": "偏内容生产 / 广告或知识付费 / 社群增长",
        "target_users": ["内容创作者", "媒体团队", "知识付费用户"],
        "keyword_strategy": "优先覆盖选题、分发、涨粉、变现和内容策略。",
        "blocked_terms": ["b2b", "saas"],
        "templates": {
            "semantic": ["{s}", "{s}内容", "{s}选题", "{s}创作", "{s}栏目", "{s}账号", "{s}方法论", "{s}教程", "{s}案例", "{s}增长"],
            "scenario": ["公众号 {s}", "短视频 {s}", "小红书 {s}", "知识付费 {s}", "个人IP {s}", "涨粉场景 {s}", "社群场景 {s}", "品牌内容 {s}", "内容运营 {s}", "分发场景 {s}"],
            "commercial": ["{s}报价", "{s}合作", "{s}投放", "{s}怎么变现", "{s}接单", "{s}课程价格", "{s}社群收费", "{s}赞助", "{s}账号报价", "{s}服务价格"],
            "ranking": ["{s}推荐", "{s}榜单", "最佳{s}", "{s}优选", "{s}排行榜", "{s}热门账号", "{s}创作者推荐", "{s}课程推荐", "{s}案例推荐", "{s}资源推荐"],
            "review": ["{s}测评", "{s}拆解", "{s}对比", "{s}复盘", "{s}口碑", "{s}值不值", "{s}案例分析", "{s}优缺点", "{s}体验", "{s}使用感受"],
            "brand": ["{s}账号", "{s}品牌", "{s}作者", "{s}课程", "{s}栏目", "{s}社群", "{s}替代方案", "{s}官网", "{s}工作室", "{s}IP"],
            "question": ["如何做{s}", "{s}怎么起号", "{s}怎么变现", "{s}怎么选题", "{s}适合谁", "{s}怎么运营", "{s}如何涨粉", "{s}有哪些坑", "{s}怎么持续输出", "{s}值得做吗"],
            "technical": ["{s}选题流程", "{s}内容结构", "{s}分发策略", "{s}工作流", "{s}排期", "{s}脚本模板", "{s}素材库", "{s}社群转化", "{s}账号定位", "{s}增长模型"],
        },
    },
}

PROFILE_RULES = [
    ("consumer_education", ["教育", "培训", "课程", "辅导", "数学", "英语", "家教", "提分", "考研", "高考", "留学", "题库", "老师", "小初高"]),
    ("local_service", ["家政", "搬家", "装修", "维修", "保洁", "摄影", "婚礼", "月嫂", "开锁", "搬运", "鲜花", "宠物", "律师", "牙科"]),
    ("ecommerce_brand", ["电商", "护肤", "美妆", "服饰", "鞋", "箱包", "食品", "咖啡", "母婴", "礼盒", "面膜", "香水", "零食", "品牌"]),
    ("content_media", ["公众号", "短视频", "小红书", "内容创作", "知识付费", "个人ip", "自媒体", "课程博主", "社群", "涨粉", "选题"]),
    ("enterprise_service", ["saas", "crm", "api", "ai", "geo", "seo", "服务商", "平台", "系统", "解决方案", "营销", "增长", "运营", "企业", "咨询", "官网优化"]),
]


def normalize_seeds(seeds: list[str]) -> list[str]:
    normalized: list[str] = []
    seen = set()
    for item in seeds:
        text = re.sub(r"\s+", " ", str(item or "").strip())
        if not text or text in seen:
            continue
        normalized.append(text[:40])
        seen.add(text)
        if len(normalized) >= 8:
            break
    return normalized


def _stable_score(seed: str, dimension_key: str, keyword: str, base: int, spread: int) -> int:
    digest = hashlib.md5(f"{seed}|{dimension_key}|{keyword}".encode("utf-8")).hexdigest()
    return max(35, min(99, base + (int(digest[:8], 16) % spread)))


def _infer_keyword_profile(seeds: list[str]) -> dict:
    combined = " ".join(seeds).lower()
    scores = {key: 0 for key in PROFILE_LIBRARY}
    for profile_key, markers in PROFILE_RULES:
        for marker in markers:
            if marker in combined:
                scores[profile_key] += 1

    profile_key = max(scores.items(), key=lambda item: item[1])[0]
    if scores[profile_key] == 0:
        profile_key = "enterprise_service"

    profile = PROFILE_LIBRARY[profile_key]
    primary_seed = seeds[0]
    return {
        "key": profile_key,
        "name": profile["name"],
        "company_hint": profile["company_hint"].format(seed=primary_seed),
        "business_model": profile["business_model"],
        "target_users": profile["target_users"],
        "keyword_strategy": profile["keyword_strategy"],
        "blocked_terms": profile.get("blocked_terms", []),
    }


def _templates_for(profile_key: str, dimension_key: str) -> list[str]:
    profile = PROFILE_LIBRARY.get(profile_key, PROFILE_LIBRARY["enterprise_service"])
    return profile["templates"].get(dimension_key) or PROFILE_LIBRARY["enterprise_service"]["templates"][dimension_key]


def _is_keyword_allowed(profile: dict, keyword: str) -> bool:
    lowered = keyword.lower()
    for token in profile.get("blocked_terms", []):
        if token in lowered:
            return False
    return True


def _fallback_item(seed: str, dimension_key: str, keyword: str) -> dict:
    recommendation_base = {
        "semantic": 62,
        "scenario": 60,
        "commercial": 58,
        "ranking": 64,
        "review": 61,
        "brand": 63,
        "question": 59,
        "technical": 57,
    }[dimension_key]
    business_base = {
        "semantic": 54,
        "scenario": 60,
        "commercial": 72,
        "ranking": 68,
        "review": 63,
        "brand": 66,
        "question": 52,
        "technical": 58,
    }[dimension_key]
    return {
        "keyword": keyword,
        "recommendation_score": _stable_score(seed, dimension_key, keyword, recommendation_base, 28),
        "business_score": _stable_score(seed, f"{dimension_key}-biz", keyword, business_base, 26),
        "reason": None,
    }


def _fallback_dimension_items(seed: str, profile: dict, dimension_key: str, limit: int = 10) -> list[dict]:
    items: list[dict] = []
    seen = set()
    for template in _templates_for(profile["key"], dimension_key):
        keyword = template.replace("{s}", seed).strip()
        if not keyword or keyword in seen or not _is_keyword_allowed(profile, keyword):
            continue
        seen.add(keyword)
        items.append(_fallback_item(seed, dimension_key, keyword))
        if len(items) >= limit:
            break
    return items


def _fallback_expand(seeds: list[str], profile: dict) -> list[dict]:
    merged: dict[str, list[dict]] = {item["key"]: [] for item in DIMENSIONS}
    seen: dict[str, set[str]] = {item["key"]: set() for item in DIMENSIONS}
    for seed in seeds:
        for dim in DIMENSIONS:
            key = dim["key"]
            for item in _fallback_dimension_items(seed, profile, key):
                keyword = item["keyword"]
                if keyword in seen[key]:
                    continue
                merged[key].append(item)
                seen[key].add(keyword)
                if len(merged[key]) >= 10:
                    break
    return [
        {
            **dim,
            "count": len(merged[dim["key"]]),
            "items": merged[dim["key"]][:10],
        }
        for dim in DIMENSIONS
    ]


def _sanitize_dimension_items(seed: str, dimension_key: str, raw_items: list[dict], profile: dict) -> list[dict]:
    items: list[dict] = []
    seen = set()
    for raw in raw_items or []:
        keyword = re.sub(r"\s+", " ", str(raw.get("keyword") or raw.get("kw") or "").strip())
        if not keyword or keyword in seen or not _is_keyword_allowed(profile, keyword):
            continue
        seen.add(keyword)
        try:
            recommendation = int(raw.get("recommendation_score", raw.get("rec", 0)))
        except Exception:
            recommendation = 0
        try:
            business = int(raw.get("business_score", raw.get("biz", 0)))
        except Exception:
            business = 0
        recommendation = max(35, min(99, recommendation or _stable_score(seed, dimension_key, keyword, 60, 28)))
        business = max(35, min(99, business or _stable_score(seed, f"{dimension_key}-biz", keyword, 58, 26)))
        items.append(
            {
                "keyword": keyword[:80],
                "recommendation_score": recommendation,
                "business_score": business,
                "reason": str(raw.get("reason") or "").strip()[:120] or None,
            }
        )
        if len(items) >= 10:
            break
    return items


async def _ai_expand(seeds: list[str], profile: dict, provider_override=None) -> list[dict]:
    system = """你是 GEO 关键词策略专家。你会先理解种子词背后的业务画像，再按画像输出 8 个维度的关键词词包。严格返回 JSON：
{
  "dimensions": [
    {
      "key": "semantic|scenario|commercial|ranking|review|brand|question|technical",
      "items": [
        {
          "keyword": "关键词",
          "recommendation_score": 0-100整数,
          "business_score": 0-100整数,
          "reason": "简短原因"
        }
      ]
    }
  ]
}
规则：
1. 每个维度输出 8-10 个词。
2. 先遵守给定业务画像，再生成词包。
3. 如果画像明显偏 C 端教育/本地服务/内容创作，就不要输出 B2B、SaaS、市场部等不匹配表达。
4. recommendation_score 表示该词适合用于 GEO 推荐与被 AI 引用的潜力。
5. business_score 表示商业转化和采购/转化意图强度。
6. 关键词必须自然、真实、中文为主，不要堆砌符号。
7. 不要输出解释文字，只返回 JSON。"""

    user = json.dumps(
        {
            "seeds": seeds,
            "profile": {
                "name": profile["name"],
                "company_hint": profile["company_hint"],
                "business_model": profile["business_model"],
                "target_users": profile["target_users"],
                "keyword_strategy": profile["keyword_strategy"],
                "blocked_terms": profile["blocked_terms"],
            },
            "dimensions": [
                {"key": item["key"], "name": item["name"], "description": item["description"]}
                for item in DIMENSIONS
            ],
        },
        ensure_ascii=False,
    )
    raw = await ai_client.complete(
        system,
        user,
        temperature=0.45,
        provider_override=provider_override,
    )
    start, end = raw.find("{"), raw.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError("AI 返回的拓词结果不是有效 JSON")
    payload = json.loads(raw[start:end])
    result: list[dict] = []
    mapping = {item.get("key"): item.get("items") for item in payload.get("dimensions", []) if isinstance(item, dict)}

    for dim in DIMENSIONS:
        items = _sanitize_dimension_items(seeds[0], dim["key"], mapping.get(dim["key"]) or [], profile)
        if not items:
            items = _fallback_dimension_items(seeds[0], profile, dim["key"])
        if not items:
            raise ValueError(f"维度 {dim['key']} 没有生成有效关键词")
        result.append(
            {
                **dim,
                "count": len(items),
                "items": items,
            }
        )
    return result


def _build_summary(dimensions: list[dict]) -> dict:
    all_items = [item for dim in dimensions for item in dim["items"]]
    total = len(all_items)
    if not total:
        return {
            "total_keywords": 0,
            "average_recommendation_score": 0,
            "average_business_score": 0,
            "high_recommendation_ratio": 0,
            "high_business_ratio": 0,
        }
    avg_rec = round(sum(item["recommendation_score"] for item in all_items) / total)
    avg_biz = round(sum(item["business_score"] for item in all_items) / total)
    high_rec = round(sum(1 for item in all_items if item["recommendation_score"] >= 80) / total * 100)
    high_biz = round(sum(1 for item in all_items if item["business_score"] >= 80) / total * 100)
    return {
        "total_keywords": total,
        "average_recommendation_score": avg_rec,
        "average_business_score": avg_biz,
        "high_recommendation_ratio": high_rec,
        "high_business_ratio": high_biz,
    }


async def expand_keywords(seeds: list[str], provider_override=None) -> dict:
    normalized = normalize_seeds(seeds)
    if not normalized:
        raise ValueError("请至少输入一个关键词")

    profile = _infer_keyword_profile(normalized)

    try:
        dimensions = await asyncio.wait_for(
            _ai_expand(normalized, profile, provider_override=provider_override),
            timeout=8.0,
        )
    except Exception:
        if provider_override is not None:
            raise
        dimensions = _fallback_expand(normalized, profile)

    return {
        "seeds": normalized,
        "profile": {
            "name": profile["name"],
            "company_hint": profile["company_hint"],
            "business_model": profile["business_model"],
            "target_users": profile["target_users"],
            "keyword_strategy": profile["keyword_strategy"],
        },
        "dimensions": dimensions,
        "summary": _build_summary(dimensions),
    }
