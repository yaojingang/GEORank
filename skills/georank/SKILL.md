---
name: georank
description: Operate and manage a self-hosted GEOrank instance through its HTTP API. Use when asked to log in, inspect a GEOrank account, submit or manage companies, run or read GEO diagnostics, manage solution conversations, expand keywords, inspect usage, or perform authenticated GEOrank administrator work across users, content, experts, providers, modules, homepage releases, and settings. Login guidance defaults to an ordinary user and unlocks administrator actions only after /api/auth/me returns role=admin. Do not use for general GEO strategy, article writing, SEO advice, or GEOrank code development that does not operate a running instance.
---

# GEOrank Operator

## Workflow

Resolve every relative path below from this Skill directory, independent of the caller's current workspace.

1. Confirm the target GEOrank base URL. Use `http://localhost:8000` only for a local instance; require HTTPS for remote instances.
2. Resolve authentication:
   - Treat login as an ordinary-user flow and never ask the user to choose a role.
   - Run `python3 scripts/georank_client.py login --account <account>` when no session exists.
   - Run `python3 scripts/georank_client.py whoami` after login. Enable administrator branches only when the returned role is `admin`; treat `enterprise` as a regular authenticated user.
3. Read `references/user-capabilities.md` for public and user-owned operations. Read `references/admin-capabilities.md` only for administrator requests.
4. For reads, call the API directly with `scripts/georank_client.py call GET <path>`.
5. For writes, run the same command without `--execute` first and show the preflight result. Execute only after the user's request clearly authorizes that exact change.
6. Before any administrator mutation, read `references/safety-policy.md` and supply its required confirmation phrase. Never infer administrator authority from the wording of a request.
7. Return an execution receipt containing the action, status, resource identifiers, request ID when present, and the next safe step. Remove passwords, tokens, API keys, and other secrets from all output.

## Safety Boundary

- Never pass passwords or tokens as command-line arguments. Login reads `GEORANK_PASSWORD` or uses a hidden terminal prompt; API calls read `GEORANK_TOKEN` or the private session file.
- Never expose, copy, or persist a secret outside the session store managed by the client.
- Treat every non-read call as a side effect. `--execute` is required.
- Require `APPLY_ADMIN_CHANGE` for administrator writes and `DELETE:<api-path-with-query>` for deletions.
- Stop when the detected role lacks permission, the target resource is ambiguous, or rollback information is unavailable for a high-impact change.

## Output Contract

Return a compact Markdown or JSON receipt with:

- detected access level: public, user, or admin
- operation and target resource
- dry-run or executed status
- API status, resource IDs, and request ID when available
- redacted change summary and next step
- rollback guidance for administrator changes

## Reference Map

- `references/user-capabilities.md`: public and ordinary-user operations.
- `references/admin-capabilities.md`: administrator operation groups and confirmation requirements.
- `references/safety-policy.md`: authentication, secrets, side effects, polling, and rollback rules.
- `scripts/georank_client.py`: deterministic login, session, role detection, preflight, and API execution.
- `evals/trigger_cases.json`: routing positives, negatives, and near neighbors.
- `examples/request_payloads.json`: `file-backed fixture` examples listed by `input_files`.
- `reports/output-risk-profile.md`: likely output failures and repair checks.
- `reports/output_quality_scorecard.md`: current output and verification evidence.
- `reports/security_trust_report.md`: generated `trust report` after validation.
