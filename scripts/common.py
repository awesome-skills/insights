"""Shared types and helpers for insights skill."""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


GIT_COMMIT_RE = re.compile(r"\bgit\s+commit\b", re.IGNORECASE)
GIT_PUSH_RE = re.compile(r"\bgit\s+push\b", re.IGNORECASE)

# Match `path/to/file.ext` shaped tokens inside Bash commands so a session that
# only edits Python via `python3 foo.py` still shows up in the language histogram.
# Conservative: needs at least one `/` or `.` plus a recognised extension; trims
# trailing punctuation that's not part of the path.
_BASH_PATH_EXT_RE = re.compile(
    r"(?<![A-Za-z0-9_/.-])"
    r"((?:[A-Za-z0-9_./-]+/)?[A-Za-z0-9_.-]+"
    r"\.(?:py|pyi|js|jsx|ts|tsx|go|rs|java|kt|swift|rb|php|c|h|cc|cpp|hpp|"
    r"cs|md|json|ya?ml|toml|sh|bash|zsh|sql|html|css|scss|vue|svelte|"
    r"lua|r|dart|scala|clj|ex|exs|erl))"
    r"(?![A-Za-z0-9])"
)

_PATCH_PATH_RE = re.compile(r"^\*\*\* (?:(?:Add|Update|Delete) File|Move to): (.+)$")


def extract_bash_paths(command: str, limit: int = 12) -> list[str]:
    """Return file paths referenced by a Bash command string.

    Doesn't enforce path validity — just extension-tagged tokens that look
    file-shaped. Capped to `limit` per command so one mega `find` invocation
    can't blow up files_touched.
    """
    if not command:
        return []
    seen = []
    for m in _BASH_PATH_EXT_RE.finditer(command):
        candidate = m.group(1)
        if candidate not in seen:
            seen.append(candidate)
            if len(seen) >= limit:
                break
    return seen


def extract_patch_paths(patch_text: str, limit: int = 100) -> list[str]:
    """Return file paths mentioned in an apply_patch-style patch."""
    if not patch_text:
        return []
    seen = []
    for line in str(patch_text).splitlines():
        m = _PATCH_PATH_RE.match(line.strip())
        if not m:
            continue
        path = m.group(1).strip()
        if path and path not in seen:
            seen.append(path)
            if len(seen) >= limit:
                break
    return seen

LANG_EXT = {
    ".py": "python", ".js": "javascript", ".ts": "typescript", ".tsx": "typescript",
    ".jsx": "javascript", ".go": "go", ".rs": "rust", ".java": "java",
    ".kt": "kotlin", ".swift": "swift", ".rb": "ruby", ".php": "php",
    ".c": "c", ".cpp": "c++", ".h": "c", ".hpp": "c++", ".cs": "csharp",
    ".md": "markdown", ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".toml": "toml", ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".sql": "sql", ".html": "html", ".css": "css", ".scss": "scss",
    ".vue": "vue", ".svelte": "svelte", ".lua": "lua", ".r": "r",
    ".dart": "dart", ".scala": "scala", ".clj": "clojure", ".ex": "elixir",
    ".exs": "elixir", ".erl": "erlang",
}


@dataclass
class NormalizedMessage:
    role: str  # user | assistant | tool_use | tool_result | system | info
    timestamp: str = ""
    text: str = ""
    tool_name: str = ""
    is_error: bool = False
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass
class SessionMetadata:
    """Quantitative per-session facts. Comparable to Claude Code's session-meta."""
    session_id: str
    agent: str  # claude-code | codex | gemini | opencode
    project_path: str = ""
    start_time: str = ""
    end_time: str = ""
    duration_minutes: float = 0.0
    user_message_count: int = 0
    assistant_message_count: int = 0
    tool_counts: dict[str, int] = field(default_factory=dict)
    languages: dict[str, int] = field(default_factory=dict)
    git_commits: int = 0
    git_pushes: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    first_prompt: str = ""
    user_interruptions: int = 0
    tool_errors: int = 0
    tool_error_categories: dict[str, int] = field(default_factory=dict)
    uses_task_agent: bool = False
    uses_mcp: bool = False
    uses_web_search: bool = False
    uses_web_fetch: bool = False
    lines_added: int = 0
    lines_removed: int = 0
    files_modified: int = 0
    files_touched: list[str] = field(default_factory=list)
    message_hours: list[int] = field(default_factory=list)
    model: str = ""
    reasoning_effort: str = ""
    approval_policy: str = ""
    sandbox_policy: str = ""
    collaboration_mode: str = ""
    cli_version: str = ""
    model_provider: str = ""
    originator: str = ""
    memory_mode: str = ""
    thread_source: str = ""
    agent_role: str = ""
    reasoning_output_tokens: int = 0
    compactions: int = 0
    rollbacks: int = 0
    patches_applied: int = 0
    patches_failed: int = 0
    image_inputs: int = 0
    mcp_calls: int = 0


