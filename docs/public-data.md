# Public data and built-in homepage

This document records the canonical source, publication path, and update rules for the reusable public data shipped with GEOrank.

## Expert profiles

`data/public/experts.json` is the canonical public fixture for the five built-in expert profiles:

- `yao-jingang` — 姚金刚
- `qiao-xiangyang` — 乔向阳
- `fu-wei` — 夫唯
- `guangtou-niuge` — 光头牛哥
- `zhang-kai` — 张凯

The fixture keeps stable UUIDs and slugs, the fields supported by the expert API and admin console, optional public asset/link fields, ordering, publication status, and authorization metadata. `avatar_url` is `null` because the reviewed repository contains no expert portrait asset. `social_links` stays empty because the reviewed sources do not provide a complete set of confirmed public profile URLs. The 姚金刚 arXiv paper URL is retained under `public_links` from the historical public expert-page source.

`source`, `provenance`, and `distribution_basis` record a maintainer-directed migration from the repository's public expert-channel seed. The repository records no separate authorization from each named subject. `verification_scope` states that the review covered migration consistency, public-data boundaries, and link provenance. `last_verified` is the date of that scoped review, and the biographical claims remain maintainer-supplied without independent fact-checking.

Migration `012_seed_expert_profiles` contains a frozen inline snapshot so an old database upgrade never depends on a mutable working-tree fixture. Its versioned audit copy is `backend/alembic/snapshots/012_seed_expert_profiles.json`; the migration test compares 012 only with that frozen seed snapshot. The current canonical fixture points to this seed snapshot through `migration_snapshot`. Keep migration 012 and its seed snapshot frozen. The downgrade deletes rows only when both the fixed UUID and slug match.

Future publication-state changes use a separate versioned contract. After a verified request, copy the canonical fixture, update the affected projection, and add `migration_chain` with the frozen seed entry followed by a state entry. Write the state snapshot under `backend/alembic/snapshots/` using `data/public/schemas/expert-state-transition.v1.schema.json`. Generate and review a new migration with `backend/migration_contracts/expert_migration_contract.py`; the module exposes the matching revision, parent revision, effective date, downgrade policy, and exact-pair state operations. The path-driven loader resolves each repository snapshot and Alembic module, validates seed-first/state-rest ordering and unique revisions, folds the state chain, and compares the result with the canonical projection. The PostgreSQL dry run must demonstrate that the affected expert leaves the public API projection while every unaffected expert remains published.

Public fixture review must confirm:

- exactly five expected UUID/slug pairs;
- unique IDs and slugs;
- no email, phone, WeChat, address, or private contact fields;
- a documented source, authorization basis, and verification date;
- links copied only from reviewed public material.

## Built-in homepage

Release `9fe4a087-42bc-423a-bc59-fc020018a6f9` is the built-in default homepage. Its canonical uploaded source is:

`runtime/homepages/releases/<release-id>/source`

The corresponding `manifest.json` is the immutable release record. `runtime/homepages/public/releases/<release-id>` contains the output produced by `build_zip_homepage_release`: HTML passes through the homepage normalizer, script markup is removed, local asset URLs are rewritten to `/_custom_homepage/active`, a restrictive CSP is inserted, SVG files pass through the markup sanitizer, and binary assets retain their bytes. `runtime/homepages/public/active` is runtime state: Git ignores it, and API startup rebuilds the relative symlink from the database selection.

The canonical source keeps the current template, CSS, book-cover asset, configuration, and the internal `/tutorial` link. Tests rebuild the published HTML from the source with `normalize_homepage_html`, then verify every public file against the manifest size and SHA-256 hash.

Treat an existing release directory as immutable. To publish an updated default homepage, package the revised canonical source and call `build_zip_homepage_release` with a new release ID. Commit the new source, generated public output, and manifest after the public boundary gate passes. The active pointer stays local to each deployment.

## Rights and requests

Software licensing and public-content rights have separate scopes. Read [DATA_LICENSE.md](../DATA_LICENSE.md) before redistributing expert identity data, a portrait, book-cover artwork, a logo, or branded homepage material.

A public issue may identify only the affected slug or repository path and a non-sensitive summary. Sensitive evidence uses [GitHub Private Vulnerability Reporting](https://github.com/yaojingang/GEORank/security/advisories/new), which must be enabled before the repository is released.

After a verified rights or privacy request, maintainers first mark the canonical fixture record `hidden` and stop publishing it through the API. They then add a state snapshot and new tombstone migration for the exact `(id, slug)` pair, followed by the `migration_chain` pointer update described above. Existing seed migrations and seed snapshots stay frozen. A verified rights or privacy request can require history removal when a frozen artifact itself perpetuates the violation; that exceptional cleanup follows the history process below and records replacement revisions.

The response must also cover immutable public surfaces. Replace affected homepage and downloadable releases. When the material requires removal from Git history, use a clean-history rewrite, request GitHub sensitive-data purge support, and publish a release replacement. Notify known downstream users without copying the disputed evidence. Independent forks, caches, mirrors, indexes, and downstream copies remain outside the maintainer's direct control.

The current fixture remains published and featured because no verified removal request is implemented by this release. It has no production state snapshot or tombstone migration.
