"""Development-time contracts for public expert seed and state migrations."""

from __future__ import annotations

import copy
import importlib.util
import json
import re
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


_REVISION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]{2,119}$")
_SNAPSHOT_PATH_PATTERN = re.compile(
    r"^backend/alembic/snapshots/[A-Za-z0-9_.-]+\.json$"
)


@dataclass(frozen=True)
class TombstoneTransitionPlan:
    fixture: dict[str, Any]
    snapshot: dict[str, Any]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _seed_runtime_projection(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": uuid.UUID(expert["id"]),
            "slug": expert["slug"],
            "display_name": expert["display_name"],
            "avatar_initials": expert["avatar_initials"],
            "title": expert["title"],
            "category": expert["category"],
            "specialty_label": expert["specialty_label"],
            "summary": expert["summary"],
            "consultation": expert["consultation"],
            "expertise": expert["expertise"],
            "keywords": expert["keywords"],
            "sort_order": expert["sort_order"],
            "is_featured": expert["is_featured"],
            "is_published": expert["is_published"],
        }
        for expert in snapshot["experts"]
    ]


def _normalized_state_operations(operations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "operation": operation["operation"],
            "id": str(operation["id"]),
            "slug": operation["slug"],
            "from_state": dict(operation["from_state"]),
            "to_state": dict(operation["to_state"]),
            "reason": operation["reason"],
        }
        for operation in operations
    ]


def _validate_tombstone_operations(operations: list[dict[str, Any]]) -> None:
    _require(bool(operations), "tombstone contract requires at least one operation")
    for operation in operations:
        _require(operation["operation"] == "set_publication_state", "invalid tombstone operation")
        _require(
            operation["from_state"] == {"is_published": True, "is_featured": True},
            "tombstone source state must be published and featured",
        )
        _require(
            operation["to_state"] == {"is_published": False, "is_featured": False},
            "tombstone target state must be hidden and unfeatured",
        )


def _fixture_runtime_projection(fixture: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": uuid.UUID(expert["id"]),
            "slug": expert["slug"],
            "display_name": expert["name"],
            "avatar_initials": expert["avatar_initials"],
            "title": expert["title"],
            "category": expert["category"],
            "specialty_label": expert["specialty_label"],
            "summary": expert["summary"],
            "consultation": expert["description"],
            "expertise": expert["expertise"],
            "keywords": expert["keywords"],
            "sort_order": expert["sort_order"],
            "is_featured": expert["featured"],
            "is_published": expert["status"] == "published",
        }
        for expert in fixture["experts"]
    ]


def validate_expert_migration_snapshot(module: Any, snapshot: dict[str, Any]) -> str:
    """Validate a loaded Alembic module against a seed or state snapshot."""

    _require(module.revision == snapshot["revision"], "migration revision drift")
    _require(module.down_revision == snapshot["down_revision"], "migration parent drift")

    if "experts" in snapshot:
        _require(hasattr(module, "SEED_DATE"), "seed migration must expose SEED_DATE")
        _require(hasattr(module, "EXPERT_SEEDS"), "seed migration must expose EXPERT_SEEDS")
        _require(
            module.SEED_DATE.date().isoformat() == snapshot["seed_date"],
            "seed effective date drift",
        )
        _require(
            module.EXPERT_SEEDS == _seed_runtime_projection(snapshot),
            "seed runtime projection drift",
        )
        return "seed"

    _require(
        snapshot.get("contract") == "expert-state-transition",
        "unknown expert migration snapshot contract",
    )
    _require(hasattr(module, "EFFECTIVE_DATE"), "state migration must expose EFFECTIVE_DATE")
    _require(hasattr(module, "STATE_TRANSITIONS"), "state migration must expose STATE_TRANSITIONS")
    _require(hasattr(module, "DOWNGRADE_POLICY"), "state migration must expose DOWNGRADE_POLICY")
    _validate_tombstone_operations(snapshot["operations"])
    effective_date = module.EFFECTIVE_DATE
    if isinstance(effective_date, date):
        effective_date = effective_date.isoformat()
    _require(effective_date == snapshot["effective_date"], "state effective date drift")
    _require(
        module.DOWNGRADE_POLICY == snapshot["downgrade_policy"],
        "state downgrade policy drift",
    )
    _require(
        _normalized_state_operations(module.STATE_TRANSITIONS)
        == _normalized_state_operations(snapshot["operations"]),
        "state transition drift",
    )
    return "state"


