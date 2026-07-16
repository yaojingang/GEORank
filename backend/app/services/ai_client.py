"""
AI 客户端服务 — OpenAI API 调用封装
支持：LLM 生成 / Embedding / RAG 问答 / 流式输出
懒初始化 — 未配置 API Key 时不影响其他服务启动
"""
import json
import httpx
from typing import Optional, AsyncGenerator, Any
from app.core.config import settings
from app.services.runtime_settings import get_ai_runtime_config

DEFAULT_CHAT_MAX_TOKENS = 4096
ACTION_PLAN_MAX_TOKENS = 6000


class EmbeddingNotConfiguredError(ValueError):
    """Raised when no dedicated embedding provider is configured."""


class AIClient:
    """OpenAI API 封装，懒初始化"""

    def __init__(self):
        self._client = None
        self._embed_client = None
        self._codex_client = None
        self._provider_clients = {}
        self._client_signature = None
        self._embed_client_signature = None
        self._codex_client_signature = None
        self._provider_cursor = 0

    async def _get_client(self):
        config = await get_ai_runtime_config()
        signature = (config["llm_api_key"], config["llm_base_url"])
        if self._client is None or self._client_signature != signature:
            key = config["llm_api_key"]
            if not key:
                raise ValueError("LLM API Key 未配置，请在 .env 中填入 LLM_API_KEY 或在后台系统设置中配置 API Provider")
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(
                api_key=key,
                base_url=config["llm_base_url"] or None,
            )
            self._client_signature = signature
        return self._client

    async def _get_embed_client(self):
        """Embedding 使用独立 Client（可能是不同的 base_url / key）"""
        config = await get_ai_runtime_config()
        signature = (config["embedding_api_key"], config["embedding_base_url"])
        if self._embed_client is None or self._embed_client_signature != signature:
            key = config["embedding_api_key"]
            if not key:
                raise EmbeddingNotConfiguredError(
                    "Embedding API Key 未配置，请在 .env 中填入 EMBEDDING_API_KEY 或在后台系统设置中配置"
                )
            from openai import AsyncOpenAI
            # 如果配置了专用 Embedding base_url 则用它，否则用默认 OpenAI
            base_url = config["embedding_base_url"] or None
            self._embed_client = AsyncOpenAI(api_key=key, base_url=base_url)
            self._embed_client_signature = signature
        return self._embed_client

    async def _get_codex_client(self):
        """Codex / fallback 使用独立 Client（可配置独立 key/base_url）"""
        config = await get_ai_runtime_config()
        signature = (config["codex_api_key"], config["codex_base_url"])
        if self._codex_client is None or self._codex_client_signature != signature:
            key = config["codex_api_key"]
            if not key:
                raise ValueError("Codex API Key 未配置")
            from openai import AsyncOpenAI
            self._codex_client = AsyncOpenAI(
                api_key=key,
                base_url=config["codex_base_url"] or None,
            )
            self._codex_client_signature = signature
        return self._codex_client

    async def _get_provider_client(self, provider: dict):
        """多 LLM API Provider 使用独立 Client，按 provider id 缓存。"""
        provider_id = provider.get("id") or "provider"
        signature = (provider.get("api_key"), provider.get("base_url"))
        cached = self._provider_clients.get(provider_id)
        if cached and cached[0] == signature:
            return cached[1]
        key = provider.get("api_key")
        if not key:
            raise ValueError(f"{provider.get('name') or provider_id} API Key 未配置")
        from openai import AsyncOpenAI
        client = AsyncOpenAI(
            api_key=key,
            base_url=provider.get("base_url") or None,
        )
        self._provider_clients[provider_id] = (signature, client)
        return client

    async def _get_runtime_config(self):
        return await get_ai_runtime_config()

    async def reset_clients(self):
        self._client = None
        self._embed_client = None
        self._codex_client = None
        self._provider_clients = {}
        self._client_signature = None
        self._embed_client_signature = None
        self._codex_client_signature = None
        self._provider_cursor = 0

    @staticmethod
    def _is_blank_text(value: str | None) -> bool:
        return not isinstance(value, str) or not value.strip()

    @staticmethod
    def _extract_chat_content(payload: dict) -> str:
        choices = payload.get("choices") or []
        if not choices:
            return ""
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    chunks.append(item.get("text", ""))
                elif isinstance(item, str):
                    chunks.append(item)
            return "".join(chunks)
        return ""

    @staticmethod
    def _build_raw_chat_url(base_url: str | None) -> str:
        normalized = (base_url or "").rstrip("/")
        if not normalized:
            raise ValueError("Codex Base URL 未配置")
        return f"{normalized}/chat/completions"

    async def _raw_chat_complete(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int | None = None,
    ) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self._build_raw_chat_url(base_url),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        return self._extract_chat_content(body)

    def _build_chat_targets(self, config: dict, model: str | None = None) -> list[tuple[str, str]]:
        if model:
            return [("llm", model)]

        targets: list[tuple[str, str]] = []
        primary_model = config["llm_model"] or settings.OPENAI_MODEL
        if primary_model:
            targets.append(("llm", primary_model))

        fallback_model = config.get("llm_fallback_model") or config.get("codex_model")
        if fallback_model and fallback_model != primary_model:
            targets.append(("codex", fallback_model))
        return targets

    def _build_provider_targets(self, config: dict, model: str | None = None) -> list[dict]:
        providers = [
            dict(provider)
            for provider in (config.get("llm_providers") or [])
            if provider.get("enabled", True)
            and provider.get("api_key")
            and provider.get("base_url")
            and (provider.get("model") or model)
        ]
        if not providers:
            return []

        providers.sort(key=lambda item: (int(item.get("priority") or 999), item.get("id") or ""))
        if config.get("llm_provider_strategy") == "round_robin" and len(providers) > 1:
            start = self._provider_cursor % len(providers)
            self._provider_cursor += 1
            providers = providers[start:] + providers[:start]

        if model:
            providers = [{**provider, "model": model} for provider in providers]
        return providers

    async def _resolve_chat_client(self, slot: str):
        if slot == "codex":
            return await self._get_codex_client()
        return await self._get_client()

    async def _complete_with_fallback(
        self,
        messages: list[dict],
        *,
        temperature: float,
        model: str | None = None,
        max_tokens: int | None = None,
        provider_override: Any | None = None,
    ) -> str:
        if provider_override is not None:
            content = await self._raw_chat_complete(
                api_key=provider_override.api_key,
                base_url=provider_override.base_url,
                model=provider_override.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if self._is_blank_text(content):
                raise ValueError(f"{provider_override.model} 返回空内容")
            return content

        config = await self._get_runtime_config()
        errors: list[Exception] = []

        provider_targets = self._build_provider_targets(config, model)
        if provider_targets:
            for provider in provider_targets:
                target_model = provider["model"]
                try:
                    client = await self._get_provider_client(provider)
                    payload = {
                        "model": target_model,
                        "messages": messages,
                        "temperature": temperature,
                    }
                    if max_tokens is not None:
                        payload["max_tokens"] = max_tokens
                    response = await client.chat.completions.create(**payload)
                    content = response.choices[0].message.content or ""
                    if self._is_blank_text(content):
                        raise ValueError(f"{target_model} 返回空内容")
                    return content
                except Exception as exc:
                    errors.append(exc)

            if errors:
                raise errors[-1]

        for slot, target_model in self._build_chat_targets(config, model):
            try:
                if slot == "codex":
                    content = await self._raw_chat_complete(
                        api_key=config["codex_api_key"],
                        base_url=config["codex_base_url"],
                        model=target_model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                else:
                    client = await self._resolve_chat_client(slot)
                    payload = {
                        "model": target_model,
                        "messages": messages,
                        "temperature": temperature,
                    }
                    if max_tokens is not None:
                        payload["max_tokens"] = max_tokens
                    response = await client.chat.completions.create(**payload)
                    content = response.choices[0].message.content or ""
                if self._is_blank_text(content):
                    raise ValueError(f"{target_model} 返回空内容")
                return content
            except Exception as exc:
                errors.append(exc)

        if errors:
            raise errors[-1]
        raise ValueError("未配置可用的 LLM 模型")

    async def _stream_complete_with_fallback(
        self,
        messages: list[dict],
        *,
        temperature: float,
        model: str | None = None,
        max_tokens: int | None = None,
        provider_override: Any | None = None,
    ) -> AsyncGenerator[str, None]:
        if provider_override is not None:
            merged = await self._raw_chat_complete(
                api_key=provider_override.api_key,
                base_url=provider_override.base_url,
                model=provider_override.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if self._is_blank_text(merged):
                raise ValueError(f"{provider_override.model} 流式返回空内容")
            yield merged
            return

        config = await self._get_runtime_config()
        errors: list[Exception] = []

        provider_targets = self._build_provider_targets(config, model)
        if provider_targets:
            for provider in provider_targets:
                chunks: list[str] = []
                target_model = provider["model"]
                try:
                    client = await self._get_provider_client(provider)
                    payload = {
                        "model": target_model,
                        "messages": messages,
                        "temperature": temperature,
                        "stream": True,
                    }
                    if max_tokens is not None:
                        payload["max_tokens"] = max_tokens
                    stream = await client.chat.completions.create(**payload)
                    async for chunk in stream:
                        delta = chunk.choices[0].delta.content
                        if delta:
                            chunks.append(delta)
                    merged = "".join(chunks)
                    if self._is_blank_text(merged):
                        raise ValueError(f"{target_model} 流式返回空内容")
                    # The upstream stream has already completed and is buffered.
                    # Yield the merged reply once so a downstream SSE disconnect
                    # cannot leave accounting with only the first buffered chunk.
                    yield merged
                    return
                except Exception as exc:
                    errors.append(exc)

            if errors:
                raise errors[-1]

        for slot, target_model in self._build_chat_targets(config, model):
            chunks: list[str] = []
            try:
                if slot == "codex":
                    merged = await self._raw_chat_complete(
                        api_key=config["codex_api_key"],
                        base_url=config["codex_base_url"],
                        model=target_model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    if self._is_blank_text(merged):
                        raise ValueError(f"{target_model} 流式返回空内容")
                    yield merged
                    return
                else:
                    client = await self._resolve_chat_client(slot)
                    payload = {
                        "model": target_model,
                        "messages": messages,
                        "temperature": temperature,
                        "stream": True,
                    }
                    if max_tokens is not None:
                        payload["max_tokens"] = max_tokens
                    stream = await client.chat.completions.create(**payload)
                    async for chunk in stream:
                        delta = chunk.choices[0].delta.content
                        if delta:
                            chunks.append(delta)
                merged = "".join(chunks)
                if self._is_blank_text(merged):
                    raise ValueError(f"{target_model} 流式返回空内容")
                yield merged
                return
            except Exception as exc:
                errors.append(exc)

        if errors:
            raise errors[-1]
        raise ValueError("未配置可用的 LLM 模型")

    async def embed(self, text: str) -> list[float]:
        """将文本转换为向量（需要支持 Embedding 的 API Key）"""
        client = await self._get_embed_client()
        config = await self._get_runtime_config()
        response = await client.embeddings.create(
            model=config["embedding_model"],
            input=text,
            dimensions=config["embedding_dimensions"],
        )
        return response.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量 Embedding"""
        client = await self._get_embed_client()
        config = await self._get_runtime_config()
        response = await client.embeddings.create(
            model=config["embedding_model"],
            input=texts,
            dimensions=config["embedding_dimensions"],
        )
        return [item.embedding for item in response.data]

    async def complete(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        max_tokens: int | None = DEFAULT_CHAT_MAX_TOKENS,
        provider_override: Any | None = None,
    ) -> str:
        """单次 LLM 补全"""
        return await self._complete_with_fallback(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            provider_override=provider_override,
        )

    async def stream_complete(
        self,
        system: str,
        user: str,
        temperature: float = 0.5,
        max_tokens: int | None = DEFAULT_CHAT_MAX_TOKENS,
        provider_override: Any | None = None,
    ) -> AsyncGenerator[str, None]:
        """流式 LLM 补全 — yield token 片段"""
        async for token in self._stream_complete_with_fallback(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            provider_override=provider_override,
        ):
            yield token

    async def _resolve_solution_channel(self, channel_key: str | None) -> dict:
        from app.services.runtime_settings import get_solution_channel_config

        config = await get_solution_channel_config()
        channels = [
            channel for channel in config.get("channels", [])
            if channel.get("enabled", True)
        ]
        if not channels:
            return {}

        selected_key = channel_key or config.get("default_channel_key")
        for channel in channels:
            if channel.get("key") == selected_key:
                return channel
        return channels[0]

    @staticmethod
    def _format_solution_channel_instruction(channel: dict) -> str:
        if not channel:
            return ""
        return (
            "\n\n当前问答频道：{name}\n"
            "频道说明：{description}\n"
            "频道回答要求：{hint}"
        ).format(
            name=channel.get("name") or "通用问答",
            description=channel.get("description") or "围绕 GEO 和 AI 搜索进行问答。",
            hint=channel.get("system_hint") or "优先回答用户问题，再补充必要背景和行动建议。",
        )

    async def rag_recommend(
        self,
        message: str,
        diagnostic_report_id: Optional[str],
        db,
        channel_key: Optional[str] = None,
        provider_override: Any | None = None,
    ) -> tuple[str, list]:
        """
        RAG 问答管道（非流式）：
        1. 将用户问题向量化
        2. 在 Qdrant 中检索 top-5 相关公司知识块
        3. 构建含检索上下文和频道规则的 Prompt → LLM 生成回答
        4. 返回 (回复文本, 关联公司列表)
        """
        from app.services.vector_store import vector_store
        from app.services.company_retrieval import fallback_company_recommendations
        from app.services.runtime_settings import get_solution_template_config
        from sqlalchemy import select
        from app.models.company import Company, PublishStatus

        # BYOK 请求只能使用用户自己的模型凭据。平台 Embedding 属于平台成本，
        # 因此 BYOK 路径直接使用数据库中的确定性推荐作为上下文。
        search_results = []
        if provider_override is None:
            try:
                query_vector = await self.embed(message)
                # Step 2: Qdrant 检索
                search_results = vector_store.search_companies(query_vector, top_k=5)
            except Exception:
                search_results = []

        # Step 3: 获取公司详情
        company_ids = list({r["company_id"] for r in search_results if r.get("company_id")})
        recommended_companies = []
        context_text = ""

        if company_ids:
            import uuid
            result = await db.execute(
                select(Company).where(
                    Company.id.in_([uuid.UUID(cid) for cid in company_ids]),
                    Company.publish_status == PublishStatus.PUBLISHED,
                )
            )
            companies = result.scalars().all()
            for c in companies:
                context_text += f"\n### {c.name}\n{c.description or c.short_description or ''}\n"
                recommended_companies.append({
                    "id": str(c.id),
                    "name": c.name,
                    "short_description": c.short_description,
                    "logo_url": c.logo_url,
                    "geo_score": c.geo_score,
                    "category": c.category,
                })
        elif db is not None:
            fallback_companies = await fallback_company_recommendations(
                db,
                message,
                diagnostic_report_id=diagnostic_report_id,
                limit=5,
            )
            for c in fallback_companies:
                context_text += f"\n### {c.name}\n{c.description or c.short_description or ''}\n"
                recommended_companies.append({
                    "id": str(c.id),
                    "name": c.name,
                    "short_description": c.short_description,
                    "logo_url": c.logo_url,
                    "geo_score": c.geo_score,
                    "category": c.category,
                })

        # Step 4: 诊断报告上下文
        diagnostic_context = ""
        if diagnostic_report_id:
            from app.models.diagnostic import DiagnosticReport
            import uuid
            result = await db.execute(
                select(DiagnosticReport).where(DiagnosticReport.id == uuid.UUID(diagnostic_report_id))
            )
            report = result.scalar_one_or_none()
            if report and report.overall_score:
                diagnostic_context = (
                    f"\n用户网站诊断结果：GEO 综合评分 {report.overall_score:.0f}/100\n"
                )

        templates = await get_solution_template_config()
        channel = await self._resolve_solution_channel(channel_key)
        channel_instruction = self._format_solution_channel_instruction(channel)
        system_prompt = f"{templates['system_prompt']}{channel_instruction}"

        user_prompt = f"""用户问题：{message}
问答频道：{channel.get('name', '通用问答') if channel else '通用问答'}
{diagnostic_context}
相关公司知识库：
{context_text or "（暂无匹配数据，请根据问题给出一般性建议）"}

{templates["response_instruction"]}"""

        reply_max_tokens = (
            ACTION_PLAN_MAX_TOKENS
            if (channel.get("key") if channel else channel_key) == "action-plan"
            else DEFAULT_CHAT_MAX_TOKENS
        )
        reply = await self.complete(
            system_prompt,
            user_prompt,
            max_tokens=reply_max_tokens,
            provider_override=provider_override,
        )
        return reply, recommended_companies

    async def rag_recommend_stream(
        self,
        message: str,
        diagnostic_report_id: Optional[str],
        db=None,
        channel_key: Optional[str] = None,
        provider_override: Any | None = None,
    ) -> AsyncGenerator[dict, None]:
        """RAG 问答流式版本"""
        from app.services.vector_store import vector_store
        from app.services.company_retrieval import fallback_company_recommendations
        from app.services.runtime_settings import get_solution_template_config

        search_results = []
        if provider_override is None:
            try:
                query_vector = await self.embed(message)
                search_results = vector_store.search_companies(query_vector, top_k=5)
            except Exception:
                search_results = []
        company_ids = list({r["company_id"] for r in search_results if r.get("company_id")})

        if not company_ids and db is not None:
            fallback_companies = await fallback_company_recommendations(
                db,
                message,
                diagnostic_report_id=diagnostic_report_id,
                limit=5,
            )
            company_ids = [str(company.id) for company in fallback_companies]

        if company_ids:
            yield {"type": "companies", "content": [{"company_id": cid} for cid in company_ids]}

        templates = await get_solution_template_config()
        channel = await self._resolve_solution_channel(channel_key)
        channel_instruction = self._format_solution_channel_instruction(channel)
        system_prompt = f"{templates['streaming_system_prompt']}{channel_instruction}"
        user_prompt = (
            f"用户问题：{message}\n"
            f"问答频道：{channel.get('name', '通用问答') if channel else '通用问答'}\n\n"
            f"{templates['response_instruction']}"
        )

        stream_max_tokens = (
            ACTION_PLAN_MAX_TOKENS
            if (channel.get("key") if channel else channel_key) == "action-plan"
            else DEFAULT_CHAT_MAX_TOKENS
        )
        async for token in self.stream_complete(
            system_prompt,
            user_prompt,
            max_tokens=stream_max_tokens,
            provider_override=provider_override,
        ):
            yield {"type": "text", "content": token}

    async def extract_company_info(self, html: str) -> dict:
        """从官网页面正文中提取结构化公司信息（用于爬取清洗任务）。"""
        system = """你是企业官网结构化提取专家。从带页面来源标记的官网正文中提取公司信息，严格返回 JSON：
{
  "name": "公司名",
  "description": "300字内完整介绍",
  "short_description": "80字内一句话简介",
  "category": "教育培训/企业服务/AI与软件/营销广告/金融/医疗健康/消费零售/工业制造/文化传媒/交通出行/房地产/专业服务/其他",
  "headquarters": "总部城市或地区",
  "funding_stage": "种子轮/天使轮/A轮/B轮/C轮/已盈利/未知",
  "employee_count": "1-10人/10-50人/50-200人/200-500人/500-1000人/1000人以上/未知",
  "founded_date": "YYYY-MM 或 null",
  "tags": ["最多6个品牌/业务语义标签"],
  "tech_stack": ["最多8个明确出现在页面里的技术或平台名"],
  "team_members": [{"name": "姓名", "role": "职位", "bg": "背景，可为空"}]
}
要求：
1. 只提取页面明确出现或可高度确定的信息。
2. category 必须选择最贴近公司主营业务的一项，禁止因页面使用 AI 技术就统一归为 AI与软件。
3. tags 使用主营产品、服务对象、业务场景等语义标签。
4. tech_stack 只填明确出现的技术、平台、工具名。
5. team_members 最多 6 人。
6. 严格返回 JSON，不要额外解释。"""

        raw = await self.complete(system, f"官网页面正文：\n{html[:24000]}", temperature=0.1)
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
        return {}

    async def select_company_pages(self, base_url: str, homepage_title: str, candidate_links: list[dict]) -> list[dict]:
        """从首页一级目录中挑选不超过 3 个关键页面。"""
        from app.services.company_ingest import fallback_select_company_pages

        fallback = fallback_select_company_pages(base_url, homepage_title, candidate_links, limit=3)
        if not candidate_links:
            return fallback

        candidate_payload = [
            {
                "url": item.get("url"),
                "title": item.get("title"),
                "path": item.get("path"),
            }
            for item in candidate_links[:12]
        ]
        system = """你是企业官网抓取规划助手。基于官网首页和一级目录链接，选择不超过 3 个最适合构建企业知识库的页面。
要求：
1. 必须包含主页（role=homepage）。
2. 其余页面优先选择 about/company/team/leadership/product/solution 这类能解释公司是谁、做什么、团队是谁的页面。
3. 不要选择登录、注册、隐私、博客、新闻等页面，除非没有更好的选择。
4. 返回 JSON：{"selected":[{"url":"...","title":"...","role":"homepage/about/team/product/supporting","reason":"一句中文解释"}]}。
5. 严格返回 JSON，不要额外解释。"""

        user = (
            f"官网主页：{base_url}\n"
            f"主页标题：{homepage_title}\n"
            f"候选链接：{json.dumps(candidate_payload, ensure_ascii=False)}"
        )
        try:
            raw = await self.complete(system, user, temperature=0.1)
            start, end = raw.find("{"), raw.rfind("}") + 1
            if start < 0 or end <= start:
                return fallback
            parsed = json.loads(raw[start:end])
            selected = []
            allowed_urls = {base_url}
            allowed_urls.update(item["url"] for item in candidate_payload if item.get("url"))
            used = set()
            for item in parsed.get("selected", []):
                url = item.get("url")
                if not url or url in used or url not in allowed_urls:
                    continue
                selected.append(
                    {
                        "url": url,
                        "title": item.get("title") or homepage_title,
                        "role": item.get("role") or "supporting",
                        "reason": item.get("reason") or "该页面被判定为企业知识库构建的重要来源。",
                    }
                )
                used.add(url)
                if len(selected) >= 3:
                    break
            if not selected:
                return fallback
            if base_url not in used:
                selected.insert(
                    0,
                    {
                        "url": base_url,
                        "title": homepage_title or "主页",
                        "role": "homepage",
                        "reason": "主页通常包含公司定位、产品摘要与核心导航，是企业知识库的主入口。",
                    },
                )
            return selected[:3]
        except Exception:
            return fallback

    async def extract_entities(self, text: str) -> dict:
        """从公司文本中提取实体和关系（用于 Neo4j 知识图谱构建）"""
        system = """从文本中提取实体和关系，返回 JSON：
{"nodes": [{"type": "Person/Product/Technology/Company", "name": "...", "description": "..."}],
"relationships": [{"from": "name", "type": "FOUNDED_BY/HAS_PRODUCT/USES_TECH/COMPETES_WITH", "to": "name"}]}
只提取明确提到的实体。严格返回 JSON。"""

        raw = await self.complete(system, text, temperature=0.1)
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(raw[start:end])
        return {"nodes": [], "relationships": []}


# 全局单例
ai_client = AIClient()


# ---- 向后兼容的函数式接口 ----

async def chat_completion(messages: list[dict], model: str | None = None, temperature: float = 0.3, max_tokens: int = 4096) -> str:
    return await ai_client._complete_with_fallback(
        messages,
        temperature=temperature,
        model=model,
        max_tokens=max_tokens,
    )


async def get_embedding(text: str) -> list[float]:
    return await ai_client.embed(text)


async def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    return await ai_client.embed_batch(texts)
