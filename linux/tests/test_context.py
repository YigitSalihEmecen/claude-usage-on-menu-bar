"""Covers the transcript shape Claude Code writes and how the newest one is found."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from claude_usage import context
from claude_usage.context import ContextUsage


def assistant(tokens: dict, model="claude-opus-5", cwd="/home/me/dev/thing", sidechain=False) -> str:
    return json.dumps(
        {
            "type": "assistant",
            "cwd": cwd,
            "isSidechain": sidechain,
            "message": {"model": model, "usage": tokens},
        }
    )


class TokenCounting(unittest.TestCase):
    def test_cached_tokens_count_toward_the_window(self):
        usage = {
            "input_tokens": 2,
            "cache_creation_input_tokens": 511,
            "cache_read_input_tokens": 49496,
            "output_tokens": 208,
        }
        self.assertEqual(context.context_tokens(usage), 50_217)

    def test_missing_counters_are_zero(self):
        self.assertEqual(context.context_tokens({"input_tokens": 100}), 100)

    def test_unknown_fields_and_bad_values_are_ignored(self):
        usage = {"input_tokens": 1, "output_tokens": 2, "server_tool_use": {"x": 0}, "iterations": [{}]}
        self.assertEqual(context.context_tokens(usage), 3)
        self.assertEqual(context.context_tokens({"input_tokens": "9", "output_tokens": True}), 0)

    def test_context_limits_by_model(self):
        self.assertEqual(context.context_limit("claude-opus-5"), 1_000_000)
        self.assertEqual(context.context_limit("claude-sonnet-5"), 1_000_000)
        self.assertEqual(context.context_limit("claude-haiku-4-5-20251001"), 200_000)
        self.assertEqual(context.context_limit(None), 1_000_000)

    def test_fraction_is_clamped_and_rounded(self):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        self.assertEqual(ContextUsage("t", 50_009, 1_000_000, None, now).percent, 5)
        self.assertEqual(ContextUsage("t", 2_000_000, 1_000_000, None, now).fraction, 1)


class ReadingTranscripts(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.projects = Path(self._tmp.name)

    def write(self, project: str, name: str, lines: list[str], mtime: float | None = None) -> Path:
        directory = self.projects / project
        directory.mkdir(exist_ok=True)
        path = directory / name
        path.write_text("\n".join(lines) + "\n")
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def test_no_projects_directory(self):
        self.assertIsNone(context.current_session(self.projects / "missing"))

    def test_empty_projects_directory(self):
        self.assertIsNone(context.current_session(self.projects))

    def test_reads_the_last_assistant_turn(self):
        self.write(
            "-home-me-dev-thing",
            "a.jsonl",
            [
                assistant({"input_tokens": 1}),
                json.dumps({"type": "user", "message": {"content": "hi"}}),
                assistant({"input_tokens": 10, "cache_read_input_tokens": 90, "output_tokens": 5}),
                json.dumps({"type": "user", "message": {"content": "more"}}),
            ],
        )

        result = context.current_session(self.projects)

        self.assertEqual(result.tokens, 105)
        self.assertEqual(result.project, "thing")
        self.assertEqual(result.limit, 1_000_000)

    def test_follows_the_most_recently_modified_transcript(self):
        self.write("-p-old", "a.jsonl", [assistant({"input_tokens": 1}, cwd="/x/old")], mtime=1_000)
        self.write("-p-new", "b.jsonl", [assistant({"input_tokens": 2}, cwd="/x/new")], mtime=2_000)

        self.assertEqual(context.current_session(self.projects).project, "new")

    def test_sidechain_turns_are_skipped(self):
        self.write(
            "-p-thing",
            "a.jsonl",
            [assistant({"input_tokens": 500}), assistant({"input_tokens": 9_999}, sidechain=True)],
        )

        self.assertEqual(context.current_session(self.projects).tokens, 500)

    def test_haiku_uses_the_smaller_window(self):
        self.write("-p-thing", "a.jsonl", [assistant({"input_tokens": 1}, model="claude-haiku-4-5")])

        self.assertEqual(context.current_session(self.projects).limit, 200_000)

    def test_project_name_falls_back_to_the_directory_slug(self):
        line = json.dumps({"type": "assistant", "message": {"usage": {"input_tokens": 1}}})
        self.write("-home-me-dev-widget", "a.jsonl", [line])

        self.assertEqual(context.current_session(self.projects).project, "widget")

    def test_malformed_lines_are_ignored(self):
        self.write("-p-thing", "a.jsonl", [assistant({"input_tokens": 7}), "{not json", "garbage", "{}"])

        self.assertEqual(context.current_session(self.projects).tokens, 7)

    def test_a_transcript_with_no_assistant_turn_yields_nothing(self):
        self.write("-p-thing", "a.jsonl", [json.dumps({"type": "user"})])

        self.assertIsNone(context.current_session(self.projects))

    def test_large_tool_results_fall_through_to_the_deeper_window(self):
        padding = json.dumps({"type": "user", "message": {"content": "x" * (context.TAIL_WINDOW + 10)}})
        self.write("-p-thing", "a.jsonl", [assistant({"input_tokens": 42}), padding, padding])

        self.assertEqual(context.current_session(self.projects).tokens, 42)

    def test_tail_discards_the_partial_leading_record(self):
        # The window starts mid-line; that fragment must not be parsed as a turn.
        old = assistant({"input_tokens": 1})
        recent = assistant({"input_tokens": 77})
        path = self.write("-p-thing", "a.jsonl", [old, recent])
        text = context._tail(path, len(recent) + 5)

        self.assertEqual(context._last_assistant_turn(text)[0], 77)

    def test_multibyte_characters_split_by_the_window_do_not_break_decoding(self):
        line = json.dumps({"type": "user", "message": {"content": "é" * 50}}, ensure_ascii=False)
        path = self.write("-p-thing", "a.jsonl", [line, assistant({"input_tokens": 3})])

        self.assertIsNotNone(context._tail(path, len(assistant({"input_tokens": 3})) + 7))
        self.assertEqual(context.current_session(self.projects).tokens, 3)


if __name__ == "__main__":
    unittest.main()
