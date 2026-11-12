# AI Overview 证据源（GoAnyAPI）

GEO 诊断的问答环节目前由 LLM 生成：它回答的是「模型会怎么答」，而不是「Google 实际怎么答」。
AI Overview 是 Google 自己的答案层，引用的是它自己选的来源——这两件事经常不一致：
模型给出的建议再漂亮，也换不来一次真实的 AI Overview 引用。

`backend/app/services/ai_overview.py` 补上这条真实证据：给定一个查询词，
取回 Google AI Overview 的正文与引用列表，用来判断目标品牌/域名是否被引用、引用在第几位。

## 启用方式

```bash
GOANYAPI_API_KEY=your-key
# 默认 https://api.goanyapi.com ，一般不用改
GOANYAPI_BASE_URL=https://api.goanyapi.com
```

Key 留空时 `is_configured()` 返回 `False`，调用方按「证据源未启用」降级，原有诊断流程不受影响。

## 用法

```python
from app.services import ai_overview

if ai_overview.is_configured():
    evidence = await ai_overview.fetch_ai_overview(
        "how do solar panels work",
        country="us",
        language="en",
        device="desktop",
    )
    visibility = ai_overview.brand_visibility(
        evidence["citations"],
        "EnergySage",
        domains=["energysage.com"],
    )
    # evidence["available"]      AI Overview 是否存在（false 也是成功响应）
    # evidence["answer"]         答案正文
    # evidence["citations"]      引用来源（已按 URL 去重，带位次）
    # visibility["cited"]        是否被引用，position 为引用位次
    # visibility["share"]        单一来源在引用中的占比
```

## 计费与失败处理

- 每次请求约 3 credits（约 \$0.003）。`feature_available=false` 的成功响应照样计费，
  所以调用前应先用便宜的接口（如关键词量）筛掉明显没有 AI Overview 的词。
- 402（余额不足）、401/403（鉴权失败）抛出的 `AIOverviewRequestError.retryable=False`，不要重试。
- 429、500/502/503/504 与网络错误 `retryable=True`，可按指数退避重试。
- 引用去重时会忽略 `utm_*`、`gclid` 等追踪参数，并把 `www.` 与非 `www.` 视为同一来源。

## 为什么不直接接进诊断任务

诊断任务牵涉 AI 额度预留与计费（`resolve_async_ai_access` / `record_ai_usage`），
把新证据源并入流程需要同时改额度口径与报告结构，属于独立的设计决定。
这个 PR 只提供可复用的服务层与测试；如果要接入诊断流程，建议单独讨论：
按查询词缓存结果、只对高价值词调用、并在报告里把「模型模拟」与「AI Overview 实测」分开呈现。
