# Runtime Permission Probes

Runtime permission probes verify that generated target adapters expose high-permission capabilities, make native-enforcement limits explicit, and link installer enforcement evidence when available.

## Summary

- OK: `True`
- Targets probed: `4`
- Passed: `4`
- Failed: `0`
- Native enforcement targets: `0`
- Explicit metadata fallbacks: `4`
- Installer enforcement source: `present`
- Installer-enforced targets: `4`
- Installer permission failures: `0`
- World-class native evidence ready: `False`
- Required capabilities: `file_write, interactive, network`

| Target | Status | Assurance | Native Enforcement | Metadata Fallback | Installer Enforcement | Residual Risk |
| --- | --- | --- | --- | --- | --- | --- |
| `openai` | `pass` | `metadata-fallback-explicit` | `False` | `True` | `pass` | Client-native permission enforcement is not provided by this target; installer or operator must honor metadata. |
| `claude` | `pass` | `metadata-fallback-explicit` | `False` | `True` | `pass` | Client-native permission enforcement is not provided by this target; installer or operator must honor metadata. |
| `generic` | `pass` | `metadata-fallback-explicit` | `False` | `True` | `pass` | Client-native permission enforcement is not provided by this target; installer or operator must honor metadata. |
| `vscode` | `pass` | `metadata-fallback-explicit` | `False` | `True` | `pass` | Client-native permission enforcement is not provided by this target; installer or operator must honor metadata. |

## Installer Enforcement

- Source: `reports/install_simulation.json`
- Source status: `present`
- Package dir matches probe: `True`

Installer enforcement means the package install simulation blocks missing capability approvals or target enforcement notes. It is supporting local distribution evidence, not proof of target-client native enforcement.

## Failures

- None

## Reviewer Note

A passing probe means the target contract is explicit and auditable. It does not claim that a host client enforces permissions natively.
