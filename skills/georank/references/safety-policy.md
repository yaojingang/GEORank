# Safety policy

## Authentication

- Default login guidance assumes an ordinary user account.
- Login never accepts or transmits a role selection.
- `/api/auth/me` is the only authority for enabling administrator branches.
- A missing, inactive, expired, or non-admin session stops administrator execution.
- The session file stores the token with owner-only permissions (`0600`) and a GEOrank format marker. The client replaces or removes only a recognized GEOrank session and leaves permissions on an existing parent directory unchanged. `GEORANK_TOKEN` overrides the stored token for ephemeral automation.

## Secrets

- Read passwords through a hidden prompt or the environment variable named by `--password-env`.
- Read API request bodies containing secrets from a protected file or stdin.
- Reject secret-bearing query parameters so receipts and confirmation phrases cannot expose them.
- Redact normalized key names containing token, password, secret, api_key, authorization, credential, or cookie, including snake_case, kebab-case, and camelCase variants.
- Do not place credentials in chat, command arguments, reports, fixtures, shell history, commits, or execution receipts.

## Side effects

| Risk | Default behavior | Execution gate |
|---|---|---|
| Read | Execute | Role check for administrator paths. |
| User/public write | Dry-run | `--execute`. |
| Administrator write | Dry-run | `--execute --confirm APPLY_ADMIN_CHANGE`. |
| Delete | Dry-run | `--execute --confirm DELETE:<exact-api-path-including-query>`. |

API paths are percent-decoded, validated, and re-encoded before role and risk classification. Request bodies are limited to 16 MiB, API responses to 32 MiB, and local sessions to 1 MiB.

AI-backed submissions may consume quota even when the eventual asynchronous task fails. Confirm the normalized target, capture the returned ID, and use bounded polling. Stop polling when the resource reaches a terminal status or the agreed timeout expires.

## Rollback boundary

The client can prevent unconfirmed writes, preserve a redacted request summary, and report request IDs. It cannot reverse deletion, recover an overwritten secret, restore a reset password, refund consumed model quota, or guarantee restoration of an external homepage asset. For those actions, require a backup, a known previous value, or an explicit compensating operation before execution.

## Failure handling

- `401`: stop and guide login again.
- `403`: report the detected role and required permission; do not retry with broader authority.
- `404`: verify the base URL, API version, and resource identifier.
- `409` or `422`: show the redacted API detail and request a corrected input.
- `429`: stop automated retries and report the applicable usage policy.
- `5xx` or network failure: keep the action state as unknown until a read confirms whether the write took effect.
