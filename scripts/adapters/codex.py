"""Codex adapter.

Session storage: ~/.codex/sessions/YYYY/MM/DD/rollout-<ts>-<uuid>.jsonl
Each line is `{timestamp, type, payload}`. Types include `session_meta`,
`turn_context`, `event_msg`, and `response_item` payloads such as messages,
function calls, custom tool calls, and web searches.
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
    extract_patch_paths,
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
    call_tools: dict[str, str] = {}
    call_result_ids: set[str] = set()
    counted_event_tools: set[str] = set()
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
                meta.cli_version = payload.get("cli_version", "") or meta.cli_version
                meta.model_provider = payload.get("model_provider", "") or meta.model_provider
                meta.originator = payload.get("originator", "") or meta.originator
                meta.memory_mode = _stringify(payload.get("memory_mode")) or meta.memory_mode
                meta.thread_source = _stringify(payload.get("thread_source")) or meta.thread_source
                meta.agent_role = _stringify(payload.get("agent_role")) or meta.agent_role
                continue

            if etype == "response_item":
                _handle_response_item(payload, ts, meta, messages, call_tools, call_result_ids, counted_event_tools)
            elif etype == "turn_context":
                _handle_turn_context(payload, meta)
            elif etype == "event_msg":
                _handle_event_msg(payload, ts, meta, messages, call_result_ids, counted_event_tools)
            elif etype == "compacted":
                meta.compactions += 1

    if not meta.session_id:
        meta.session_id = p.stem
    if first_ts:
        meta.start_time = first_ts
    if last_ts:
        meta.end_time = last_ts
    finalize_metadata(meta)
    return ParsedSession(metadata=meta, messages=messages)


def _stringify(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)


def _extract_output_text(value) -> str:
    if isinstance(value, dict):
        return _stringify(value.get("output") or value.get("content") or value)
    return _stringify(value)


def _looks_error(output: str, status: str = "") -> bool:
    status_l = (status or "").lower()
    if status_l and status_l not in {"completed", "success", "succeeded"}:
        return True
    text = output or ""
    try:
        parsed = json.loads(text)
    except (TypeError, json.JSONDecodeError):
        parsed = None
    if isinstance(parsed, dict):
        metadata = parsed.get("metadata") or {}
        if isinstance(metadata, dict):
            exit_code = metadata.get("exit_code")
            if isinstance(exit_code, int):
                return exit_code != 0
    head = text[:240]
    if "Process exited with code " in head:
        try:
            code_text = head.split("Process exited with code ", 1)[1].split()[0]
            return int(code_text) != 0
        except (ValueError, IndexError):
            return True
    # Anchor each marker to a line *start* (after stripping leading whitespace) so
    # successful build output that happens to mention "error: " or "fatal: " mid-
    # sentence — "1 error: unused", "Note: fatal: was expected" — doesn't get
    # mis-classified as a tool failure and pollute the friction histogram.
    head_l = head.lower()
    explicit_failure_line_starts = (
        "traceback (most recent call last)",
        "command failed",
        "failed with exit code",
        "error: ",
        "fatal: ",
        "exception:",
    )
    for line in head_l.splitlines():
        stripped = line.lstrip()
        if any(stripped.startswith(marker) for marker in explicit_failure_line_starts):
            return True
    return False


def _handle_turn_context(payload: dict, meta: SessionMetadata) -> None:
    meta.model = payload.get("model", "") or meta.model
    meta.reasoning_effort = payload.get("effort", "") or meta.reasoning_effort
    meta.approval_policy = payload.get("approval_policy", "") or meta.approval_policy
    sandbox = payload.get("sandbox_policy")
    if isinstance(sandbox, dict):
        meta.sandbox_policy = sandbox.get("type", "") or _stringify(sandbox) or meta.sandbox_policy
    else:
        meta.sandbox_policy = _stringify(sandbox) or meta.sandbox_policy
    mode = payload.get("collaboration_mode")
    if isinstance(mode, dict):
        meta.collaboration_mode = mode.get("mode", "") or _stringify(mode) or meta.collaboration_mode
    else:
        meta.collaboration_mode = _stringify(mode) or meta.collaboration_mode


def _handle_event_msg(
    payload: dict,
    ts: str,
    meta: SessionMetadata,
    messages: list[NormalizedMessage],
    call_result_ids: set[str],
    counted_event_tools: set[str],
) -> None:
    ptype = payload.get("type", "")
    ptype_l = ptype.lower()
    if "interrupt" in ptype_l or ptype == "turn_aborted":
        meta.user_interruptions += 1
    elif ptype == "context_compacted":
        meta.compactions += 1
    elif ptype == "thread_rolled_back":
        meta.rollbacks += 1
    elif ptype == "task_started":
        meta.uses_task_agent = True
    elif ptype == "task_complete":
        meta.uses_task_agent = True
    elif ptype == "token_count":
        info = payload.get("info") or {}
        total = info.get("total_token_usage") or {}
        if total:
            meta.input_tokens = (total.get("input_tokens") or 0) + (total.get("cached_input_tokens") or 0)
            meta.output_tokens = total.get("output_tokens") or 0
            meta.reasoning_output_tokens = total.get("reasoning_output_tokens") or meta.reasoning_output_tokens
    elif ptype == "patch_apply_end":
        if payload.get("success"):
            meta.patches_applied += 1
        else:
            meta.patches_failed += 1
        changes = payload.get("changes")
        if isinstance(changes, dict):
            for path, detail in changes.items():
                if path:
                    meta.files_touched.append(str(path))
                if isinstance(detail, dict):
                    for moved_path in (detail.get("move_path"), detail.get("new_path"), detail.get("to")):
                        if moved_path:
                            meta.files_touched.append(str(moved_path))
                    _count_diff_lines(meta, detail.get("unified_diff") or "")
        out = payload.get("stdout") or payload.get("stderr") or payload.get("status") or ""
        if out and payload.get("call_id", "") not in call_result_ids:
            nm = NormalizedMessage(
                role="tool_result",
                timestamp=ts,
                text=truncate(str(out), 400),
                tool_name="apply_patch",
                is_error=not bool(payload.get("success", False)),
            )
            aggregate_message(meta, nm)
            messages.append(nm)
    elif ptype == "web_search_end":
        meta.uses_web_search = True
        if "web_search" not in counted_event_tools:
            counted_event_tools.add("web_search")
            nm = NormalizedMessage(role="tool_use", timestamp=ts, text="", tool_name="web_search")
            aggregate_message(meta, nm)
            messages.append(nm)
    elif ptype == "mcp_tool_call_end":
        meta.uses_mcp = True
        meta.mcp_calls += 1
        invocation = payload.get("invocation") or {}
        server = invocation.get("server") or invocation.get("server_name") or "mcp"
        tool = invocation.get("tool") or invocation.get("name") or "tool"
        name = f"mcp::{server}::{tool}"
        result = payload.get("result") or {}
        is_error = False
        result_text = ""
        if isinstance(result, dict):
            ok = result.get("Ok") or result.get("ok")
            if isinstance(ok, dict):
                is_error = bool(ok.get("isError") or ok.get("is_error"))
                result_text = _extract_mcp_text(ok)
            elif "Err" in result or "error" in result:
                is_error = True
                result_text = _stringify(result.get("Err") or result.get("error") or result)
        nm = NormalizedMessage(role="tool_use", timestamp=ts, text="", tool_name=name)
        aggregate_message(meta, nm)
        messages.append(nm)
        if result_text or is_error:
            result_msg = NormalizedMessage(
                role="tool_result",
                timestamp=ts,
                text=truncate(result_text or "MCP tool reported an error", 400),
                tool_name=name,
                is_error=is_error,
            )
            aggregate_message(meta, result_msg)
            messages.append(result_msg)
    elif ptype in {"user_message", "agent_message"}:
        meta.image_inputs += len(payload.get("images") or []) + len(payload.get("local_images") or [])


def _extract_mcp_text(ok: dict) -> str:
    content = ok.get("content")
    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content") or item.get("data")
                if text:
                    chunks.append(_stringify(text))
            elif item:
                chunks.append(_stringify(item))
        return "\n".join(chunks)
    if content:
        return _stringify(content)
    for key in ("text", "output", "message"):
        if ok.get(key):
            return _stringify(ok[key])
    return ""


def _count_diff_lines(meta: SessionMetadata, diff: str) -> None:
    for line in str(diff or "").splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            meta.lines_added += 1
        elif line.startswith("-"):
            meta.lines_removed += 1


def _handle_response_item(
    payload: dict,
    ts: str,
    meta: SessionMetadata,
    messages: list[NormalizedMessage],
    call_tools: dict[str, str],
    call_result_ids: set[str],
    counted_event_tools: set[str],
) -> None:
    ptype = payload.get("type")
    if ptype == "message":
        role = payload.get("role", "user")
        text_chunks = []
        for c in payload.get("content", []) or []:
            if isinstance(c, dict):
                if c.get("type") in {"input_image", "image"}:
                    meta.image_inputs += 1
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
        call_id = payload.get("call_id", "")
        if call_id:
            call_tools[call_id] = name
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
        text = _extract_output_text(out)
        if payload.get("call_id"):
            call_result_ids.add(payload.get("call_id", ""))
        tool_name = call_tools.get(payload.get("call_id", ""), "")
        nm = NormalizedMessage(role="tool_result", timestamp=ts, text=truncate(text, 400), tool_name=tool_name, is_error=_looks_error(text))
        aggregate_message(meta, nm)
        messages.append(nm)
    elif ptype == "custom_tool_call":
        name = payload.get("name", "")
        call_id = payload.get("call_id", "")
        if call_id:
            call_tools[call_id] = name
        tool_input = _stringify(payload.get("input", ""))
        if name == "apply_patch":
            for path in extract_patch_paths(tool_input):
                meta.files_touched.append(path)
        nm = NormalizedMessage(
            role="tool_use",
            timestamp=ts,
            text=tool_input,
            tool_name=name,
            is_error=_looks_error("", payload.get("status", "")),
        )
        aggregate_message(meta, nm)
        messages.append(nm)
    elif ptype == "custom_tool_call_output":
        text = _extract_output_text(payload.get("output", ""))
        if payload.get("call_id"):
            call_result_ids.add(payload.get("call_id", ""))
        tool_name = call_tools.get(payload.get("call_id", ""), "")
        nm = NormalizedMessage(role="tool_result", timestamp=ts, text=truncate(text, 400), tool_name=tool_name, is_error=_looks_error(text))
        aggregate_message(meta, nm)
        messages.append(nm)
    elif ptype == "web_search_call":
        if "web_search" in counted_event_tools:
            meta.uses_web_search = True
            return
        counted_event_tools.add("web_search")
        nm = NormalizedMessage(
            role="tool_use",
            timestamp=ts,
            text=_stringify(payload.get("action", "")),
            tool_name="web_search",
            is_error=_looks_error("", payload.get("status", "")),
        )
        aggregate_message(meta, nm)
        messages.append(nm)
    elif ptype == "reasoning":
        # Codex reasoning summaries are internal execution context, not assistant
        # replies. Keep token accounting from token_count events, but don't let
        # summaries pollute user-facing transcript/facet extraction.
        return
