# GEOrank

[简体中文](README.md) | English

**[Try the official demo: GEORankHub](https://www.georankhub.com/)**

[GitHub repository](https://github.com/yaojingang/GEORank)

GEOrank is an open-source workbench for Generative Engine Optimization. It helps teams diagnose AI search visibility, turn insights into Q&A and action plans, expand keyword assets, generate structured content tools, and manage the workflow through a self-hosted admin console.

Teams can use it as an internal GEO toolbox, apply it to their own diagnostic and analysis workflows, or self-host and extend the code to deliver GEO tools and services to clients.

This repository includes the product code, engineering structure, configuration templates, demo data, and the built-in public expert profiles used by the experts channel. It does not include private production data, non-public expert content, real tutorial assets, user conversations, generated customer plans, keyword packs, database dumps, object storage files, or API keys.

## Official Demo

[GEORankHub](https://www.georankhub.com/) is the official online demo and public-interest GEO research platform for GEOrank. It provides direct access to website diagnostics, GEO Q&A, action plans, keyword expansion, structured tools, tutorials, open documentation, and research resources.

## Why GEOrank?

Search is moving from traditional result pages to AI answers. Users increasingly ask systems such as ChatGPT, Claude, Perplexity, and Gemini directly instead of clicking through search result pages.

That creates a new set of questions:

- Can AI systems accurately understand your company, products, and expertise?
- Is your website structured in a way that can be summarized, cited, and recommended by AI systems?
- Should your team prioritize Schema, page structure, metadata, citation signals, or content readability?
- How can a diagnostic report become an executable 30/60/90-day action plan?
- How can keywords, questions, tutorials, tools, and expert resources become reusable assets?
- How can an open-source system support user-owned API keys and reduce platform operating costs?

GEOrank turns those disconnected tasks into a structured workflow: diagnose, ask, plan, expand, structure, and manage.

The open-source build shows the built-in GEO workbench homepage at `/` by default. The original company directory remains available at `/companies`, and you can upload or switch custom homepage releases from the admin settings panel.

## How You Can Use GEOrank

- **Build an internal GEO toolbox**: bring website diagnostics, AI Q&A, action plans, keyword expansion, and structured-content tools into one workspace for growth, SEO, content, and product teams.
- **Improve your own business and brand**: analyze the AI search visibility of corporate sites, product pages, and brand content, then produce diagnostic reports, recommendations, content ideas, and 30/60/90-day action plans.
- **Deliver GEO services to clients**: consulting firms, marketing agencies, and independent advisors can use GEOrank for client diagnostics, Q&A, analysis, keyword planning, and content-tool support across pre-sales assessments, project delivery, and ongoing advisory work.
- **Run GEO capabilities in your own environment**: deploy the full project on your infrastructure and connect your own model APIs, databases, analytics, and access policies while keeping business data, credentials, and client records under your control.
- **Create a tailored product from the open-source code**: extend the homepage, channels, diagnostic rules, model providers, and tool modules for an internal team, a specific industry, or a client segment.
- **Build a GEO resource and knowledge platform**: organize companies, tools, service providers, experts, tutorials, and case studies into a public directory, a tool collection, or an internal GEO knowledge base.

## Features

| Module | Description |
|---|---|
| Company Directory | Collect, review, categorize, and publish GEO-related companies, tools, services, and examples |
| Website Diagnostics | Evaluate Schema, page structure, metadata, content readability, citation signals, and AI search visibility |
| AI Q&A | Generate structured answers around GEO, AI search, and brand visibility with company and diagnostic context |
| GEO Action Plans | Generate executable 30/60/90-day optimization plans from goals, websites, resources, and constraints |
| Keyword Expansion | Build reusable keyword assets across topics, questions, scenarios, commercial intent, and recommendation patterns |
| GEO Tools | Generate JSON-LD, llms.txt, GEO titles, AI-friendliness checks, and knowledge-base drafts |
| Experts | Present 5 built-in public GEO and AI expert profiles with detail pages |
| Tutorials | Organize GEO knowledge, technical markup, content structure, governance, and practical examples |
| Admin Console | Manage content, settings, API providers, usage policy, modules, homepage releases, and analytics snippets |

## Architecture

GEOrank is a monorepo with a static frontend, a Next.js 2.0 migration path, a FastAPI backend, and shared packages.

- **Frontend**: the 3009 static frontend is the current experience baseline, with a Next.js App Router migration path.
- **Admin**: Next.js admin console for companies, diagnostics, Q&A, keywords, experts, tutorials, users, and settings.
- **Backend**: FastAPI, SQLAlchemy, Alembic, Celery.
- **Data services**: PostgreSQL, Redis, Qdrant, Neo4j, MinIO.
- **AI layer**: OpenAI-compatible chat and embedding providers with configurable API pools.
- **Tooling**: pnpm workspace, Turborepo, OpenAPI SDK, Docker Compose.

## Local Development

```bash
pnpm install
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Web app
pnpm dev:web

# Admin app
pnpm dev:admin
```

Compose runs the one-shot `migrate` service first. API and task services start only after the database reaches the Alembic head; `migrate` showing `Exited (0)` in `docker compose ps` is expected. See [Database migrations and startup](docs/database-migrations.md) for upgrades, legacy database recovery, and failure handling.

AI-powered features require an OpenAI-compatible model provider. Configure your provider in `.env` or in the admin settings panel after the backend is running.

## Production gateway and TLS

The Compose Traefik service uses the read-only configuration directory as its only file provider. Traefik, `frontend`, and `api` communicate on the shared Compose network through stable service names. Traefik has no Docker socket access, and its Dashboard is disabled.

Set `GEORANK_HTTP_PORT` and `GEORANK_HTTPS_PORT` to change the public HTTP and HTTPS entry ports. Frontend, API, database, cache, vector, graph, and object-storage services remain private to the Compose network with no direct host ports. `docker-compose.dev.yml` binds the static frontend and API to `127.0.0.1`; `GEORANK_FRONTEND_PORT` and `GEORANK_API_PORT` control their local ports for static-page and Next.js development. The repository template supplies HTTP routes and reserves the `websecure` entry point on port 443. Configure a trusted certificate, certificate resolver, and TLS router before serving HTTPS, or terminate TLS at an external load balancer. The built-in ACME example stores state in the dedicated volume at `/var/lib/traefik/acme.json`, leaving the configuration mount read-only. The current API uses HTTP and SSE without a WebSocket endpoint; `/api` and `/api/` paths are forwarded directly to the API service.

## Open Source Boundary

This repository only contains product code, engineering structure, configuration templates, and demo data.

See [Public data and built-in homepage](docs/public-data.md) for the canonical expert fixture, immutable homepage source, and update workflow.

See [Release engineering](docs/release-engineering.md) for the version policy, CI contract, pinned container images, and release gate. Run `pnpm install --frozen-lockfile` followed by `pnpm release:check` for a release candidate.

It does not include:

- Real API keys.
- Production databases, vector stores, graph data, or object storage files.
- Non-public expert profiles or private expert content maintained in the admin console.
- Real tutorial content.
- User conversations.
- Customer plans or diagnostic records.
- Keyword packs or commercial datasets.
- Runtime custom-homepage releases uploaded by users through the admin console, except for the built-in default homepage included with the repository.

## Disclaimer

GEOrank is a research and engineering project for Generative Engine Optimization. It helps teams analyze and improve AI search visibility, but it does not sell rankings, guarantee model recommendations, or represent any AI search provider.

## License

Software code is licensed under Apache-2.0. Expert profiles, names, likenesses, brands, and built-in homepage content have additional rights boundaries described in [DATA_LICENSE.md](DATA_LICENSE.md).
