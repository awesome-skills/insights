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
_FAILED_TOOL_STATUSES = {"error", "failed", "failure", "cancelled", "canceled", "timeout", "timed_out"}
_METADATA_ONLY_JSON_REMOVE_PATHS = (
    "$.content",
    "$.data",
    "$.state.output",
    "$.state.error",
    "$.state.stderr",
    "$.state.message",
)


def _epoch_ms_to_iso(ms: int | None) -> str:
    if not ms:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def _stringify_part_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def _metadata_part_rows(cur: sqlite3.Cursor, sid: str, mid: str) -> list[str]:
    paths = ", ".join("?" for _ in _METADATA_ONLY_JSON_REMOVE_PATHS)
    try:
        return [row[0] for row in cur.execute(
            f"SELECT json_remove(data, {paths}) FROM part WHERE session_id=? AND message_id=? ORDER BY time_created ASC",
            (*_METADATA_ONLY_JSON_REMOVE_PATHS, sid, mid),
        ).fetchall()]
    except sqlite3.OperationalError:
        return [row[0] for row in cur.execute(
            "SELECT data FROM part WHERE session_id=? AND message_id=? ORDER BY time_created ASC",
            (sid, mid),
        ).fetchall()]


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

        part_rows_by_message: dict[str, list[str]] = {}
        if not metadata_only:
            part_rows = cur.execute(
                "SELECT message_id, data FROM part WHERE session_id=? ORDER BY time_created ASC",
                (sid,),
            ).fetchall()
            for mid, pdata_raw in part_rows:
                part_rows_by_message.setdefault(mid, []).append(pdata_raw)

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
            ctx = (tokens.get("input", 0) or 0) + (cache.get("read", 0) or 0) + (cache.get("write", 0) or 0)
            if ctx > meta.input_tokens:
                meta.input_tokens = ctx
            tout = tokens.get("output", 0) or 0
            meta.output_tokens += tout
            # Don't pass tokens through aggregate_message; OpenCode output is
            # message-level and some messages only contain patch/reasoning parts.
            tin = 0
            tout = 0

            counted = False
            text_chunks = []
            has_user_content = False
            part_rows_for_message = (
                _metadata_part_rows(cur, sid, mid) if metadata_only else part_rows_by_message.get(mid, [])
            )
            for pdata_raw in part_rows_for_message:
                try:
                    p = json.loads(pdata_raw)
                except (TypeError, json.JSONDecodeError):
                    continue
                ptype = p.get("type")
                if ptype == "text":
                    text_chunks.append(p.get("text", ""))
                    has_user_content = True
                elif ptype == "reasoning":
                    continue
                elif ptype == "file":
                    has_user_content = True
                    path = p.get("path") or p.get("filename")
                    if path:
                        meta.files_touched.append(path)
                    mime = str(p.get("mime") or p.get("media_type") or "")
                    if mime.startswith("image/"):
                        meta.image_inputs += 1
                elif ptype == "tool":
                    name = p.get("tool", "")
                    state = p.get("state", {}) or {}
                    cmd, fp = extract_tool_input(state.get("input"))
                    if fp:
                        meta.files_touched.append(fp)
                    status = str(state.get("status", "") or "")
                    is_err = status.lower() in _FAILED_TOOL_STATUSES
                    # A single OpenCode tool `input` can carry a multi-KB patch
                    # body. Cap it so full-transcript loads don't balloon RSS
                    # for sessions full of large apply_patch / Edit calls.
                    nm = NormalizedMessage(
                        role="tool_use",
                        timestamp=ts,
                        text=truncate(cmd, 600),
                        tool_name=name,
                        tokens_in=tin if not counted else 0,
                        tokens_out=tout if not counted else 0,
                        is_error=False,
                    )
                    counted = True
                    aggregate_message(meta, nm)
                    messages.append(nm)
                    if metadata_only:
                        if is_err:
                            result = NormalizedMessage(
                                role="tool_result",
                                timestamp=ts,
                                text="",
                                tool_name=name,
                                is_error=True,
                            )
                            aggregate_message(meta, result)
                            messages.append(result)
                        continue
                    if is_err:
                        result_value = (state.get("error") or state.get("output") or
                                        state.get("stderr") or state.get("message") or status)
                    else:
                        result_value = state.get("output")
                    result_text = _stringify_part_value(result_value)
                    if result_text:
                        result = NormalizedMessage(
                            role="tool_result",
                            timestamp=ts,
                            text=truncate(result_text, 1200),
                            tool_name=name,
                            is_error=is_err,
                        )
                        aggregate_message(meta, result)
                        messages.append(result)
                elif ptype == "subtask":
                    desc = p.get("description") or p.get("command") or p.get("prompt") or p.get("agent") or "subtask"
                    nm = NormalizedMessage(
                        role="tool_use",
                        timestamp=ts,
                        text=_stringify_part_value(desc),
                        tool_name="subtask",
                    )
                    aggregate_message(meta, nm)
                    messages.append(nm)
                elif ptype == "patch":
                    files = p.get("files") or []
                    if isinstance(files, list):
                        for f in files:
                            if isinstance(f, str) and f:
                                meta.files_touched.append(f)
                            elif isinstance(f, dict) and f.get("path"):
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
                    if has_user_content:
                        aggregate_message(meta, NormalizedMessage(role="user", timestamp=ts, text="[file attachment]"))

        finalize_metadata(meta)
        return ParsedSession(metadata=meta, messages=messages)
    finally:
        conn.close()
