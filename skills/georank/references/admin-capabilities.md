# Administrator capabilities

Administrator paths require a valid session whose `/api/auth/me` response contains `role=admin`. The client verifies this before every `/api/admin` request.

## Capability groups

| Group | Path family | Representative actions |
|---|---|---|
| Operations | `/api/admin/dashboard`, `/api/admin/ops/*` | Read platform state and recent failures. |
| Companies | `/api/admin/companies*` | Create, edit, approve, reject, retry, and delete companies. |
| Diagnostics | `/api/admin/diagnostics/*` | Inspect, retry, export, delete reports, and configure rules. |
| Solutions | `/api/admin/solutions/*` | Inspect/delete conversations and configure templates/channels. |
| Content | `/api/admin/content*`, `/api/admin/tutorials*` | Create, edit, publish, and delete content. |
| Experts | `/api/admin/experts*` | Create, edit, and delete expert profiles. |
| Users | `/api/admin/users*` | Create/edit users, change roles, toggle access, reset passwords, and delete users. |
| Keywords | `/api/admin/keywords/*` | Create, inspect, export, and delete keyword packs. |
| AI policy | `/api/admin/api-policy*`, `/api/admin/llm-providers*` | Configure quotas, providers, models, and encrypted keys. |
| Frontend | `/api/admin/frontend-modules*`, `/api/admin/homepage*` | Toggle modules and manage homepage releases. |
| Settings | `/api/admin/settings*` | Read, update, or delete allowed settings. |

## Required gates

- Administrator reads execute after role verification.
- Administrator writes require `--execute --confirm APPLY_ADMIN_CHANGE`.
- Every delete requires `--execute --confirm 'DELETE:<exact-api-path-including-query>'`.
- Settings and provider payloads must come from a protected file or stdin. Never place keys or passwords in argv.
- Homepage activation, role change, password reset, module changes, provider changes, and content publication require a user-visible before/after summary.

## Examples

```bash
# Read-only
python3 scripts/georank_client.py call GET /api/admin/dashboard

# Preflight only
python3 scripts/georank_client.py call PUT /api/admin/frontend-modules --json-file /path/to/modules.json

# Execute an approved admin change
python3 scripts/georank_client.py call PUT /api/admin/frontend-modules \
  --json-file /path/to/modules.json --execute --confirm APPLY_ADMIN_CHANGE

# Execute an approved deletion
python3 scripts/georank_client.py call DELETE /api/admin/diagnostics/reports/REPORT_ID \
  --execute --confirm 'DELETE:/api/admin/diagnostics/reports/REPORT_ID'
```
