"""Tests for the multi-format log parser."""
import unittest

from loglens.parser import (
    parse_line, parse_lines, parse_file,
    _parse_iso, _parse_json_line, _parse_syslog_line,
    _parse_nginx_line, _parse_common_line,
)
from tests.helpers import TempLogFile


class TestTimestampParsing(unittest.TestCase):
    def test_iso_basic(self):
        dt = _parse_iso("2024-01-15 10:30:00")
        self.assertEqual(dt.year, 2024)
        self.assertEqual(dt.month, 1)
        self.assertEqual(dt.hour, 10)

    def test_iso_t_separator(self):
        dt = _parse_iso("2024-01-15T10:30:00")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.hour, 10)

    def test_iso_with_ms(self):
        dt = _parse_iso("2024-01-15 10:30:00.123")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.microsecond, 123000)

    def test_iso_z(self):
        dt = _parse_iso("2024-01-15T10:30:00Z")
        self.assertIsNotNone(dt)

    def test_invalid(self):
        self.assertIsNone(_parse_iso("not a date"))


class TestJsonParser(unittest.TestCase):
    def test_basic(self):
        line = '{"timestamp":"2024-01-15 10:00:00","level":"ERROR","message":"db connection failed"}'
        e = _parse_json_line(line)
        self.assertIsNotNone(e)
        self.assertEqual(e.level, "ERROR")
        self.assertEqual(e.message, "db connection failed")
        self.assertIsNotNone(e.timestamp)

    def test_alternate_keys(self):
        line = '{"time":"2024-01-15T10:00:00Z","severity":"warn","msg":"slow query"}'
        e = _parse_json_line(line)
        self.assertIsNotNone(e)
        self.assertEqual(e.level, "WARNING")
        self.assertEqual(e.message, "slow query")

    def test_epoch(self):
        line = '{"timestamp":1705312800,"level":"INFO","message":"started"}'
        e = _parse_json_line(line)
        self.assertIsNotNone(e)
        self.assertIsNotNone(e.timestamp)

    def test_not_json(self):
        self.assertIsNone(_parse_json_line("not json at all"))


class TestSyslogParser(unittest.TestCase):
    def test_basic(self):
        line = "Jan 15 10:30:00 myhost sshd[1234]: Accepted publickey for user"
        e = _parse_syslog_line(line)
        self.assertIsNotNone(e)
        self.assertEqual(e.source, "sshd[1234]")
        self.assertIn("Accepted", e.message)

    def test_no_pid(self):
        line = "Jan 15 10:30:00 myhost cron: job started"
        e = _parse_syslog_line(line)
        self.assertIsNotNone(e)
        self.assertEqual(e.source, "cron")


class TestNginxParser(unittest.TestCase):
    def test_access(self):
        line = '192.168.1.1 - - [15/Jan/2024:10:30:00 +0000] "GET /api/users HTTP/1.1" 200 1234'
        e = _parse_nginx_line(line)
        self.assertIsNotNone(e)
        self.assertEqual(e.level, "INFO")
        self.assertIn("GET", e.message)

    def test_500_is_error(self):
        line = '10.0.0.1 - - [15/Jan/2024:10:30:00 +0000] "POST /api HTTP/1.1" 500 0'
        e = _parse_nginx_line(line)
        self.assertEqual(e.level, "ERROR")

    def test_404_is_warning(self):
        line = '10.0.0.1 - - [15/Jan/2024:10:30:00 +0000] "GET /missing HTTP/1.1" 404 0'
        e = _parse_nginx_line(line)
        self.assertEqual(e.level, "WARNING")


class TestCommonParser(unittest.TestCase):
    def test_basic(self):
        line = "2024-01-15 10:30:00 INFO myapp: server started on port 8080"
        e = _parse_common_line(line)
        self.assertIsNotNone(e)
        self.assertEqual(e.level, "INFO")
        self.assertEqual(e.source, "myapp")
        self.assertIn("port 8080", e.message)

    def test_error_level(self):
        line = "2024-01-15 10:30:00 ERROR db: connection timeout after 30s"
        e = _parse_common_line(line)
        self.assertEqual(e.level, "ERROR")
        self.assertEqual(e.source, "db")


class TestAutoDetect(unittest.TestCase):
    def test_json_detected(self):
        e = parse_line('{"level":"INFO","message":"hi"}')
        self.assertEqual(e.level, "INFO")

    def test_common_detected(self):
        e = parse_line("2024-01-15 10:00:00 INFO app: hello")
        self.assertEqual(e.level, "INFO")
        self.assertEqual(e.source, "app")

    def test_generic_fallback(self):
        e = parse_line("something went wrong: error code 500 encountered")
        self.assertEqual(e.level, "ERROR")  # "error" keyword triggers ERROR

    def test_empty_line(self):
        e = parse_line("")
        self.assertEqual(e.message, "")

    def test_line_numbers(self):
        entries = parse_lines(["2024-01-15 10:00:00 INFO a: x", "2024-01-15 10:00:01 INFO b: y"])
        self.assertEqual(entries[0].line_no, 1)
        self.assertEqual(entries[1].line_no, 2)


class TestParseFile(unittest.TestCase):
    def test_file(self):
        with TempLogFile([
            "2024-01-15 10:00:00 INFO app: started",
            "2024-01-15 10:00:01 ERROR app: failed",
        ]) as f:
            entries = parse_file(f.path)
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[1].level, "ERROR")


if __name__ == "__main__":
    unittest.main()
