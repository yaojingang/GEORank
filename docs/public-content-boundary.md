# Public content boundary

GEOrank keeps product capabilities in the public repository while runtime data and private content stay outside Git. The tutorial models, APIs, admin editor, Markdown rendering, server-rendered channel pages, detail pages, and empty states remain available for self-hosted deployments.

## Included in the public repository

- Application source code, migrations, tests, and deployment templates.
- `.env.example` with explicit placeholders.
- The configurable static homepage template and its release snapshot.
- Public expert-channel seed data already approved for distribution.
- One short, original tutorial seed named `GEO 基础检查清单`.
- Neutral icons and empty states used by public pages.
- Reviewed synthetic sample data in `.csv` or JSON Lines format under `public/data`, `data/public`, or an explicitly public runtime asset directory. Samples must contain no customer or runtime export data.

## Excluded from the public repository

- Environment files other than `.env.example`.
- Production credentials, provider keys, administrator passwords, sessions, and encryption material.
- Tutorial source archives, private knowledge-base exports, internal documents, and private document links.
- Databases, dumps, backups, spreadsheets, Parquet files, and other runtime exports. JSON Lines and CSV files are excluded outside the narrow public sample-data allowlist above.
- Customer data, user activity, generated reports, caches, screenshots containing private state, and build output caches.
- Private tutorial images and generated copies of private tutorial text.

## Automated gate

Run the public boundary gate before creating a release commit:

```bash
pnpm public:check
```

The gate has two explicit inventory modes. In a Git checkout it reads all tracked files from the index and scans both each index blob and its changed working copy, so untracked local files do not affect the result. In a source archive without local `.git` metadata it recursively enumerates every file and symbolic link without following link targets. Pristine archive mode scans dependency paths too. After the pristine scan and locked dependency installation, `--allow-installed-dependencies` ignores only the root and declared pnpm-workspace `node_modules` directories; Git mode ignores this flag. Virtual environments, cache directories, and similarly named paths elsewhere remain in scope. Unsupported filesystem entries, embedded or invalid Git metadata, escaping symbolic links, and every unsafe file found by the normal policy fail closed.

Validate an extracted source archive in this order:

```bash
node scripts/check-public-boundary.mjs
pnpm install --frozen-lockfile
pnpm release:check
```

Both modes reject forbidden paths, high-confidence secret formats, hard-coded seed administrator passwords, Feishu links, and GitHub Wiki links. Text candidates are checked as UTF-8, UTF-16LE, and UTF-16BE; a NUL byte in any path without an explicit binary extension fails closed. Database, dump, backup, spreadsheet, and Parquet extensions remain blocked inside public asset directories. Placeholders such as `replace-me`, `your-token-here`, and test-only values are accepted only when the complete value matches the approved sentinel form.

`scripts/public-content-policy.mjs` supplies the shared public-content checks. It applies Unicode NFKC plus whitespace, hyphen, and parenthesis normalization before detecting phone and telephone numbers, email addresses, and WeChat account identifiers in public data and homepage content. The gate also rejects legacy repository-owner references across all tracked files, including history, release, and binary paths; there are no directory-level exceptions.

The workflow in `.github/workflows/public-boundary.yml` runs the same command for pull requests and protected release branches.

## Release checklist

1. Keep local secrets in an ignored `.env` file and commit only `.env.example`.
2. Export databases, reports, screenshots, and content archives outside the repository.
3. Run the pristine archive scan before dependency installation, then run `pnpm public:check`, application type checks, and the backend test suite.
4. Inspect the complete Git history before publication. Git mode evaluates index and working-copy content, while archive mode evaluates the extracted source tree; a clean public history prevents deleted private files from remaining reachable.
5. Review public expert data, homepage links, analytics settings, and tutorial seeds for distribution rights.
