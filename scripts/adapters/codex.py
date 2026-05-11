"""Codex adapter.

Session storage: ~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl
Each line is `{timestamp, type, payload}`. Types include `session_meta` and
`response_item` (messages, function_call, function_call_output).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

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
    truncate,
)


DEFAULT_ROOT = Path.home() / ".codex" / "sessions"


def _is_subagent_rollout(jsonl: Path) -> bool:
    """Codex stores sub-agent threads as their own rollout files. The first line
    is a session_meta event whose payload.source is `{"subagent": {...}}` when
    the rollout belongs to a spawned sub-agent. Counting these as top-level
    sessions double-counts the parent's work — same problem class as Claude
    Code's `subagents/` directory.
    """
    try:
        with jsonl.open("r", encoding="utf-8", errors="replace") as f:
            first = f.readline()
            if not first.strip():
                return False
            ev = json.loads(first)
    except (json.JSONDecodeError, OSError):
        return False
    if ev.get("type") != "session_meta":
        return False
    src = (ev.get("payload") or {}).get("source")
    if isinstance(src, dict) and "subagent" in src:
        return True
    if isinstance(src, str) and src == "subagent":
        return True
    return False


def list_sessions(since: datetime | None = None, root: Path = DEFAULT_ROOT) -> list[dict]:
    if not root.exists():
        return []
    out: list[dict] = []
    for jsonl in root.rglob("rollout-*.jsonl"):
        try:
            mtime = datetime.fromtimestamp(jsonl.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if since and mtime < since:
            continue
        if _is_subagent_rollout(jsonl):
            continue
        sid = jsonl.stem  # rollout-<ts>-<uuid>
        parts = sid.split("-")
        if len(parts) >= 6:
            uuid = "-".join(parts[-5:])
        else:
            uuid = sid
        out.append({
            "session_id": uuid,
            "path": str(jsonl),
            "project_path": "",
            "mtime": mtime.isoformat(),
        })
    out.sort(key=lambda r: r["mtime"], reverse=True)
    return out


def parse_session(path: str, metadata_only: bool = False) -> ParsedSession:
    p = Path(path)
    meta = SessionMetadata(session_id="", agent="codex")
    messages: list[NormalizedMessage] = DiscardList() if metadata_only else []
    first_ts = None
    last_ts = None

    with p.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            if len(raw) > MAX_JSONL_LINE_BYTES:
                continue
            raw = raw.strip()
            if not raw:
                continue
            try:
                ev = json.loads(raw)
            except json.JSONDecodeError:
                continue

            ts = ev.get("timestamp", "")
            if ts:
                if not first_ts:
                    first_ts = ts
                last_ts = ts

            etype = ev.get("type")
            payload = ev.get("payload", {}) or {}

            if etype == "session_meta":
                meta.session_id = payload.get("id", "") or meta.session_id
                meta.project_path = payload.get("cwd", "") or meta.project_path
                continue

            if etype == "response_item":
                _handle_response_item(payload, ts, meta, messages)
            elif etype == "turn_context":
                continue
            elif etype == "event_msg":
                ptype = payload.get("type", "")
                if "interrupt" in ptype.lower():
                    meta.user_interruptions += 1
                elif ptype == "token_count":
                    info = payload.get("info") or {}
                    total = info.get("total_token_usage") or {}
                    if total:
                        meta.input_tokens = (total.get("input_tokens") or 0) + (total.get("cached_input_tokens") or 0)
                        meta.output_tokens = total.get("output_tokens") or 0

    if not meta.session_id:
        meta.session_id = p.stem
    if first_ts:
        meta.start_time = first_ts
    if last_ts:
        meta.end_time = last_ts
    finalize_metadata(meta)
    return ParsedSession(metadata=meta, messages=messages)


def _handle_response_item(payload: dict, ts: str, meta: SessionMetadata, messages: list[NormalizedMessage]) -> None:
    ptype = payload.get("type")
    if ptype == "message":
        role = payload.get("role", "user")
        text_chunks = []
        for c in payload.get("content", []) or []:
            if isinstance(c, dict):
                t = c.get("text") or c.get("input_text") or c.get("output_text") or ""
                if t:
                    text_chunks.append(t)
        text = "\n".join(text_chunks).strip()
        if is_system_injection(role, text):
            return
        nm = NormalizedMessage(role=role, timestamp=ts, text=text)
        aggregate_message(meta, nm)
        messages.append(nm)
    elif ptype == "function_call":
        name = payload.get("name", "")
        args = payload.get("arguments", "")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        cmd, fp = extract_tool_input(args)
        if fp:
            meta.files_touched.append(fp)
        nm = NormalizedMessage(role="tool_use", timestamp=ts, text=cmd, tool_name=name)
        aggregate_message(meta, nm)
        messages.append(nm)
    elif ptype == "function_call_output":
        out = payload.get("output", "")
        if isinstance(out, dict):
            out = out.get("output") or out.get("content") or ""
        is_err = False
        if isinstance(out, str) and ("error" in out.lower()[:80] or "Error:" in out[:80]):
            is_err = True
        nm = NormalizedMessage(role="tool_result", timestamp=ts, text=truncate(str(out), 400), is_error=is_err)
        aggregate_message(meta, nm)
        messages.append(nm)
    elif ptype == "reasoning":
        # codex thinking - keep short summary
        summary = payload.get("summary", [])
        if isinstance(summary, list):
            text = " ".join(str(s.get("text", "")) if isinstance(s, dict) else str(s) for s in summary)
        else:
            text = str(summary)
        if text.strip():
            nm = NormalizedMessage(role="assistant", timestamp=ts, text=truncate(text, 300))
            aggregate_message(meta, nm)
            messages.append(nm)
