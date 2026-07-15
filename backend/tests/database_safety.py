import re
from collections.abc import MutableMapping

from sqlalchemy import text
from sqlalchemy.engine import make_url


_PROTECTED_DATABASE_NAMES = {"georank", "postgres", "template0", "template1"}
_TEST_DATABASE_MARKER = re.compile(r"(?:^|[-_])(?:test|ci)(?:$|[-_0-9])", re.IGNORECASE)


def bootstrap_test_database_environment(
    environment: MutableMapping[str, str],
) -> tuple[str, str]:
    """Validate TEST_DATABASE_URL, then map it onto the app's normal DB settings."""
    explicit_url = environment.get("TEST_DATABASE_URL", "").strip()
    if not explicit_url:
        raise RuntimeError("TEST_DATABASE_URL is required for test database bootstrapping")

    database_url, database_name = resolve_test_database(
        default_database_url=explicit_url,
        configured_database_name=None,
        explicit_test_database_url=explicit_url,
    )
    parsed_url = make_url(database_url)
    if parsed_url.drivername != "postgresql+asyncpg":
        raise RuntimeError("TEST_DATABASE_URL must use PostgreSQL")
    if parsed_url.query:
        raise RuntimeError("TEST_DATABASE_URL query parameters are not supported by test bootstrapping")
    if not parsed_url.host or not parsed_url.username or parsed_url.password is None:
        raise RuntimeError("TEST_DATABASE_URL must include host, username, and password")

    mapped_values = {
        "POSTGRES_HOST": parsed_url.host,
        "POSTGRES_PORT": str(parsed_url.port or 5432),
        "POSTGRES_DB": database_name,
        "POSTGRES_USER": parsed_url.username,
        "POSTGRES_PASSWORD": parsed_url.password,
    }
    environment.update(mapped_values)
    return database_url, database_name


def resolve_test_database(
    *,
    default_database_url: str,
    configured_database_name: str | None,
    explicit_test_database_url: str | None = None,
) -> tuple[str, str]:
    explicit_url = (explicit_test_database_url or "").strip()
    configured_name = (configured_database_name or "").strip()
    if not explicit_url and not configured_name:
        raise RuntimeError("Database integration tests require an explicitly configured dedicated test database")

    database_url = explicit_url or default_database_url
    parsed_url = make_url(database_url)
    database_name = (parsed_url.database or "").strip()
    if not database_name or database_name.lower() in _PROTECTED_DATABASE_NAMES:
        raise RuntimeError("Database integration tests require a dedicated test database")

    if not _TEST_DATABASE_MARKER.search(database_name):
        raise RuntimeError("The resolved database name must include a distinct test or ci marker")

    if not explicit_url and database_name != configured_name:
        raise RuntimeError("POSTGRES_DB must identify the database used by the integration test URL")

    if parsed_url.drivername in {"postgres", "postgresql"}:
        parsed_url = parsed_url.set(drivername="postgresql+asyncpg")
    if parsed_url.drivername == "postgresql+asyncpg" and parsed_url.port is None:
        parsed_url = parsed_url.set(port=5432)

    return parsed_url.render_as_string(hide_password=False), database_name


async def verify_test_database_engine(engine, database_url: str, database_name: str) -> None:
    engine_url = engine.url.render_as_string(hide_password=False)
    if engine_url != database_url:
        raise RuntimeError("The integration-test engine does not use the resolved test database URL")
    async with engine.connect() as connection:
        connected_database = await connection.scalar(text("SELECT current_database()"))
    if connected_database != database_name:
        raise RuntimeError("The integration-test connection reached an unexpected database")