def validate_expert_fixture_projection(
    fixture: dict[str, Any],
    contracts: list[tuple[Any, dict[str, Any]]],
) -> None:
    """Apply a seed/state contract chain and compare its final public projection."""

    _require(bool(contracts), "expert migration contract chain must not be empty")
    kinds = [
        validate_expert_migration_snapshot(module, snapshot)
        for module, snapshot in contracts
    ]
    _require(kinds[0] == "seed", "expert migration chain must start with a seed")
    _require(all(kind == "state" for kind in kinds[1:]), "seed may appear only once")

    chain = fixture.get("migration_chain")
    if chain is None:
        _require(kinds == ["seed"], "state contracts require migration_chain metadata")
    else:
        _require(len(chain) == len(kinds), "migration_chain length drift")
        _require(
            [entry["kind"] for entry in chain] == kinds,
            "migration_chain kind order drift",
        )
        _require(
            chain[0]["snapshot"] == fixture["migration_snapshot"],
            "migration_chain seed must match migration_snapshot",
        )

    projected = copy.deepcopy(_seed_runtime_projection(contracts[0][1]))
    for _, snapshot in contracts[1:]:
        for operation in snapshot["operations"]:
            matches = [
                expert
                for expert in projected
                if str(expert["id"]) == str(operation["id"])
                and expert["slug"] == operation["slug"]
            ]
            _require(len(matches) == 1, "state transition must match exactly one id/slug pair")
            target = matches[0]
            _require(
                {
                    "is_published": target["is_published"],
                    "is_featured": target["is_featured"],
                }
                == operation["from_state"],
                "state transition source projection drift",
            )
            target.update(operation["to_state"])

    _require(
        projected == _fixture_runtime_projection(fixture),
        "canonical expert projection does not match migration chain",
    )