@dataclass
class ParsedSession:
    metadata: SessionMetadata
    messages: list[NormalizedMessage]


class DiscardList(list):
    """A list-compatible sink that drops everything passed to append.

    Used by adapters when `metadata_only=True` so the aggregation pipeline
    doesn't need parallel code paths. Lets callers still iterate (yields 0
    messages) without retaining gigabytes of NormalizedMessage instances.
    """
    __slots__ = ()

    def append(self, _item) -> None:  # noqa: D401
        return None

    def extend(self, _items) -> None:  # noqa: D401
        return None


# ----------------- helpers ------------------

_SAFE_ID_CHARS = re.compile(r"[^A-Za-z0-9._-]")
_MAX_SAFE_ID_LEN = 128


def safe_session_id(raw: str, fallback: str = "unknown") -> str:
    """Return a session id safe to use as a filename component.

    Session ids come from external data — Gemini reads `sessionId` from the
    session JSON, OpenCode reads it from SQLite. A hostile or corrupted source
    could supply `../../etc/passwd`, an absolute path, or a 10 MB string.
    Without sanitisation, `meta_dir / f"{session_id}.json"` then escapes the
    workspace via Path's segment semantics.

    Strip anything that isn't `[A-Za-z0-9._-]`, cap length, and refuse `..`
    or `.` as the whole result.
    """
    # None has no useful identity to distinguish, so collapse to the bare fallback.
    # "" / "." / ".." DO carry distinct identities and must not collide with each
    # other or with a literal `fallback` upstream session id — append a digest.
    if raw is None:
        return fallback
    raw_s = str(raw)
    digest = hashlib.sha256(raw_s.encode("utf-8", errors="replace")).hexdigest()[:8]
    if not raw_s or raw_s in (".", ".."):
        return f"{fallback}-{digest}"
    cleaned_full = _SAFE_ID_CHARS.sub("_", raw_s)
    cleaned = cleaned_full[:_MAX_SAFE_ID_LEN]
    cleaned = cleaned.strip("._-")
    if not cleaned or cleaned in (".", ".."):
        return f"{fallback}-{digest}"
    if cleaned == raw_s and len(raw_s) <= _MAX_SAFE_ID_LEN:
        return cleaned
    suffix = f"-{digest}"
    base = cleaned[: _MAX_SAFE_ID_LEN - len(suffix)].strip("._-") or fallback
    if base in (".", ".."):
        base = fallback
    return f"{base}{suffix}"


def truncate(s: str, n: int = 200) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def parse_iso(ts: str | int | float | None) -> datetime | None:
    if ts is None:
        return None
    # bool is a subclass of int; reject explicitly so True/False don't become 1970 timestamps.
    if isinstance(ts, bool):
        return None
    if isinstance(ts, (int, float)):
        # NaN/Inf would otherwise overflow inside fromtimestamp.
        if isinstance(ts, float) and (ts != ts or ts in (float("inf"), float("-inf"))):
            return None
        try:
            seconds = ts / 1000 if ts > 1e12 else ts
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, ValueError, OSError):
            return None
    if isinstance(ts, str):
        try:
            s = ts.replace("Z", "+00:00")
            return datetime.fromisoformat(s)
        except ValueError:
            return None
    return None


def detect_language(path: str) -> str:
    if not path:
        return ""
    _, _, ext = path.lower().rpartition(".")
    if not ext:
        return ""
    return LANG_EXT.get(f".{ext}", "")


def count_git_actions(command: str) -> tuple[int, int]:
    """Return (commits, pushes) implied by a shell command string."""
    if not command:
        return 0, 0
    commits = len(GIT_COMMIT_RE.findall(command))
    pushes = len(GIT_PUSH_RE.findall(command))
    return commits, pushes


# Skip JSONL lines bigger than this (single tool_result blobs can be 300MB+,
# parsing one of those as a Python dict eats ~3x in RSS).
MAX_JSONL_LINE_BYTES = 8 * 1024 * 1024


