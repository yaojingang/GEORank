import unittest

from typer.testing import CliRunner

from georank_cli import __version__
from georank_cli.main import app


class CliVersionTests(unittest.TestCase):
    def test_version_flag_reports_independent_cli_version(self):
        result = CliRunner().invoke(app, ["--version"])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout.strip(), f"georank-cli {__version__}")


if __name__ == "__main__":
    unittest.main()
