"""Gemini CLI adapter.

Session storage: ~/.gemini/tmp/<project-slug>/chats/session-*.json
Single JSON file per session with {sessionId, projectHash, startTime, lastUpdated, messages[]}.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from common import (  # type: ignore[import-not-found]
    DiscardList,
    NormalizedMessage,
    ParsedSession,
    SessionMetadata,
    aggregate_message,
    extract_tool_input,
    finalize_metadata,
    truncate,
)


DEFAULT_ROOT = Path.home() / ".gemini" / "tmp"

# Orchestrator-facing capabilities (see claude_code.py for the contract).
ROOT_KWARG = "root"
LIST_KWARGS: dict = {}


def is_subagent_session(ref: dict) -> bool:
    """Gemini has no subagent rollout concept."""
    return False


def parse_one(ref: dict, metadata_only: bool = False):
    """Uniform per-adapter parse entry; see claude_code.parse_one."""
    return parse_session(ref["path"], metadata_only=metadata_only)

# Refuse to load Gemini session files above this size into memory. Gemini stores
# inlineData (images) as base64 in the JSON, so individual files can balloon.
# 50MB covers the longest legitimate sessions we've seen.
_MAX_SESSION_BYTES = 50 * 1024 * 1024


def _safe_load_json(path: Path):
    """Return parsed JSON dict, or None if file is too big / unparseable / not a dict."""
    try:
        if path.stat().st_size > _MAX_SESSION_BYTES:
            return None
        doc = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(doc, dict):
        return None
    return doc


def list_sessions(since: datetime | None = None, root: Path = DEFAULT_ROOT) -> list[dict]:
    if not root.exists():
        return []
    out: list[dict] = []
    for jf in root.glob("*/chats/session-*.json"):
        try:
            mtime = datetime.fromtimestamp(jf.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if since and mtime < since:
            continue
        project_slug = jf.parent.parent.name
        # Default to file-stem id; only peek at JSON for canonical sessionId.
        # This is a per-file cost (~3ms each); see SKILL.md docs for trade-off.
        sid = jf.stem.replace("session-", "")
        doc = _safe_load_json(jf)
        if doc is not None:
            sid = doc.get("sessionId") or sid
        out.append({
            "session_id": sid,
            "path": str(jf),
            "project_path": project_slug,
            "mtime": mtime.isoformat(),
        })
    out.sort(key=lambda r: r["mtime"], reverse=True)
    return out


def parse_session(path: str, metadata_only: bool = False) -> ParsedSession:
    p = Path(path)
    fallback_sid = p.stem.replace("session-", "")
    doc = _safe_load_json(p)
    if doc is None:
        return ParsedSession(metadata=SessionMetadata(session_id=fallback_sid, agent="gemini"), messages=[])

    sid = doc.get("sessionId") or fallback_sid
    meta = SessionMetadata(session_id=sid, agent="gemini")
    meta.project_path = p.parent.parent.name
    meta.start_time = doc.get("startTime", "") or ""
    meta.end_time = doc.get("lastUpdated", "") or ""

    messages: list[NormalizedMessage] = DiscardList() if metadata_only else []
    for m in doc.get("messages", []) or []:
        if not isinstance(m, dict):
            continue
        mtype = m.get("type")
        ts = m.get("timestamp", "")
        if mtype == "info":
            continue
        if mtype == "user":
            text = _extract_user_text(m.get("content"))
            nm = NormalizedMessage(role="user", timestamp=ts, text=text)
            aggregate_message(meta, nm)
            messages.append(nm)
        elif mtype == "gemini":
            content = m.get("content", "")
            if isinstance(content, list):
                content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
            tokens = m.get("tokens") or {}
            # Gemini reports cumulative tokens (input includes prior context). Track the
            # max seen instead of summing so we don't N² overcount.
            tin = (tokens.get("input", 0) or 0) + (tokens.get("cached", 0) or 0)
            tout = tokens.get("output", 0) or 0
            if tin > meta.input_tokens:
                meta.input_tokens = tin
            if tout > meta.output_tokens:
                meta.output_tokens = tout
            # Don't pass tokens through aggregate_message — clear them out.
            tin = 0
            tout = 0
            counted = False
            for tc in m.get("toolCalls", []) or []:
                if not isinstance(tc, dict):
                    continue
                name = tc.get("name", "")
                cmd, fp = extract_tool_input(tc.get("args"))
                if fp:
                    meta.files_touched.append(fp)
                nm = NormalizedMessage(
                    role="tool_use",
                    timestamp=tc.get("timestamp", ts),
                    text=cmd,
                    tool_name=name,
                    tokens_in=tin if not counted else 0,
                    tokens_out=tout if not counted else 0,
                    is_error=(tc.get("status") not in (None, "success")),
                )
                counted = True
                aggregate_message(meta, nm)
                messages.append(nm)
            if content.strip():
                nm = NormalizedMessage(
                    role="assistant",
                    timestamp=ts,
                    text=truncate(content, 600),
                    tokens_in=tin if not counted else 0,
                    tokens_out=tout if not counted else 0,
                )
                aggregate_message(meta, nm)
                messages.append(nm)

    finalize_metadata(meta)
    return ParsedSession(metadata=meta, messages=messages)


def _extract_user_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict):
                t = c.get("text") or c.get("input_text") or ""
                if t:
                    parts.append(t)
        return "\n".join(parts)
    return ""
