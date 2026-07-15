# Release engineering

GEOrank uses a product release version plus independent component versions. The repository release target for this source tree is **v1.3.0**.

## Version policy

| Surface | Version in this release | Policy |
|---|---:|---|
| Product release, root workspace, web, admin, auth, i18n, UI | 1.3.0 | These private workspaces ship as one GEOrank product and move with the repository tag. |
| FastAPI metadata, health/readiness responses, OpenAPI document | 1.3.0 | Public API metadata reports the product release. `backend/app/version.py` is the Python source of truth. |
| TypeScript API SDK | 0.1.0 | This private workspace uses an independent source version and ships with the repository. It is not published to npm. Its `openapi.json` reports the API product version. |
| CLI | 0.1.0 | The CLI has an independent package lifecycle. `georank --version`, `pyproject.toml`, and `georank_cli.__version__` stay aligned. |

Product release updates change the root `package.json`, product workspace manifests, `backend/app/version.py`, and the generated OpenAPI document together. SDK source revisions update only the private workspace version and repository release notes. CLI releases update its component version and release notes. `pnpm release:contract` blocks accidental version drift across these surfaces.

## CI and release gate

Frontend CI uses the locked pnpm version and lockfile, then runs the release contract, generated SDK drift check, public boundary checks, i18n checks, web/admin type checks, and production builds. Backend CI verifies the checked-in OpenAPI document against the live FastAPI schema, then runs Alembic and the full Python suite against PostgreSQL. It also builds the crawler image and runs its import smoke test. CLI CI installs the package, executes all CLI tests, and verifies the installed entry point.

Use this local gate before preparing a source release:

```bash
pnpm install --frozen-lockfile
pnpm release:check
```

The backend database suite and container migration contract require PostgreSQL and Docker, so they remain explicit release-matrix steps. See [Database migrations and startup](database-migrations.md).

## Python runtime matrix

- The API, migration service, worker, and beat image use Python 3.12.13 on Debian Bookworm.
- The crawler uses the Playwright 1.49.1 Jammy image with Python 3.10.12. This keeps the browser binaries, Python Playwright package, and system libraries on the same Playwright release.
- `backend/requirements.txt` is installed into both images. `backend/scripts/crawler_import_smoke.py` checks Python 3.10 and imports Playwright, Celery, and the crawler task in CI.

## Container image updates

Dockerfiles and Compose use explicit image tags plus multi-architecture registry index digests. This gives amd64 and arm64 users the same reviewed release while keeping the content immutable. Dependabot checks Dockerfiles and Compose weekly. A digest update requires these checks:

1. Confirm the tag and digest resolve to a multi-architecture image index.
2. Build both backend images.
3. Run the crawler import smoke and container migration contract.
4. Render the merged Compose configuration with all required test environment values.

The Playwright image and `playwright==1.49.1` requirement move together.

## pnpm lifecycle scripts

pnpm blocks dependency lifecycle scripts unless a package is explicitly reviewed. The root `onlyBuiltDependencies` list contains three build-time dependencies used by Next.js and next-intl:

- `sharp`: validates the native image-processing package used by Next.js.
- `@parcel/watcher`: prepares the native file watcher used through next-intl.
- `@swc/core`: validates the native SWC compiler binding used through next-intl.

Keep this allowlist narrow. A clean frozen install must finish without an ignored-build warning, and `node_modules/.modules.yaml` must keep `pendingBuilds` empty. Review any new package before adding it to `onlyBuiltDependencies`.
