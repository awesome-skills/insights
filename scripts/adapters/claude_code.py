"""Claude Code adapter.

Session storage: ~/.claude/projects/<encoded-cwd>/<session-uuid>.jsonl
One JSONL file per session; each line is a typed event (user/assistant/system/...).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from common import (  # type: ignore[import-not-found]
    DiscardList,
    MAX_JSONL_LINE_BYTES,
    NormalizedMessage,
    ParsedSession,
    SessionMetadata,
    aggregate_message,
    extract_tool_input,
    finalize_metadata,
    is_system_injection,
    parse_iso,  # noqa: F401
    truncate,
)


DEFAULT_ROOT = Path.home() / ".claude" / "projects"


def list_sessions(since: datetime | None = None, root: Path = DEFAULT_ROOT) -> list[dict]:
    """Return [{session_id, path, project_path, mtime}] for all top-level sessions.

    Skip sub-agent transcripts under `<session-dir>/subagents/*.jsonl` — those are
    fragments of a parent session and would otherwise be double-counted.
    """
    if not root.exists():
        return []
    results: list[dict] = []
    # Top-level pattern: <root>/<project-encoded>/<session-uuid>.jsonl
    for jsonl in root.glob("*/*.jsonl"):
        if "subagents" in jsonl.parts:
            continue
        try:
            mtime = datetime.fromtimestamp(jsonl.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if since and mtime < since:
            continue
        results.append({
            "session_id": jsonl.stem,
            "path": str(jsonl),
            "project_path": _decode_project(jsonl.parent.name),
            "mtime": mtime.isoformat(),
        })
    results.sort(key=lambda r: r["mtime"], reverse=True)
    return results


def _decode_project(encoded: str) -> str:
    # Claude Code stores the project directory as a flat name with `/` replaced
    # by `-`, e.g. `-Users-someone-code-myrepo` → `/Users/someone/code/myrepo`.
    if encoded.startswith("-"):
        return "/" + encoded[1:].replace("-", "/")
    return encoded


def parse_session(path: str, metadata_only: bool = False) -> ParsedSession:
    p = Path(path)
    session_id = p.stem
    meta = SessionMetadata(session_id=session_id, agent="claude-code")
    # Drop messages into a sink that discards them when only metadata is wanted.
    # Adapters still aggregate via the same path; we just avoid retaining N
    # NormalizedMessage dataclasses per session (1.2GB RSS on 308MB JSONL).
    messages: list[NormalizedMessage] = DiscardList() if metadata_only else []

    first_ts = None
    last_ts = None

    with p.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            # Drop oversized lines (single tool_result can be 300MB → 1GB+ RSS
            # after json.loads). The count is preserved via len(raw) heuristic
            # but the structured fields are skipped.
            if len(raw) > MAX_JSONL_LINE_BYTES:
                continue
            raw = raw.strip()
            if not raw:
                continue
            try:
                ev = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # Skip sub-agent / sidechain events — they belong to a child task and
            # would otherwise be double-counted into the parent session's totals.
            if ev.get("isSidechain"):
                continue

            etype = ev.get("type")
            ts = ev.get("timestamp", "")
            if ts:
                if not first_ts:
                    first_ts = ts
                last_ts = ts

            if not meta.project_path and ev.get("cwd"):
                meta.project_path = ev["cwd"]

            if etype == "user":
                _handle_user(ev, ts, meta, messages)
            elif etype == "assistant":
                _handle_assistant(ev, ts, meta, messages)
            elif etype == "system":
                # interruption hints (e.g., "User interrupted")
                txt = _extract_text(ev.get("message"))
                if "interrupted" in txt.lower():
                    meta.user_interruptions += 1
            # ignore: permission-mode, attachment, last-prompt, file-history-snapshot, queue-operation

    if first_ts:
        meta.start_time = first_ts
    if last_ts:
        meta.end_time = last_ts
    finalize_metadata(meta)
    return ParsedSession(metadata=meta, messages=messages)


_CMD_ARGS_RE = re.compile(r"<command-args>(.*?)</command-args>", re.DOTALL)


def _extract_real_user_text(raw: str) -> str:
    """Claude Code wraps slash-command turns as `<command-message>X</command-message>
    <command-name>/foo</command-name><command-args>actual user text</command-args>`.
    `is_system_injection` filters out the wrapper, but the user's real input
    lives inside `<command-args>` — pull it out so `first_prompt` and
    `user_message_count` reflect what the human typed.
    """
    if not raw or "<command-args>" not in raw:
        return ""
    m = _CMD_ARGS_RE.search(raw)
    if not m:
        return ""
    return m.group(1).strip()


def _handle_user(ev: dict, ts: str, meta: SessionMetadata, messages: list[NormalizedMessage]) -> None:
    msg = ev.get("message", {})
    content = msg.get("content")
    if isinstance(content, str):
        # Recover any user input wrapped inside <command-args> before filtering.
        recovered = _extract_real_user_text(content)
        if recovered:
            nm = NormalizedMessage(role="user", timestamp=ts, text=recovered)
            aggregate_message(meta, nm)
            messages.append(nm)
            return
        if is_system_injection("user", content):
            return
        nm = NormalizedMessage(role="user", timestamp=ts, text=content)
        aggregate_message(meta, nm)
        messages.append(nm)
        return
    if isinstance(content, list):
        for c in content:
            if not isinstance(c, dict):
                continue
            ctype = c.get("type")
            if ctype == "text":
                text = c.get("text", "")
                recovered = _extract_real_user_text(text)
                if recovered:
                    nm = NormalizedMessage(role="user", timestamp=ts, text=recovered)
                    aggregate_message(meta, nm)
                    messages.append(nm)
                    continue
                if is_system_injection("user", text):
                    continue
                nm = NormalizedMessage(role="user", timestamp=ts, text=text)
                aggregate_message(meta, nm)
                messages.append(nm)
            elif ctype == "tool_result":
                is_err = bool(c.get("is_error"))
                tres = c.get("content", "")
                if isinstance(tres, list):
                    tres = " ".join(str(x.get("text", "")) for x in tres if isinstance(x, dict))
                nm = NormalizedMessage(
                    role="tool_result",
                    timestamp=ts,
                    text=truncate(str(tres), 400),
                    is_error=is_err,
                )
                aggregate_message(meta, nm)
                messages.append(nm)


def _handle_assistant(ev: dict, ts: str, meta: SessionMetadata, messages: list[NormalizedMessage]) -> None:
    msg = ev.get("message", {})
    usage = msg.get("usage", {}) or {}
    tin = (usage.get("input_tokens", 0) or 0) + (usage.get("cache_creation_input_tokens", 0) or 0)
    tout = usage.get("output_tokens", 0) or 0

    content = msg.get("content", [])
    if isinstance(content, str):
        nm = NormalizedMessage(role="assistant", timestamp=ts, text=content, tokens_in=tin, tokens_out=tout)
        aggregate_message(meta, nm)
        messages.append(nm)
        return
    if not isinstance(content, list):
        return

    text_chunks = []
    counted_tokens = False
    for c in content:
        if not isinstance(c, dict):
            continue
        ctype = c.get("type")
        if ctype == "text":
            text_chunks.append(c.get("text", ""))
        elif ctype == "thinking":
            text_chunks.append(c.get("thinking", ""))
        elif ctype == "tool_use":
            name = c.get("name", "")
            cmd_text, fp = extract_tool_input(c.get("input"))
            if fp:
                meta.files_touched.append(fp)
            nm = NormalizedMessage(
                role="tool_use",
                timestamp=ts,
                text=cmd_text,
                tool_name=name,
                tokens_in=tin if not counted_tokens else 0,
                tokens_out=tout if not counted_tokens else 0,
            )
            counted_tokens = True
            aggregate_message(meta, nm)
            messages.append(nm)

    if text_chunks:
        nm = NormalizedMessage(
            role="assistant",
            timestamp=ts,
            text=truncate("\n".join(text_chunks), 600),
            tokens_in=tin if not counted_tokens else 0,
            tokens_out=tout if not counted_tokens else 0,
        )
        aggregate_message(meta, nm)
        messages.append(nm)


def _extract_text(payload) -> str:
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        c = payload.get("content")
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            return " ".join(_extract_text(x) for x in c)
    if isinstance(payload, list):
        return " ".join(_extract_text(x) for x in payload)
    return ""
