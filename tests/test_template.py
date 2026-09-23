"""Tests for message templating and clustering."""
import unittest

from loglens.parser import parse_lines
from loglens.template import (
    template_of, signature, cluster_entries, error_clusters,
)


class TestTemplateOf(unittest.TestCase):
    def test_numbers(self):
        self.assertEqual(template_of("user 123 logged in"), "user <NUM> logged in")

    def test_uuid(self):
        t = template_of("request abc12345-1234-5678-90ab-cdef01234567 completed")
        self.assertIn("<UUID>", t)
        self.assertNotIn("abc12345", t)

    def test_ip(self):
        t = template_of("connection from 192.168.1.100 refused")
        self.assertIn("<IP>", t)

    def test_url(self):
        t = template_of("fetching https://example.com/api/data")
        self.assertIn("<URL>", t)

    def test_path(self):
        t = template_of("reading /var/log/app.log failed")
        self.assertIn("<PATH>", t)

    def test_quoted(self):
        t = template_of('user said "hello world"')
        self.assertIn("<QSTR>", t)

    def test_version(self):
        t = template_of("running version 1.2.3")
        self.assertIn("<VERSION>", t)

    def test_date(self):
        t = template_of("date is 2024-01-15")
        self.assertIn("<DATE>", t)

    def test_same_template_different_values(self):
        t1 = template_of("user 1 logged in from 10.0.0.1")
        t2 = template_of("user 2 logged in from 10.0.0.2")
        self.assertEqual(t1, t2)

    def test_different_templates(self):
        t1 = template_of("user logged in")
        t2 = template_of("user logged out")
        self.assertNotEqual(t1, t2)


class TestSignature(unittest.TestCase):
    def test_stops_words(self):
        sig = signature("the user has logged in to the system")
        self.assertNotIn("the", sig.split())
        self.assertIn("user", sig.split())


class TestClustering(unittest.TestCase):
    def _entries(self, lines):
        return parse_lines(lines)

    def test_groups_similar(self):
        entries = self._entries([
            "2024-01-15 10:00:00 INFO app: user 1 logged in",
            "2024-01-15 10:00:01 INFO app: user 2 logged in",
            "2024-01-15 10:00:02 INFO app: user 3 logged in",
            "2024-01-15 10:00:03 INFO app: server started",
        ])
        clusters = cluster_entries(entries)
        self.assertEqual(len(clusters), 2)
        self.assertEqual(clusters[0].count, 3)  # login group

    def test_level_counts(self):
        entries = self._entries([
            "2024-01-15 10:00:00 ERROR app: request 1 failed",
            "2024-01-15 10:00:01 ERROR app: request 2 failed",
            "2024-01-15 10:00:02 INFO app: request 3 succeeded",
        ])
        clusters = cluster_entries(entries)
        # two templates: "request <NUM> failed" and "request <NUM> succeeded"
        self.assertEqual(len(clusters), 2)

    def test_error_clusters(self):
        entries = self._entries([
            "2024-01-15 10:00:00 ERROR app: db error 1",
            "2024-01-15 10:00:01 ERROR app: db error 2",
            "2024-01-15 10:00:02 INFO app: ok",
        ])
        clusters = cluster_entries(entries)
        errs = error_clusters(clusters)
        self.assertEqual(len(errs), 1)
        self.assertEqual(errs[0].count, 2)

    def test_empty(self):
        self.assertEqual(cluster_entries([]), [])

    def test_sorted_by_count(self):
        entries = self._entries([
            "2024-01-15 10:00:00 INFO a: event x",
            "2024-01-15 10:00:01 INFO a: event x",
            "2024-01-15 10:00:02 INFO a: event y",
        ])
        clusters = cluster_entries(entries)
        self.assertGreaterEqual(clusters[0].count, clusters[1].count)


if __name__ == "__main__":
    unittest.main()
