# Public data and content rights

GEOrank software code, original engineering documentation, and configuration templates are provided under the Apache License 2.0 in [LICENSE](LICENSE).

The repository also contains public expert profiles and a built-in homepage. Those materials can include names, biographies, likenesses, book covers, logos, product names, trade names, and trademarks. Their inclusion records authorization to distribute this repository snapshot. Apache-2.0 does not grant independent publicity, portrait, privacy, trademark, or endorsement rights held by an expert or another third party.

## Expert profiles

The five records in `data/public/experts.json` are supplied for the public GEOrank expert channel. The repository maintainer approved their distribution during the open-source migration. `source: user-authorized migration` records that maintainer-directed migration provenance. The repository does not record separate authorization from each named subject. `last_verified` records the date of the migration-consistency, privacy-boundary, and link-provenance review; it does not certify every biographical claim. The fixture labels those claims as maintainer-supplied and not independently fact-checked.

Reuse should preserve an accurate identity and context. Obtain any additional permission required by local law for advertising, endorsement, model training, profile aggregation, or other uses beyond the public channel supplied here. The fixture intentionally omits private contact fields and expert photographs. A public reference link remains subject to the linked site's own terms.

## Built-in homepage

The built-in homepage includes text, links, and an `AI营销：从SEO到GEO` book-cover image authorized for this repository snapshot. Rights in personal names, the cover artwork, logos, brands, and trademarks remain with their respective holders. Descriptive references do not imply sponsorship or endorsement.

## Updates and removal requests

To request a factual update or removal, open a [GitHub issue](https://github.com/yaojingang/GEORank/issues). A public issue must contain only the expert slug or repository path and a non-sensitive description of the change. Never post identity documents, private contact information, or other sensitive evidence in the issue.

Sensitive evidence uses [GitHub Private Vulnerability Reporting](https://github.com/yaojingang/GEORank/security/advisories/new). Private Vulnerability Reporting must be enabled in the GitHub repository before a public release. The reporter should send the public issue only after removing every private identifier, or use the private report alone.

The following removal playbook starts after a verified rights or privacy request:

1. Set the affected canonical fixture record to `hidden` and stop publishing it through the public API. Replace any current public homepage or downloadable release that contains the disputed material.
2. Keep the original seed migration and seed snapshot frozen. Create a state snapshot that follows `data/public/schemas/expert-state-transition.v1.schema.json`, then create a new Alembic migration from it with `backend/migration_contracts/expert_migration_contract.py`. The state snapshot and new migration must expose the same revision, parent revision, effective date, exact `(id, slug)` transition, source state, target state, reason, and downgrade policy.
3. Update the canonical fixture projection to `status: hidden` and `featured: false`. Keep `migration_snapshot` pointing to the frozen seed snapshot, and add `migration_chain` entries for that seed snapshot and the new state snapshot. Run the generic seed/state contract loader, the temporary PostgreSQL dry run, and every public boundary check before committing the reviewed files.
4. Assess repository history and published artifacts. Sensitive or unlawfully retained material may require a clean-history rewrite, a GitHub sensitive-data purge request, and release replacement. Record the reviewed scope and the replacement identifiers.
5. Notify known downstream redistributors when practical. Maintainers cannot recall independent forks, third-party caches, package mirrors, search indexes, or downstream copies; the notice should identify the affected slug or path and the clean replacement revision without repeating sensitive evidence.

The current five expert records remain published and featured. Their canonical fixture continues to point directly to the frozen 012 seed snapshot and has no `migration_chain`. This playbook does not create a state snapshot, tombstone migration, or hidden projection until a request has been verified.

Downstream redistributors are responsible for reviewing the current fixture, honoring applicable requests, and securing any rights their use requires.
