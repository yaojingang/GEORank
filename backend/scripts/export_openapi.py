"""Export or verify the canonical OpenAPI document for the TypeScript SDK."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.main import app  # noqa: E402


def canonical_document() -> str:
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Fail when the checked-in document differs.")
    mode.add_argument("--write", action="store_true", help="Write the current application schema.")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    current = canonical_document()
    if args.write:
        args.output.write_text(current, encoding="utf-8")
        print(f"Wrote OpenAPI document to {args.output}.")
        return 0

    try:
        checked_in = args.output.read_text(encoding="utf-8")
    except FileNotFoundError:
        checked_in = ""
    if checked_in != current:
        print(
            f"OpenAPI document is stale: {args.output}. "
            "Run backend/scripts/export_openapi.py --write packages/api-sdk/openapi.json from the repository root.",
            file=sys.stderr,
        )
        return 1

    print(f"OpenAPI document matches the application: {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
