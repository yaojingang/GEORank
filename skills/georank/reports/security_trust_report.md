# Security Trust Report

- OK: `True`
- Scanned files: `13`
- Scripts: `1`
- Internal script modules: `0`
- Secret findings: `0`
- Network-capable scripts: `1`
- Network policy covered scripts: `1`
- Network policy missing scripts: `0`
- File-write scripts: `1`
- Permission approvals: `3 / 3`
- Permission approval gaps: `0`
- CLI help smoke checked: `1`
- CLI help smoke failures: `0`
- Interactive scripts: `1`
- Package hash scope: `source-contract-without-generated-reports`
- Package hash files: `13`
- Package SHA256: `c8aa3180fca3ca4100058bb08d75d70a1328b042c7e891e4b2cae76bd5af9a81`

## Failures

- None

## Warnings

- No dependency or lock file detected
- Interactive scripts require reviewer awareness: scripts/georank_client.py

## Dependency Evidence

- Files: `none`
- Pinned entries: `0`
- Unpinned entries: `0`

## Network Policy

- Policy file: `security/network_policy.json`
- Present: `True`
- Covered scripts: `1`
- Missing scripts: `none`
- Mismatches: `0`

## Permission Governance

- Policy file: `security/permission_policy.json`
- Present: `True`
- Required capabilities: `file_write, interactive, network`
- Approved capabilities: `file_write, interactive, network`
- Missing approvals: `none`
- Invalid approvals: `none`
- Expired approvals: `none`

## CLI Help Smoke

- Enabled: `True`
- Timeout seconds: `5.0`
- Checked scripts: `1`
- Passed scripts: `1`
- Failed scripts: `none`

## Script Surface

| Script | Interface | Declared | Argparse | Main Guard | Input | Network | File Write | Subprocess | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| scripts/georank_client.py | cli | True | True | True | True | True | True | False |  |