_TOOL_INPUT_KEYS = ("command", "cmd", "file_path", "filePath", "path", "file", "url")
_FILE_KEYS = ("file_path", "filePath", "path", "file")


# Exact opening tokens that mark a message as a harness/system payload.
# Each entry is a literal substring that must appear at the *start* of the text
# (after lstrip()), followed by a non-name char (>, space, newline) so that a
# legit user message like "<system> review my repo" is NOT swallowed.
#
# Be conservative: prefer false negatives (some pollution leaks) over false
# positives (silently dropping real user prompts → headline metric corruption).
_SYSTEM_INJECTION_TAGS = (
    # Codex
    "environment_context",
    "user_instructions",
    "permissions_instructions",
    "permissions",
    "system_instructions",
    "system-reminder",
    "developer",
    "app-context",
    "turn_aborted",
    "subagent_notification",
    # Claude Code
    "command-name",
    "command-message",
    "command-args",
    "local-command-caveat",
    "local-command-stdout",
    "local-command-stderr",
    "bash-input",
    "bash-stdout",
    "bash-stderr",
    "task-notification",
    "task-id",
    "tool-use-id",
)

# Non-tag prefixes that should still trigger filtering (used cautiously).
_SYSTEM_INJECTION_LITERAL_PREFIXES = (
    "# AGENTS.md instructions for ",  # Codex AGENTS.md slurp
)

# Templates that frontend slash commands inject before the user's real input.
# Match anywhere in the first ~120 chars.
_SYSTEM_INJECTION_TEMPLATE_NEEDLES = (
    "The user just ran /",                # Claude Code slash-command body
    "The user ran the /",                 # variant phrasing
)


def is_system_injection(role: str, text: str) -> bool:
    """True if a user-role message is actually a harness/system payload.

    Filtering strategy:
      1. `role == developer|system` → always filtered (no legit user content).
      2. Text starts with a known XML tag opener `<TAG>` or `<TAG ` (must be
         followed by `>` or whitespace — prevents matching `<system> please …`).
      3. Text starts with a literal harness prefix like `# AGENTS.md instructions for `.
      4. The first ~120 chars contain a slash-command boilerplate template.

    Prefer false negatives (let some pollution through) over false positives
    (silently dropping a real user prompt corrupts headline metrics).
    """
    if role in ("developer", "system"):
        return True
    head = (text or "").lstrip()
    if not head:
        return False
    if head[0] == "<":
        # Strict XML opener: `<tag>` or `<tag ` only. `<tag` without delimiter
        # is treated as ordinary text so users can write `<system>` prose.
        for tag in _SYSTEM_INJECTION_TAGS:
            # Need len(tag)+2 chars: '<' + tag + ('>' or whitespace)
            cand = head[1 : 1 + len(tag) + 1]
            if cand == tag + ">" or cand == tag + " " or cand == tag + "\n" or cand == tag + "\t":
                return True
    for pfx in _SYSTEM_INJECTION_LITERAL_PREFIXES:
        if head.startswith(pfx):
            return True
    needle_zone = head[:160]
    for needle in _SYSTEM_INJECTION_TEMPLATE_NEEDLES:
        if needle in needle_zone:
            return True
    return False


def extract_tool_input(args) -> tuple[str, str]:
    """Pull a representative (command, file_path) pair from a tool's `input` payload.

    Tool input formats differ across agents but converge on a few common keys:
      Claude Code: {command, file_path, path, url}
      Codex:       {command, file_path, path}
      Gemini:      {command, file_path, path}
      OpenCode:    {command, filePath, path}

    Returns ("", "") for unrecognised payloads. The first non-empty value among
    `_TOOL_INPUT_KEYS` becomes the `command` field (useful for grepping git etc.);
    any value under `_FILE_KEYS` is returned as `file_path` for files_touched.
    """
    if not isinstance(args, dict):
        return "", ""
    cmd = ""
    fp = ""
    for k in _TOOL_INPUT_KEYS:
        v = args.get(k)
        if v:
            if isinstance(v, list):
                v = " ".join(str(x) for x in v)
            cmd = str(v)
            break
    for k in _FILE_KEYS:
        v = args.get(k)
        if v:
            fp = str(v) if not isinstance(v, list) else (str(v[0]) if v else "")
            break
    return cmd, fp


