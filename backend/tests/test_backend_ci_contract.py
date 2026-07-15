import re
import unittest
from pathlib import Path

import yaml


WORKFLOW_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "backend-ci.yml"


class BackendCiContractTests(unittest.TestCase):
    def test_backend_ci_uses_one_dedicated_test_database(self) -> None:
        workflow = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
        job = workflow["jobs"]["test"]
        postgres_service = job["services"]["postgres"]
        service_database = postgres_service["env"]["POSTGRES_DB"]
        job_database = job["env"]["POSTGRES_DB"]
        health_database_match = re.search(r"(?:^|\s)-d\s+([^\s\"']+)", postgres_service["options"])

        self.assertIsNotNone(health_database_match)
        self.assertEqual(service_database, job_database)
        self.assertEqual(health_database_match.group(1), job_database)
        self.assertRegex(job_database, r"(?:^|[-_])(?:test|ci)(?:$|[-_0-9])")
        self.assertNotIn("TEST_DATABASE_URL", job["env"])
        test_step = next(step for step in job["steps"] if step["name"] == "Run backend test suite")
        self.assertEqual(test_step["run"], "python -m tests.run")


if __name__ == "__main__":
    unittest.main()
