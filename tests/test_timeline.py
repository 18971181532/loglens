"""Tests for timeline aggregation and anomaly detection."""
import unittest
from datetime import datetime, timedelta

from loglens.parser import LogEntry
from loglens.timeline import build_timeline, detect_anomalies, time_range, _bucket_key


def _entry(ts, level="INFO", msg="x"):
    return LogEntry(timestamp=ts, level=level, source="app", message=msg, raw=msg)


class TestBucketKey(unittest.TestCase):
    def test_minute(self):
        dt = datetime(2024, 1, 15, 10, 30, 45)
        b = _bucket_key(dt, "minute")
        self.assertEqual(b.second, 0)
        self.assertEqual(b.minute, 30)

    def test_hour(self):
        dt = datetime(2024, 1, 15, 10, 30, 45)
        b = _bucket_key(dt, "hour")
        self.assertEqual(b.minute, 0)
        self.assertEqual(b.hour, 10)

    def test_5min(self):
        dt = datetime(2024, 1, 15, 10, 32, 0)
        b = _bucket_key(dt, "5min")
        self.assertEqual(b.minute, 30)


class TestBuildTimeline(unittest.TestCase):
    def test_basic(self):
        entries = [
            _entry(datetime(2024, 1, 15, 10, 0, 0)),
            _entry(datetime(2024, 1, 15, 10, 1, 0), "ERROR"),
            _entry(datetime(2024, 1, 15, 10, 2, 0), "WARNING"),
        ]
        tl = build_timeline(entries, bucket="minute")
        self.assertEqual(len(tl), 3)
        self.assertEqual(tl[0].total, 1)
        self.assertEqual(tl[1].error, 1)
        self.assertEqual(tl[2].warning, 1)

    def test_aggregation(self):
        entries = [
            _entry(datetime(2024, 1, 15, 10, 0, 0)),
            _entry(datetime(2024, 1, 15, 10, 0, 30)),
            _entry(datetime(2024, 1, 15, 10, 1, 0)),
        ]
        tl = build_timeline(entries, bucket="minute")
        self.assertEqual(len(tl), 2)
        self.assertEqual(tl[0].total, 2)

    def test_skip_no_timestamp(self):
        entries = [
            _entry(None),
            _entry(datetime(2024, 1, 15, 10, 0, 0)),
        ]
        tl = build_timeline(entries)
        self.assertEqual(len(tl), 1)

    def test_empty(self):
        self.assertEqual(build_timeline([]), [])

    def test_sorted(self):
        entries = [
            _entry(datetime(2024, 1, 15, 10, 5, 0)),
            _entry(datetime(2024, 1, 15, 10, 0, 0)),
        ]
        tl = build_timeline(entries, bucket="minute")
        self.assertLess(tl[0].time, tl[1].time)


class TestAnomalyDetection(unittest.TestCase):
    def test_spike_detected(self):
        # 7 quiet buckets then 1 spike
        base = datetime(2024, 1, 15, 10, 0, 0)
        entries = []
        for i in range(7):
            entries.append(_entry(base + timedelta(minutes=i)))
        # spike: 50 entries in one minute
        for _ in range(50):
            entries.append(_entry(base + timedelta(minutes=7)))
        tl = build_timeline(entries, bucket="minute")
        anomalies = detect_anomalies(tl, window=7, threshold=2.0)
        self.assertEqual(len(anomalies), 1)
        self.assertEqual(anomalies[0]["count"], 50)

    def test_no_anomaly_normal(self):
        base = datetime(2024, 1, 15, 10, 0, 0)
        entries = [_entry(base + timedelta(minutes=i)) for i in range(10)]
        tl = build_timeline(entries, bucket="minute")
        anomalies = detect_anomalies(tl)
        self.assertEqual(len(anomalies), 0)

    def test_too_few_buckets(self):
        entries = [_entry(datetime(2024, 1, 15, 10, i, 0)) for i in range(3)]
        tl = build_timeline(entries, bucket="minute")
        self.assertEqual(detect_anomalies(tl), [])


class TestTimeRange(unittest.TestCase):
    def test_range(self):
        entries = [
            _entry(datetime(2024, 1, 15, 10, 0, 0)),
            _entry(datetime(2024, 1, 15, 12, 0, 0)),
        ]
        first, last = time_range(entries)
        self.assertIn("10:00", first)
        self.assertIn("12:00", last)

    def test_no_timestamps(self):
        self.assertEqual(time_range([_entry(None)]), (None, None))


if __name__ == "__main__":
    unittest.main()
