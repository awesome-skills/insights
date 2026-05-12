<div align="center">

**[中文](README.md)** · **English**

```
  ██╗███╗   ██╗███████╗██╗ ██████╗ ██╗  ██╗████████╗███████╗
  ██║████╗  ██║██╔════╝██║██╔════╝ ██║  ██║╚══██╔══╝██╔════╝
  ██║██╔██╗ ██║███████╗██║██║  ███╗███████║   ██║   ███████╗
  ██║██║╚██╗██║╚════██║██║██║   ██║██╔══██║   ██║   ╚════██║
  ██║██║ ╚████║███████║██║╚██████╔╝██║  ██║   ██║   ███████║
  ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝ ╚═════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝
```

### **One `/insights` command. Every coding agent.**

Read your local sessions across **Claude Code · Codex · Gemini CLI · OpenCode** →
get a beautiful, self-contained HTML usage report.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-pytest-brightgreen.svg)](tests/)
[![Agents](https://img.shields.io/badge/agents-4-purple.svg)](#-supported-agents)
[![Stdlib only](https://img.shields.io/badge/deps-stdlib%20only-success.svg)](#-requirements)

[**Install**](#-install) · [**How it works**](#-how-it-works) · [**Report sections**](#-what-the-report-contains) · [**Add a new agent**](#-extending)

</div>

---

## ✨ Why

Coding agents leave rich local session history behind, but each one uses a
different storage format, token semantics, tool-event shape, and command entry.
Raw logs make it hard to answer the questions that matter: what did you ask the
agent to do, which workflows actually worked, which failures repeated, and which
repo instructions or prompt patterns should be made durable?

**`insights`** unifies those records into one offline report. The report uses a
Codex-native execution lens — instruction context, tool execution, verification
evidence, and handoff quality — while keeping the schema agent-neutral so
Claude Code, Codex, Gemini CLI, and OpenCode can all emit the same shape.

```
┌─────────────────────────────────────────────────────────────┐
│  ~/.claude/projects/    ─┐                                   │
│  ~/.codex/sessions/     ─┤                                   │
│  ~/.gemini/tmp/         ─┼─►  insights  ─►  report.html      │
│  ~/.local/.../          ─┘                  (self-contained) │
│  opencode.db                                                  │
└─────────────────────────────────────────────────────────────┘
```

## ⚡ Quick start

```bash
git clone https://github.com/awesome-skills/insights.git ~/.claude/skills/insights
bash ~/.claude/skills/insights/install/install.sh
```

The installer auto-detects which agents you have and drops `/insights` into each.
Then, in any installed agent:

```
/insights
```

That's it. Open the HTML file path it prints at the end.

Common args:

```bash
/insights --days 30 --limit 50 --out ~/Desktop/insights.html
```

You can also run the CLI directly:

```bash
python3 scripts/insights.py metadata --agent codex --days 30 --limit 50
python3 scripts/insights.py render --data report.json --out report.html
```

## 🧭 Supported agents

| Agent | Session storage | Format |
|---|---|---|
| 🟪 **Claude Code** | `~/.claude/projects/<encoded-cwd>/*.jsonl` | JSONL |
| 🟦 **Codex** | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` | JSONL |
| 🟩 **Gemini CLI** | `~/.gemini/tmp/<project>/chats/session-*.json` | JSON |
| 🟧 **OpenCode** | `~/.local/share/opencode/opencode.db` | SQLite |

All four use the same `/insights` command. The skill auto-detects which agent
is hosting it from env vars and session activity.

## 📊 What the report contains

<table>
<tr>
<td width="50%" valign="top">

### 🔭 At a glance
Four observations in one box: what's working, what's getting in your way, quick wins to try, and ambitious workflows your usage hints at.

### 🗺️ Project areas
Your sessions clustered by what you were actually working on — backend refactors, multi-agent reviews, doc writing — with session counts.

### 🎭 Operating style
A 2-3 paragraph narrative of how you set goals, constrain scope, and supervise execution.

### ⭐ Impressive things you did
Workflow moves worth keeping. Concrete, evidence-anchored.

</td>
<td width="50%" valign="top">

### 🧱 Where things go wrong
Recurring friction with specific session examples. Honest about what the agent got wrong.

### 💡 Suggestions
Paste-ready guidance for `AGENTS.md` / `CLAUDE.md` / command files, capabilities to try, and copyable prompt patterns.

### 🚀 On the horizon
Ambitious workflows your usage hints at — autonomous review loops, scheduled stewards, spec-driven generation.

### 📈 Charts
Bar charts of top tools, languages, goal categories, friction patterns.

</td>
</tr>
</table>

## 🧠 How it works

Mechanical work runs in Python (fast, reproducible). Narrative work runs in the
host LLM (creative, context-aware). They meet at a JSON intermediate layer.

```
   ┌──────────────────────┐
   │  1. discover         │  ←─ adapter glob/sqlite, find session files
   └──────────┬───────────┘
              ↓
   ┌──────────────────────┐
   │  2. metadata         │  ←─ extract tool counts, tokens, commits,
   │     (cached, fast)   │     first_prompt, error rate per session
   └──────────┬───────────┘
              ↓
   ┌──────────────────────┐
   │  3. transcript       │  ←─ Markdownify with head_tail truncation
   │     + facet (LLM)    │     so the model sees session endings
   └──────────┬───────────┘
              ↓
   ┌──────────────────────┐
   │  4. aggregate (LLM)  │  ←─ synthesize narrative sections
   └──────────┬───────────┘
              ↓
   ┌──────────────────────┐
   │  5. render           │  ←─ single self-contained HTML
   └──────────────────────┘
```

The host LLM (Claude, GPT, Gemini, whatever you're using) does the qualitative
work: clustering projects, judging instruction handling, evaluating tool
execution and verification evidence, and writing actionable suggestions. The
Python layer keeps mechanical metadata/facet/report generation consistent across agents.

## 🛠 Install options

```bash
bash install/install.sh             # install everywhere detected
bash install/install.sh --status    # show what's currently linked
bash install/install.sh --uninstall # remove entries managed by this installer
bash install/install.sh --force     # overwrite existing entries
bash install/install.sh --dry-run   # print actions without doing them
```

After install, each agent gets an entry pointing at this skill. Claude/Gemini use
symlinks; OpenCode/Codex use rendered command/prompt files with absolute paths:

```
~/.claude/skills/insights/                     ← Claude Code (auto-discovered)
~/.gemini/commands/insights.toml               ← Gemini CLI
~/.config/opencode/commands/insights.md        ← OpenCode
~/.codex/prompts/insights.md                   ← Codex (or $CODEX_HOME/prompts/insights.md)
```

The installer refuses to write through symlinked parent directories and never
clobbers existing entries unless you pass `--force`.

## 🟦 Codex support

Codex is not treated as just another JSONL source. The adapter understands
Codex rollout events such as `function_call`, `custom_tool_call` (`apply_patch`),
`web_search_call`, `event_msg`, MCP tool events, `turn_context`, and
`session_meta`, so reports can reflect model/effort, approval and sandbox mode,
web search, subagents, compaction/rollback, patch files, verification commands,
and tool failures. Codex reasoning summaries are treated as internal execution
context, not user-visible transcript text.

Codex reports prioritize suggestions around `AGENTS.md` rules, subagents, local
code review, web search, MCP, approval modes, `codex exec` automation, and the
evidence chain: changed files, tests, browser smoke checks, and unverified risks.

## 🟨 OpenCode support

OpenCode stores sessions in local SQLite, not JSONL. `insights` opens
`~/.local/share/opencode/opencode.db` read-only and parses `text`, `tool`,
`file`, `subtask`, and `patch` parts from the message / part tables. Reports can
therefore reflect tool calls, failed tool states, subtask usage, image/file
attachments, touched files, and language distribution.

Token accounting is OpenCode-specific: input uses the peak of
`input + cache.read + cache.write` so cumulative context is not added repeatedly;
output is summed per turn. `metadata` mode strips large tool output and file
content before parsing parts, keeping batch scans lighter.

For installation, OpenCode uses a rendered command file at
`~/.config/opencode/commands/insights.md` with this skill's absolute path. Older
template symlinks are upgraded to rendered files on reinstall.

## 📦 Requirements

- **Python 3.8+** — stdlib only, no third-party packages
- **`sqlite3` module** — always present in CPython, used for OpenCode
- **`pytest`** — only if you want to run the regression suite

## 🏗 Architecture

<details>
<summary><b>Click to expand directory layout</b></summary>

```
insights/
├── SKILL.md                    # workflow the host LLM follows (Step 1-5)
├── README.md                   # ← you are here
├── LICENSE                     # MIT
│
├── scripts/
│   ├── insights.py             # CLI: detect / list-agents / discover / metadata / transcript / render
│   ├── common.py               # shared types, system-injection filter, tool-input extractor,
│   │                           #   Bash-path harvester, DiscardList for OOM-safe parsing
│   ├── render.py               # report.json → self-contained HTML (CSS inline, no JS,
│   │                           #   XSS-safe, prints cleanly, dark-mode resistant)
│   └── adapters/
│       ├── claude_code.py      # skip sub-agent dirs + isSidechain events,
│       │                       #   recover <command-args> body
│       ├── codex.py            # skip sub-agent rollouts (payload.source.subagent),
│       │                       #   parse turn_context/event_msg/MCP/patch/web search
│       ├── gemini.py           # 50MB file cap, non-dict guard, id round-trip
│       └── opencode.py         # read-only SQLite, tool/file/subtask/patch, peak context tokens
│
├── references/
│   ├── facet_schema.md         # per-session JSON the LLM must produce
│   └── report_schema.md        # final aggregated shape that render consumes
│
├── install/
│   ├── install.sh              # idempotent installer with --uninstall/--dry-run/--force/--status
│   ├── gemini-command.toml     # Gemini CLI slash-command (TOML)
│   ├── opencode-command.md     # OpenCode slash-command (Markdown frontmatter)
│   └── codex-prompt.md         # Codex prompt (Markdown frontmatter)
│
└── tests/                      # pytest regression suite, ~0.1s to run
    ├── conftest.py             # path setup
    ├── test_common.py          # system-injection filter, Bash paths, git actions
    ├── test_adapters.py        # one fixture per agent + regression pins
    └── test_render.py          # XSS, empty sections, schema variations, TOC accuracy
```

</details>

<details>
<summary><b>What the report doesn't try to do</b></summary>

- **No cross-agent comparison.** Token semantics differ per agent (Codex
  stores cumulative totals, OpenCode tracks per-turn fresh input, Claude Code
  reports per-message), so the `header.tokens` figure is intentionally a
  single number per report, not a leaderboard.
- **No remote upload.** Everything stays local. The HTML loads no external
  resources (no CDN, no fonts, no trackers), so the file is **readable
  offline** and survives being zipped.
- **No background scheduling.** Run `/insights` when you want a report; it
  does nothing in the background.
- **No cloud accounts, telemetry, or analytics.** Pure stdlib Python reading
  your own files.

> ⚠️ **Self-review before sharing.** The HTML is self-contained, but that
> doesn't mean its *contents* are safe to share. The report embeds real
> `first_prompt` text, session summaries, file paths, and tool-output
> fragments — these can include API keys, customer data, internal code
> snippets, private paths. Skim it before emailing / Slacking / posting a
> screenshot. Search-and-replace for sensitive tokens if you need to share.

</details>

## 🔌 Extending

Each adapter exposes two functions:

```python
def list_sessions(since: datetime | None = None, root: Path = DEFAULT_ROOT) -> list[dict]: ...
def parse_session(path: str, metadata_only: bool = False) -> ParsedSession: ...
```

To add a new agent:

1. Drop a module in `scripts/adapters/your_agent.py`
2. Implement the two functions, returning `ParsedSession(metadata, messages)`
3. Register it in `scripts/insights.py:ADAPTER_MODULES`
4. (Optional) Add an env-var probe in `common.detect_agent_from_env`

Typical adapter is ~150–250 lines. See the four existing ones for working
references covering JSONL streaming, single-file JSON, and SQLite.

## 🧪 Tests

```bash
pip install pytest
pytest tests/
```

The tests cover the critical bugs we pinned:

- Sub-agent rollout exclusion (Claude Code subdirs + Codex `payload.source.subagent`)
- System-injection filtering — strict enough to keep real `<system>` user text
- `<command-args>` extraction for slash-command bodies
- Token-counting semantics (cumulative vs per-turn vs max-of-cumulative)
- HTML escaping / XSS-safety
- Empty-section + schema-shape variations
- Edge cases (broken JSON, missing DB, non-dict top-level)

## 🤝 Contributing

PRs welcome. Worth knowing before you open one:

- **No third-party dependencies** in the runtime path. Tests can use `pytest`.
- **Adapters should be parallel** — if you add a feature, make sure it's
  consistent across all four (and the schema docs)
- **Add a pytest case** when fixing a bug; that's how we keep the four
  adapters from drifting

## 📜 License

MIT — see [LICENSE](LICENSE).

## 🙏 Acknowledgements

- The `/insights` command in **Claude Code** for the idea, the section
  structure, and the bar to clear.
- The session-data formats are all Anthropic / OpenAI / Google / SST design;
  this skill just adapts them into one place.

---

<div align="center">

**Star this repo if `/insights` helped you spot a habit you wanted to change.** ⭐

</div>
