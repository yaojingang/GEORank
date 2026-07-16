# Review Waivers

- OK: `True`
- Waivers: `0`
- Active: `0`
- Expired: `0`
- Invalid: `0`
- Covered gates: `none`
- Waiver candidates: `1`
- Open waiverable candidates: `1`
- Non-waivable boundaries: `0`

## Policy

- Blocker waivers allowed: `False`
- Minimum reason chars: `20`
- Expiry is required for every waiver.
- World-class evidence completion cannot be waived; it can only be proven by accepted ledger evidence.
- Review Studio gates: `architecture-maintainability, context-budget, intent-canvas, operations-loop, output-lab, permission-gates, permission-runtime, python-compat, registry-audit, release-notes, review-waivers, runtime-matrix, skill-atlas, trigger-lab, trust-report, world-class-evidence`
- Waiverable gates: `architecture-maintainability, context-budget, intent-canvas, operations-loop, output-lab, permission-gates, permission-runtime, python-compat, registry-audit, release-notes, runtime-matrix, skill-atlas, trigger-lab, trust-report`
- Non-waivable gates: `review-waivers, world-class-evidence`

## Waivers

- None

## Candidate Actions

| Gate | Status | Waiver | Risk | Evidence |
| --- | --- | --- | --- | --- |
| `output-lab` | `needs-reviewer-decision` | `true` | review pending 0; model-executed 0; output failures 0 | `reports/output_review_adjudication.md` |

### Output Lab

- gate: `output-lab`
- status: `needs-reviewer-decision`
- waiver allowed: `true`
- risk: review pending 0; model-executed 0; output failures 0
- evidence: `reports/output_review_adjudication.md`
- verification: `python3 scripts/yao.py review-waivers . --add-waiver --gate-key output-lab --reviewer "<reviewer>" --reason "Output Lab has pending human/provider evidence; accepted only for this bounded review scope." --expires-at 2027-07-16 --evidence reports/output_review_adjudication.md`
- world-class boundary: Does not count as provider, human, or public world-class completion evidence.

#### Required Review

- Reviewer confirms this release does not claim provider-backed or human-adjudicated output superiority.
- Reviewer names the release scope and expiry date.
- Reviewer links output_review_adjudication or output_execution evidence.

## Failures

- None

## Warnings

- None
