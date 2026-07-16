# Public and user capabilities

Login begins as an ordinary-user flow. The login request contains an account or phone, password, and `remember_me`; it never sends a role. After authentication, `/api/auth/me` determines the actual role. Treat `enterprise` as a regular authenticated user until GEOrank adds a distinct policy.

## Authentication and profile

| Job | Method and path | Access | Notes |
|---|---|---|---|
| Log in | `POST /api/auth/login` | Public | Use the client `login` command; never place the password in argv. |
| Inspect account | `GET /api/auth/me` | User | Canonical source for the current role. |
| Update profile | `PUT /api/auth/me` | User | Preflight and `--execute`; body may contain email, username, or phone. |
| Change password | `PUT /api/auth/password` | User | Read the body from a protected JSON file or stdin; never echo it. |

## Companies

| Job | Method and path | Access | Notes |
|---|---|---|---|
| Submit company | `POST /api/companies/submit` | Public or user | May start crawling and AI usage. |
| Browse companies | `GET /api/companies/` | Public | Supports page, size, category, sort, and search query. |
| Read company | `GET /api/companies/{id}` | Public | Use an ID or supported identifier. |
| Check pipeline | `GET /api/companies/{id}/pipeline-status` | Public | Poll with bounded intervals; stop on completed or failed. |
| Submit for review | `POST /api/companies/{id}/submit-review` | Public or user | Confirm the company ID before execution. |
| Upvote | `POST /api/companies/{id}/upvote` | User | User-scoped side effect. |
| Find similar | `GET /api/companies/{id}/similar` | Public | Read-only. |

## Diagnostics, solutions, keywords, and usage

| Job | Method and path | Access | Notes |
|---|---|---|---|
| Start diagnosis | `POST /api/diagnostics/` | Public or user | May incur AI usage; capture `report_id`. |
| List own diagnoses | `GET /api/diagnostics/history` | User | Results are scoped to the current user. |
| Read diagnosis | `GET /api/diagnostics/{report_id}` | Owner or public ownerless | Respect the ownership check. |
| List solution channels | `GET /api/solutions/channels` | Public | Read-only configuration. |
| Run solution chat | `POST /api/solutions/chat` | Public or user | May incur AI usage. |
| List own conversations | `GET /api/solutions/conversations` | User | User-scoped. |
| Read conversation | `GET /api/solutions/conversations/{id}` | Owner or public ownerless | Respect the ownership check. |
| Claim conversation | `POST /api/solutions/conversations/{id}/claim` | User | Assigns an owner. |
| Expand keywords | `POST /api/keywords/expand` | Public or user | May incur AI usage. |
| Inspect usage policy | `GET /api/usage/policy` | Public | Read-only. |
| Inspect own usage | `GET /api/usage/me` | Public or user | Scope depends on current session. |

## Execution pattern

```bash
python3 scripts/georank_client.py login --account user@example.com
python3 scripts/georank_client.py whoami
python3 scripts/georank_client.py call POST /api/diagnostics/ --json-file /path/to/diagnosis.json
python3 scripts/georank_client.py call POST /api/diagnostics/ --json-file /path/to/diagnosis.json --execute
```

The bundled example file contains multiple named fixtures, so select one payload into a separate temporary JSON file before using it as an API body.
