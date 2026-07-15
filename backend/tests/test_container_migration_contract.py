from pathlib import Path
import unittest

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


class ContainerMigrationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compose = yaml.safe_load(
            (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        )

    def test_compose_has_one_migration_owner(self):
        services = self.compose["services"]
        self.assertIn("migrate", services)
        self.assertEqual(
            services["migrate"]["command"],
            ["python", "-m", "app.scripts.migrate"],
        )
        self.assertEqual(
            services["migrate"]["depends_on"]["postgres"]["condition"],
            "service_healthy",
        )
        self.assertNotIn("env_file", services["migrate"])
        self.assertEqual(
            set(services["migrate"]["environment"]),
            {
                "DEBUG",
                "POSTGRES_HOST",
                "POSTGRES_PORT",
                "POSTGRES_DB",
                "POSTGRES_USER",
                "POSTGRES_PASSWORD",
            },
        )

    def test_every_database_runtime_waits_for_successful_migration(self):
        services = self.compose["services"]
        for service_name in ("api", "worker", "beat", "crawler"):
            with self.subTest(service=service_name):
                self.assertEqual(
                    services[service_name]["depends_on"]["migrate"]["condition"],
                    "service_completed_successfully",
                )

    def test_frontend_waits_for_api_healthcheck(self):
        services = self.compose["services"]
        self.assertIn("healthcheck", services["api"])
        self.assertEqual(
            services["frontend"]["depends_on"]["api"]["condition"],
            "service_healthy",
        )

    def test_postgres_healthcheck_uses_configured_database_and_user(self):
        command = self.compose["services"]["postgres"]["healthcheck"]["test"][-1]
        self.assertIn("$${POSTGRES_USER}", command)
        self.assertIn("$${POSTGRES_DB}", command)

    def test_compose_services_remain_project_isolated(self):
        for service_name, service in self.compose["services"].items():
            with self.subTest(service=service_name):
                self.assertNotIn("container_name", service)

    def test_production_startup_paths_do_not_create_schema_from_orm_metadata(self):
        for relative_path in (
            "backend/app/main.py",
            "backend/app/scripts/seed.py",
        ):
            with self.subTest(path=relative_path):
                source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
                self.assertNotIn("metadata.create_all", source)

    def test_api_image_default_command_does_not_enable_reload(self):
        dockerfile = (REPO_ROOT / "backend/Dockerfile").read_text(encoding="utf-8")
        command_line = next(
            line for line in dockerfile.splitlines() if line.startswith("CMD ")
        )
        self.assertNotIn("--reload", command_line)

    def test_all_backend_images_use_read_only_schema_preflight_entrypoint(self):
        entrypoint = (
            REPO_ROOT / "backend/docker-entrypoint.sh"
        ).read_text(encoding="utf-8")
        self.assertIn("app.scripts.migrate --check", entrypoint)
        for dockerfile_name in ("Dockerfile", "Dockerfile.crawler"):
            dockerfile = (REPO_ROOT / "backend" / dockerfile_name).read_text(
                encoding="utf-8"
            )
            with self.subTest(dockerfile=dockerfile_name):
                self.assertIn('ENTRYPOINT ["/usr/local/bin/georank-entrypoint"]', dockerfile)

    def test_ci_runs_real_container_migration_contract(self):
        script_path = REPO_ROOT / "scripts/check-container-migration-bootstrap.sh"
        self.assertTrue(script_path.is_file())
        script = script_path.read_text(encoding="utf-8")
        for contract_marker in (
            "EFFECTIVE_PRODUCTION_COMPOSE",
            "FRESH_DATABASE",
            "DIRECT_ENTRYPOINT_FAIL_CLOSED",
            "CONCURRENT_EMPTY_DATABASE",
            "IDEMPOTENT_RESTART",
            "LEGACY_FAIL_CLOSED",
            "MIGRATION_FAILURE_BLOCKS_API",
        ):
            with self.subTest(marker=contract_marker):
                self.assertIn(contract_marker, script)

        workflow = (REPO_ROOT / ".github/workflows/backend-ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("scripts/check-container-migration-bootstrap.sh", workflow)
        self.assertIn('compose_file="$repo_root/docker-compose.yml"', script)
        self.assertIn('contract_override="$repo_root/docker-compose.migration-contract.yml"', script)


if __name__ == "__main__":
    unittest.main()