def _load_migration_module(repo_root: Path, revision: str) -> Any:
    _require(bool(_REVISION_PATTERN.fullmatch(revision)), "invalid migration revision")
    versions_directory = repo_root / "backend" / "alembic" / "versions"
    matches = []
    revision_pattern = re.compile(r'^revision\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
    for path in sorted(versions_directory.glob("*.py")):
        match = revision_pattern.search(path.read_text(encoding="utf-8"))
        if match and match.group(1) == revision:
            matches.append(path)
    _require(len(matches) == 1, f"expected one migration module for revision {revision}")
    spec = importlib.util.spec_from_file_location(f"expert_contract_{revision}", matches[0])
    _require(spec is not None and spec.loader is not None, "migration module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_expert_fixture_contracts(
    fixture: dict[str, Any],
    repo_root: Path,
) -> list[tuple[Any, dict[str, Any]]]:
    """Load the actual snapshots and migrations named by a canonical fixture."""

    repo_root = repo_root.resolve()
    entries = fixture.get(
        "migration_chain",
        [{"kind": "seed", "snapshot": fixture["migration_snapshot"]}],
    )
    _require(bool(entries), "migration chain must not be empty")
    _require(entries[0]["kind"] == "seed", "migration chain must start with seed")
    _require(all(entry["kind"] == "state" for entry in entries[1:]), "state must follow seed")

    contracts = []
    snapshot_paths: set[str] = set()
    revisions: set[str] = set()
    for entry in entries:
        relative_path = entry["snapshot"]
        _require(
            bool(_SNAPSHOT_PATH_PATTERN.fullmatch(relative_path)),
            "invalid migration snapshot path",
        )
        _require(relative_path not in snapshot_paths, "duplicate migration snapshot path")
        snapshot_paths.add(relative_path)
        snapshot_path = (repo_root / relative_path).resolve()
        _require(snapshot_path.is_relative_to(repo_root), "migration snapshot escapes repository")
        _require(snapshot_path.is_file(), "migration snapshot is missing")
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        revision = snapshot["revision"]
        _require(revision not in revisions, "duplicate migration revision")
        revisions.add(revision)
        module = _load_migration_module(repo_root, revision)
        kind = validate_expert_migration_snapshot(module, snapshot)
        _require(kind == entry["kind"], "migration chain kind does not match snapshot")
        contracts.append((module, snapshot))

    validate_expert_fixture_projection(fixture, contracts)
    return contracts


def build_tombstone_transition(
    fixture: dict[str, Any],
    *,
    target_slug: str,
    revision: str,
    down_revision: str,
    effective_date: str,
    snapshot_path: str,
    reason: str,
) -> TombstoneTransitionPlan:
    """Create an in-memory future tombstone fixture and state snapshot."""

    _require(bool(_REVISION_PATTERN.fullmatch(revision)), "invalid state revision")
    _require(bool(_REVISION_PATTERN.fullmatch(down_revision)), "invalid parent revision")
    _require(bool(_SNAPSHOT_PATH_PATTERN.fullmatch(snapshot_path)), "invalid state snapshot path")
    date.fromisoformat(effective_date)
    _require(len(reason.strip()) >= 10, "state transition reason is too short")

    mutated = copy.deepcopy(fixture)
    matches = [expert for expert in mutated["experts"] if expert["slug"] == target_slug]
    _require(len(matches) == 1, "target slug must identify exactly one expert")
    target = matches[0]
    _require(target["status"] == "published", "target expert must currently be published")
    _require(target["featured"] is True, "target expert must currently be featured")

    operation = {
        "operation": "set_publication_state",
        "id": target["id"],
        "slug": target["slug"],
        "from_state": {"is_published": True, "is_featured": True},
        "to_state": {"is_published": False, "is_featured": False},
        "reason": reason.strip(),
    }
    target["status"] = "hidden"
    target["featured"] = False
    chain = copy.deepcopy(mutated.get("migration_chain"))
    if chain is None:
        chain = [{"kind": "seed", "snapshot": mutated["migration_snapshot"]}]
    chain.append({"kind": "state", "snapshot": snapshot_path})
    mutated["migration_chain"] = chain

    snapshot = {
        "schema_version": 1,
        "contract": "expert-state-transition",
        "revision": revision,
        "down_revision": down_revision,
        "effective_date": effective_date,
        "downgrade_policy": "preserve_target_state",
        "operations": [operation],
    }
    return TombstoneTransitionPlan(fixture=mutated, snapshot=snapshot)


def render_state_migration(snapshot: dict[str, Any]) -> str:
    """Render a self-contained Alembic state migration for reviewed output."""

    _require(snapshot.get("contract") == "expert-state-transition", "invalid state contract")
    _validate_tombstone_operations(snapshot["operations"])
    operations_json = json.dumps(snapshot["operations"], ensure_ascii=False, separators=(",", ":"))
    return f'''"""Apply a reviewed public expert state transition."""

from datetime import date
import json
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = {snapshot["revision"]!r}
down_revision = {snapshot["down_revision"]!r}
branch_labels = None
depends_on = None

EFFECTIVE_DATE = date.fromisoformat({snapshot["effective_date"]!r})
DOWNGRADE_POLICY = {snapshot["downgrade_policy"]!r}
STATE_TRANSITIONS = json.loads({operations_json!r})
for _transition in STATE_TRANSITIONS:
    _transition["id"] = uuid.UUID(_transition["id"])


def _expert_profiles_table():
    return sa.table(
        "expert_profiles",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("slug", sa.String(length=120)),
        sa.column("is_published", sa.Boolean()),
        sa.column("is_featured", sa.Boolean()),
    )


def _apply(connection, transition, accepted_states, target_state):
    table = _expert_profiles_table()
    accepted_state_clause = sa.or_(*[
        sa.and_(
            table.c.is_published.is_(state["is_published"]),
            table.c.is_featured.is_(state["is_featured"]),
        )
        for state in accepted_states
    ])
    statement = (
        table.update()
        .where(table.c.id == transition["id"])
        .where(table.c.slug == transition["slug"])
        .where(accepted_state_clause)
        .values(
            is_published=target_state["is_published"],
            is_featured=target_state["is_featured"],
        )
    )
    result = connection.execute(statement)
    if result.rowcount != 1:
        raise RuntimeError("expert state transition must match exactly one id/slug/state row")


def upgrade():
    connection = op.get_bind()
    for transition in STATE_TRANSITIONS:
        _apply(
            connection,
            transition,
            [transition["from_state"], transition["to_state"]],
            transition["to_state"],
        )


def downgrade():
    connection = op.get_bind()
    for transition in STATE_TRANSITIONS:
        _apply(connection, transition, [transition["to_state"]], transition["to_state"])
'''
