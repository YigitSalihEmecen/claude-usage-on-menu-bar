"""Context-window usage for the Claude Code session you touched most recently.

Claude Code appends one JSON object per line to
``~/.claude/projects/<slug>/<session-id>.jsonl``. Each assistant line carries a
``usage`` block, and the last one describes the context the model just saw.
Nothing here talks to the network: this is all local and read-only.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .paths import claude_code_dir

#: Bytes read from the tail of a transcript on the first pass. Transcripts reach
#: tens of MB, so one is never read whole.
TAIL_WINDOW = 256 * 1024
#: Second pass, for when a few very large tool results fill the first.
DEEP_TAIL_WINDOW = 4 * 1024 * 1024


@dataclass(frozen=True)
class ContextUsage:
    #: Directory the session runs in, e.g. "claude-usage-on-menu-bar".
    project: str
    #: Tokens occupying the context window as of the last assistant turn.
    tokens: int
    #: Context window for the model that produced that turn.
    limit: int
    model: str | None
    #: Last write to the transcript, used to show staleness.
    updated_at: datetime

    @property
    def fraction(self) -> float:
        return min(max(self.tokens / self.limit, 0.0), 1.0)

    @property
    def percent(self) -> int:
        return int(self.fraction * 100 + 0.5)


def context_limit(model: str | None) -> int:
    """Context window by model. Unknown models get the current generation's 1M."""
    if model and "haiku" in model:
        return 200_000
    return 1_000_000


def context_tokens(usage: dict) -> int:
    """Everything the model saw or produced on a turn. Cached tokens still count."""
    return sum(
        value
        for key in (
            "input_tokens",
            "cache_creation_input_tokens",
            "cache_read_input_tokens",
            "output_tokens",
        )
        if isinstance(value := usage.get(key), int) and not isinstance(value, bool)
    )


def current_session(projects_dir: Path | None = None) -> ContextUsage | None:
    """Reads the most recently modified transcript across every project.

    Returns None when Claude Code has never run here, or the tail held no usable
    assistant turn. Blocking: call it off the UI thread.
    """
    transcript = _newest_transcript(projects_dir or claude_code_dir() / "projects")
    if transcript is None:
        return None
    path, modified = transcript

    try:
        size = path.stat().st_size
    except OSError:
        return None

    for window in (TAIL_WINDOW, DEEP_TAIL_WINDOW):
        text = _tail(path, window)
        if text is None:
            return None
        turn = _last_assistant_turn(text)
        if turn is not None:
            tokens, model, cwd = turn
            return ContextUsage(
                project=Path(cwd).name if cwd else _project_name(path),
                tokens=tokens,
                limit=context_limit(model),
                model=model,
                updated_at=modified,
            )
        # Nothing in a window that already covered the whole file won't appear later.
        if size <= window:
            break
    return None


def _newest_transcript(projects_dir: Path) -> tuple[Path, datetime] | None:
    newest: tuple[Path, float] | None = None
    try:
        projects = [p for p in projects_dir.iterdir() if not p.name.startswith(".")]
    except OSError:
        return None

    for project in projects:
        try:
            files = list(project.glob("*.jsonl"))
        except OSError:
            continue
        for file in files:
            try:
                modified = file.stat().st_mtime
            except OSError:
                continue
            if newest is None or modified > newest[1]:
                newest = (file, modified)

    if newest is None:
        return None
    return newest[0], datetime.fromtimestamp(newest[1], tz=timezone.utc)


def _project_name(transcript: Path) -> str:
    # Slug form: "-home-me-dev-thing". The trailing segment is the closest we can
    # get to a directory name without a `cwd` to read.
    slug = transcript.parent.name
    return next((part for part in reversed(slug.split("-")) if part), slug)


def _tail(path: Path, size: int) -> str | None:
    """Last `size` bytes, trimmed forward to the first newline so the leading
    partial record is discarded."""
    try:
        with open(path, "rb") as handle:
            end = handle.seek(0, os.SEEK_END)
            offset = max(end - size, 0)
            handle.seek(offset)
            data = handle.read()
    except OSError:
        return None

    if offset > 0:
        newline = data.find(b"\n")
        data = data[newline + 1 :] if newline >= 0 else b""
    return data.decode("utf-8", errors="replace")


def _last_assistant_turn(text: str) -> tuple[int, str | None, str | None] | None:
    """Scans backwards for the newest main-thread assistant turn. Sidechain lines
    are subagent traffic and do not occupy the session's own context."""
    for line in reversed(text.splitlines()):
        if not line.startswith("{"):
            continue
        try:
            record = json.loads(line)
        except ValueError:
            continue
        if not isinstance(record, dict) or record.get("type") != "assistant":
            continue
        if record.get("isSidechain") is True:
            continue
        message = record.get("message")
        usage = message.get("usage") if isinstance(message, dict) else None
        if not isinstance(usage, dict):
            continue
        model = message.get("model")
        cwd = record.get("cwd")
        return (
            context_tokens(usage),
            model if isinstance(model, str) else None,
            cwd if isinstance(cwd, str) else None,
        )
    return None
