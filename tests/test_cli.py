"""CLI end-to-end tests."""
import io
import unittest
from contextlib import redirect_stdout, redirect_stderr

from loglens.cli import main
from tests.helpers import TempLogFile


SAMPLE = [
    "2024-01-15 10:00:00 INFO app: server started on port 8080",
    "2024-01-15 10:00:01 INFO app: user 1 logged in",
    "2024-01-15 10:00:02 INFO app: user 2 logged in",
    "2024-01-15 10:00:03 ERROR db: connection timeout for user 1",
    "2024-01-15 10:00:04 ERROR db: connection timeout for user 2",
    "2024-01-15 10:00:05 WARNING app: slow query took 1500ms",
    "2024-01-15 10:00:06 INFO app: user 3 logged in",
]


def run_cli(*args):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(list(args))
    return code, out.getvalue(), err.getvalue()


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmp = TempLogFile(SAMPLE)
        self.tmp.__enter__()

    def tearDown(self):
        self.tmp.__exit__(None, None, None)

    def test_summary(self):
        code, out, _ = run_cli("summary", self.tmp.path)
        self.assertEqual(code, 0)
        self.assertIn("lines", out)
        self.assertIn("errors", out)
        self.assertIn("2", out)  # 2 errors

    def test_clusters(self):
        code, out, _ = run_cli("clusters", self.tmp.path)
        self.assertEqual(code, 0)
        self.assertIn("template", out)
        # user N logged in should cluster (3 occurrences)
        self.assertIn("logged in", out)

    def test_errors(self):
        code, out, _ = run_cli("errors", self.tmp.path)
        self.assertEqual(code, 0)
        self.assertIn("timeout", out)

    def test_timeline(self):
        code, out, _ = run_cli("timeline", self.tmp.path, "--bucket", "minute")
        self.assertEqual(code, 0)
        self.assertIn("Timeline", out)

    def test_no_command(self):
        code, _, _ = run_cli()
        self.assertEqual(code, 1)

    def test_missing_file(self):
        code, out, _ = run_cli("summary", "/nonexistent/path.log")
        self.assertNotEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
