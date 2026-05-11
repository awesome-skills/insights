"""OpenCode adapter.

Session storage: SQLite at ~/.local/share/opencode/opencode.db
Tables:
  session(id, project_id, directory, title, time_created, time_updated, ...)
  message(id, session_id, time_created, time_updated, data)
    data JSON: {role, time, summary, agent, model, tokens?, ...}
  part(id, message_id, session_id, time_created, time_updated, data)
    data JSON: {type: text|tool|reasoning|file|step-*|patch, ...}
"""
from __future__ import annotations

import json
import sqlite3
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


DEFAULT_DB = Path.home() / ".local" / "share" / "opencode" / "opencode.db"


def _epoch_ms_to_iso(ms: int | None) -> str:
    if not ms:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def list_sessions(since: datetime | None = None, db: Path = DEFAULT_DB) -> list[dict]:
    if not db.exists():
        return []
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cur = conn.cursor()
        q = "SELECT id, directory, title, time_created, time_updated FROM session"
        params: tuple = ()
        if since:
            q += " WHERE time_updated >= ?"
            params = (int(since.timestamp() * 1000),)
        q += " ORDER BY time_updated DESC"
        out: list[dict] = []
        for sid, directory, title, tc, tu in cur.execute(q, params):
            out.append({
                "session_id": sid,
                "path": str(db),  # opaque - use session_id for parse
                "project_path": directory or "",
                "title": title or "",
                "mtime": _epoch_ms_to_iso(tu or tc),
            })
        return out
    finally:
        conn.close()


def parse_session(path_or_db: str, session_id: str = "", metadata_only: bool = False) -> ParsedSession:
    """For OpenCode, path_or_db is the DB path and session_id identifies the row."""
    db = Path(path_or_db) if path_or_db else DEFAULT_DB
    if not session_id:
        raise ValueError("OpenCode parse_session requires session_id")
    if not db.exists():
        return ParsedSession(metadata=SessionMetadata(session_id=session_id, agent="opencode"), messages=[])

    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT id, directory, title, time_created, time_updated FROM session WHERE id=?",
            (session_id,),
        ).fetchone()
        if not row:
            return ParsedSession(metadata=SessionMetadata(session_id=session_id, agent="opencode"), messages=[])
        sid, directory, title, tc, tu = row
        meta = SessionMetadata(session_id=sid, agent="opencode")
        meta.project_path = directory or ""
        meta.start_time = _epoch_ms_to_iso(tc)
        meta.end_time = _epoch_ms_to_iso(tu)

        messages: list[NormalizedMessage] = DiscardList() if metadata_only else []

        # Iterate messages in time order
        msg_rows = cur.execute(
            "SELECT id, time_created, data FROM message WHERE session_id=? ORDER BY time_created ASC",
            (sid,),
        ).fetchall()

        for mid, mtc, mdata_raw in msg_rows:
            try:
                mdata = json.loads(mdata_raw)
            except json.JSONDecodeError:
                continue
            role = mdata.get("role", "")
            ts = _epoch_ms_to_iso(mtc)
            tokens = mdata.get("tokens") or {}
            # OpenCode `input` is fresh-input-this-turn only when cache.read > 0.
            # When cache.read == 0 it contains the full cumulative context, so summing
            # would double-count prior turns N times. Track max(input + cache.read)
            # — that's the peak context size seen, the only stable cross-turn metric.
            # Output is genuinely per-turn, so keep summing it.
            cache = tokens.get("cache") or {}
            ctx = (tokens.get("input", 0) or 0) + (cache.get("read", 0) or 0)
            if ctx > meta.input_tokens:
                meta.input_tokens = ctx
            tout = tokens.get("output", 0) or 0
            # Don't pass tin through aggregate_message — clear it.
            tin = 0

            # walk parts for this message
            part_rows = cur.execute(
                "SELECT data FROM part WHERE message_id=? ORDER BY time_created ASC",
                (mid,),
            ).fetchall()

            counted = False
            text_chunks = []
            for (pdata_raw,) in part_rows:
                try:
                    p = json.loads(pdata_raw)
                except json.JSONDecodeError:
                    continue
                ptype = p.get("type")
                if ptype == "text":
                    text_chunks.append(p.get("text", ""))
                elif ptype == "reasoning":
                    text_chunks.append(p.get("text", ""))
                elif ptype == "tool":
                    name = p.get("tool", "")
                    state = p.get("state", {}) or {}
                    cmd, fp = extract_tool_input(state.get("input"))
                    if fp:
                        meta.files_touched.append(fp)
                    status = state.get("status", "")
                    is_err = status not in ("completed", "")
                    nm = NormalizedMessage(
                        role="tool_use",
                        timestamp=ts,
                        text=cmd,
                        tool_name=name,
                        tokens_in=tin if not counted else 0,
                        tokens_out=tout if not counted else 0,
                        is_error=is_err,
                    )
                    counted = True
                    aggregate_message(meta, nm)
                    messages.append(nm)
                elif ptype == "patch":
                    files = p.get("files") or []
                    if isinstance(files, list):
                        for f in files:
                            if isinstance(f, dict) and f.get("path"):
                                meta.files_touched.append(f["path"])

            if role in ("user", "assistant"):
                text = "\n".join(text_chunks).strip()
                if text:
                    nm = NormalizedMessage(
                        role=role,
                        timestamp=ts,
                        text=truncate(text, 600),
                        tokens_in=tin if not counted else 0,
                        tokens_out=tout if not counted else 0,
                    )
                    aggregate_message(meta, nm)
                    messages.append(nm)
                elif role == "user" and not text_chunks:
                    # empty user message — skip
                    pass

        finalize_metadata(meta)
        return ParsedSession(metadata=meta, messages=messages)
    finally:
        conn.close()
