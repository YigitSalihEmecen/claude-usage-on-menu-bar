"""Covers both payload shapes Anthropic's usage endpoint returns."""

import json
import unittest
from datetime import datetime, timedelta, timezone

from claude_usage import formatting
from claude_usage.snapshot import UsageSnapshot, parse_timestamp


def decode(text: str) -> UsageSnapshot:
    return UsageSnapshot.from_payload(json.loads(text))


class UsagePayloadDecoding(unittest.TestCase):
    def test_legacy_flat_payload(self):
        snapshot = decode("""
        {
          "five_hour": { "utilization": 42, "resets_at": "2026-09-15T23:00:00Z" },
          "seven_day": { "utilization": 37.5, "resets_at": "2026-09-19T09:00:00Z" },
          "seven_day_opus": { "utilization": 12, "resets_at": "2026-09-19T09:00:00Z" },
          "seven_day_sonnet": null,
          "extra_usage": { "is_enabled": true, "monthly_limit": 50, "used_credits": 4.25, "utilization": 8.5 }
        }
        """)

        self.assertEqual(snapshot.session.percent, 42)
        self.assertAlmostEqual(snapshot.session.fraction, 0.42)
        self.assertEqual(snapshot.weekly.percent, 38)  # 37.5 rounds half up, as on macOS
        self.assertEqual([w.title for w in snapshot.scoped], ["Weekly · Opus"])
        self.assertTrue(snapshot.extra.is_enabled)
        self.assertEqual(snapshot.extra.used_credits, 4.25)
        self.assertIsNotNone(snapshot.session.resets_at)

    def test_limits_array_takes_precedence(self):
        snapshot = decode("""
        {
          "five_hour": { "utilization": 99, "resets_at": "2026-09-15T23:00:00Z" },
          "limits": [
            { "kind": "session", "group": "session", "percent": 9, "is_active": false },
            { "kind": "weekly_all", "group": "weekly", "percent": 55, "is_active": true,
              "resets_at": "2026-09-19T09:00:00Z" },
            { "kind": "weekly_scoped", "group": "weekly", "percent": 100, "is_active": true,
              "resets_at": "2026-09-19T09:00:00Z", "scope": { "model": { "display_name": "Fable" } } }
          ]
        }
        """)

        self.assertEqual(snapshot.session.percent, 9)
        self.assertFalse(snapshot.session.is_active)
        self.assertEqual(snapshot.weekly.percent, 55)
        self.assertEqual([w.title for w in snapshot.scoped], ["Weekly · Fable"])
        self.assertEqual([w.kind for w in snapshot.windows], ["session", "weekly", "weeklyScoped"])

    def test_unknown_kind_falls_back_to_group(self):
        snapshot = decode(
            '{ "limits": [ { "group": "session", "percent": 20 }, { "group": "mystery", "percent": 90 } ] }'
        )

        self.assertEqual(len(snapshot.windows), 1)
        self.assertEqual(snapshot.session.percent, 20)

    def test_fraction_is_clamped_and_empty_payload_is_safe(self):
        snapshot = decode('{ "five_hour": { "utilization": 160 }, "seven_day": { "utilization": -5 } }')

        self.assertEqual(snapshot.session.fraction, 1)
        self.assertEqual(snapshot.weekly.fraction, 0)
        self.assertIsNone(snapshot.session.resets_at)
        self.assertEqual(decode("{}").windows, [])

    def test_scoped_windows_without_a_model_name_get_distinct_ids(self):
        snapshot = decode("""
        { "limits": [ { "kind": "weekly_scoped", "percent": 1 }, { "kind": "weekly_scoped", "percent": 2 } ] }
        """)

        ids = [w.id for w in snapshot.scoped]
        self.assertEqual(len(set(ids)), 2)

    def test_garbage_values_do_not_crash(self):
        snapshot = decode('{ "five_hour": { "utilization": "lots", "resets_at": 12 }, "limits": [1, null] }')

        self.assertEqual(snapshot.session.fraction, 0)
        self.assertIsNone(snapshot.session.resets_at)

    def test_timestamp_variants(self):
        for stamp in (
            "2026-09-15T23:00:00Z",
            "2026-09-15T23:00:00.123Z",
            "2026-09-15T23:00:00.123456789Z",
            "2026-09-15T23:00:00+00:00",
            "2026-09-15T23:00:00",
        ):
            with self.subTest(stamp=stamp):
                parsed = parse_timestamp(stamp)
                self.assertEqual(
                    parsed.replace(microsecond=0), datetime(2026, 9, 15, 23, tzinfo=timezone.utc)
                )

    def test_invalid_timestamps_are_none(self):
        for stamp in (None, "", "yesterday", 5):
            self.assertIsNone(parse_timestamp(stamp))


class Formatting(unittest.TestCase):
    now = datetime(2026, 9, 15, 12, tzinfo=timezone.utc)

    def test_countdown(self):
        cases = [
            (8040, False, "2h 14m"),
            (8040, True, "2h14m"),
            (2880, False, "48m"),
            (30, False, "<1m"),
            (-10, False, "now"),
            (187_200, False, "2d 4h"),
        ]
        for seconds, compact, expected in cases:
            with self.subTest(seconds=seconds, compact=compact):
                target = self.now + timedelta(seconds=seconds)
                self.assertEqual(formatting.countdown(target, self.now, compact), expected)

    def test_relative(self):
        self.assertEqual(formatting.relative(self.now - timedelta(seconds=2), self.now), "just now")
        self.assertEqual(formatting.relative(self.now - timedelta(seconds=42), self.now), "42s ago")
        self.assertEqual(formatting.relative(self.now - timedelta(seconds=300), self.now), "5m ago")

    def test_compact_tokens(self):
        self.assertEqual(formatting.compact_tokens(1_000_000), "1M")
        self.assertEqual(formatting.compact_tokens(200_000), "200K")
        self.assertEqual(formatting.compact_tokens(1_500_000), "1.5M")
        self.assertEqual(formatting.compact_tokens(512), "512")

    def test_tokens_are_grouped(self):
        self.assertEqual(formatting.tokens(50_009), "50,009")

    def test_reset_time_names_the_weekday(self):
        text = formatting.reset_time(datetime(2026, 9, 18, 9, 5, tzinfo=timezone.utc))
        self.assertRegex(text, r"^\w{3} \d{1,2}:05")


if __name__ == "__main__":
    unittest.main()
