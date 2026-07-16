# Output Execution Runs

This report records how output-eval variants were produced and whether timing or token evidence is observed or estimated.

- Cases: `5`
- Variant runs: `10`
- Command executed: `10`
- Model executed: `0`
- Recorded fixtures: `0`
- Timing observed: `10`
- Token observed: `0`
- Token estimated: `10`
- Delta: `100.0`
- Gate pass: `True`

No model-executed runs are recorded yet.

Use `python3 scripts/yao.py output-exec --provider-runner openai` or `--runner-command` with a reviewed provider-backed runner to replace recorded fixtures with real model output evidence.

Command runner evidence is present. This proves the eval harness executed an external command, but it is not provider-backed model evidence unless the runner reports model metadata.

## Runs

| Case | Variant | Mode | Model | Duration ms | Tokens | Score | Status |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| ordinary-user-login | baseline | command | local-output-eval-runner | 30.3 | 12 | 0.0 | pass |
| ordinary-user-login | with_skill | command | local-output-eval-runner | 30.01 | 33 | 100.0 | pass |
| admin-change-preflight | baseline | command | local-output-eval-runner | 30.23 | 10 | 0.0 | pass |
| admin-change-preflight | with_skill | command | local-output-eval-runner | 32.4 | 48 | 100.0 | pass |
| destructive-admin-boundary | baseline | command | local-output-eval-runner | 32.94 | 12 | 0.0 | pass |
| destructive-admin-boundary | with_skill | command | local-output-eval-runner | 33.03 | 60 | 100.0 | pass |
| near-neighbor-geo-strategy | baseline | command | local-output-eval-runner | 37.97 | 15 | 0.0 | pass |
| near-neighbor-geo-strategy | with_skill | command | local-output-eval-runner | 32.03 | 30 | 100.0 | pass |
| file-backed-provider-change | baseline | command | local-output-eval-runner | 30.41 | 16 | 0.0 | pass |
| file-backed-provider-change | with_skill | command | local-output-eval-runner | 31.28 | 63 | 100.0 | pass |

## Next Fixes

- Keep recorded fixtures as reproducible baselines, but do not describe them as model-executed evidence.
- Use `scripts/provider_output_eval_runner.py` for provider-backed holdout cases when release confidence depends on real generation behavior.
- Compare timing, token cost, and assertion deltas before promoting a skill to governed reuse.