# Tools that actually dispatch sub-agents / tasks (rather than skills whose name
# happens to contain "agent" like `agent-inspect`).
_TASK_AGENT_TOOL_NAMES = {
    "Task", "Agent", "TaskCreate", "TaskUpdate", "TaskGet", "TaskList",
    "dispatch_agent", "spawn_agent", "subagent", "subtask",
}


def aggregate_message(meta: SessionMetadata, msg: NormalizedMessage) -> None:
    """Fold one message into a SessionMetadata accumulator."""
    if msg.role == "user":
        meta.user_message_count += 1
        if not meta.first_prompt and msg.text:
            meta.first_prompt = truncate(msg.text, 200)
        dt = parse_iso(msg.timestamp)
        if dt:
            # Convert UTC timestamps to local time so "active hours" buckets
            # reflect the user's experienced schedule, not server time.
            try:
                meta.message_hours.append(dt.astimezone().hour)
            except (ValueError, OSError):
                meta.message_hours.append(dt.hour)
    elif msg.role == "assistant":
        meta.assistant_message_count += 1
    meta.input_tokens += msg.tokens_in
    meta.output_tokens += msg.tokens_out
    if msg.is_error:
        meta.tool_errors += 1
        if msg.tool_name:
            meta.tool_error_categories[msg.tool_name] = meta.tool_error_categories.get(msg.tool_name, 0) + 1
    if msg.tool_name and msg.role == "tool_use":
        meta.tool_counts[msg.tool_name] = meta.tool_counts.get(msg.tool_name, 0) + 1
        lower = msg.tool_name.lower()
        if msg.tool_name in _TASK_AGENT_TOOL_NAMES or lower.startswith("task"):
            meta.uses_task_agent = True
        if lower.startswith("mcp_") or lower.startswith("mcp__"):
            meta.uses_mcp = True
        if "websearch" in lower or "web_search" in lower:
            meta.uses_web_search = True
        if "webfetch" in lower or "web_fetch" in lower:
            meta.uses_web_fetch = True
        if lower in {"bash", "shell", "execute", "exec_command"}:
            c, p = count_git_actions(msg.text)
            meta.git_commits += c
            meta.git_pushes += p
            # Bash invocations like `python3 src/foo.py` carry the real file
            # path; harvest it so the language histogram isn't only "shell".
            for path in extract_bash_paths(msg.text):
                meta.files_touched.append(path)


def finalize_metadata(meta: SessionMetadata) -> None:
    if meta.start_time and meta.end_time:
        # parse_iso swallows ValueError / OverflowError / OSError and returns
        # None, so the `if s and e` guard handles every failure mode — no need
        # for an outer try/except.
        s = parse_iso(meta.start_time)
        e = parse_iso(meta.end_time)
        if s and e:
            meta.duration_minutes = max(0.0, (e - s).total_seconds() / 60)
    # de-dup files_touched
    if meta.files_touched:
        seen = []
        for f in meta.files_touched:
            f = _normalize_touched_path(f, meta.project_path)
            if f and f not in seen:
                seen.append(f)
        meta.files_touched = seen[:200]
        meta.files_modified = len(seen)
        for f in seen:
            lang = detect_language(f)
            if lang:
                meta.languages[lang] = meta.languages.get(lang, 0) + 1


def _normalize_touched_path(path: str, project_path: str = "") -> str:
    if not path:
        return ""
    text = str(path)
    if project_path:
        try:
            p = Path(text)
            root = Path(project_path)
            if p.is_absolute():
                return str(p.resolve().relative_to(root.resolve()))
        except (OSError, ValueError):
            return text
    return text


def metadata_to_dict(m: SessionMetadata) -> dict[str, Any]:
    return asdict(m)


def detect_agent_from_env() -> str | None:
    """Best-effort detection of the host agent. Returns one of:
    claude-code | codex | gemini | opencode | None
    """
    # explicit env hints
    if os.environ.get("CLAUDECODE") or os.environ.get("CLAUDE_CODE_ENTRYPOINT"):
        return "claude-code"
    if os.environ.get("CODEX_HOME") or os.environ.get("OPENAI_CODEX_HOME"):
        return "codex"
    if os.environ.get("GEMINI_CLI") or os.environ.get("GEMINI_HOME"):
        return "gemini"
    if os.environ.get("OPENCODE_HOME") or os.environ.get("OPENCODE"):
        return "opencode"
    return None
