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
[![Tests](https://img.shields.io/badge/tests-46%20passing-brightgreen.svg)](tests/)
[![Agents](https://img.shields.io/badge/agents-4-purple.svg)](#-supported-agents)
[![Stdlib only](https://img.shields.io/badge/deps-stdlib%20only-success.svg)](#-requirements)

[**Install**](#-install) · [**How it works**](#-how-it-works) · [**Report sections**](#-what-the-report-contains) · [**Add a new agent**](#-extending)

</div>

---

## ✨ Why

Claude Code ships a `/insights` command that turns your session history into a
thoughtful usage report. It's brilliant — and it only works in Claude Code.

If you switch between **Codex**, **Gemini CLI**, **OpenCode**, or all of them,
your usage data lives in four different formats on disk and goes unused.

**`insights`** unifies them. One install, one command, one HTML report — no
matter which agent you're currently talking to.

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

### 🎭 Interaction style
A 2-3 paragraph narrative of *how* you drive the agent: spec-first vs iterative? Supervisor or hands-on? With one key-pattern callout.

### ⭐ Impressive things you did
Workflow moves worth keeping. Concrete, evidence-anchored.

</td>
<td width="50%" valign="top">

### 🧱 Where things go wrong
Recurring friction with specific session examples. Honest about what the agent got wrong.

### 💡 Suggestions
Paste-ready `CLAUDE.md`/`AGENTS.md` additions, features to try (Skills, Hooks, MCP, etc.), and copyable prompt patterns.

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
work — writing observations, clustering projects, suggesting changes — and the
skill's Python layer keeps the mechanical work consistent across agents.

## 🛠 Install options

```bash
bash install/install.sh             # install everywhere detected
bash install/install.sh --status    # show what's currently linked
bash install/install.sh --uninstall # remove symlinks
bash install/install.sh --force     # overwrite existing entries
bash install/install.sh --dry-run   # print actions without doing them
```

After install, each agent gets a slash command pointing at this skill:

```
~/.claude/skills/insights/                     ← Claude Code (auto-discovered)
~/.gemini/commands/insights.toml               ← Gemini CLI
~/.config/opencode/commands/insights.md        ← OpenCode
~/.codex/prompts/insights.md                   ← Codex
```

The installer refuses to write through symlinked parent directories and never
clobbers existing entries unless you pass `--force`.

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
│       │                       #   strict system-injection filtering
│       ├── gemini.py           # 50MB file cap, non-dict guard, id round-trip
│       └── opencode.py         # read-only SQLite, max-of-(input+cache.read) tokens
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
└── tests/                      # 46 pytest cases, ~0.1s to run
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

46 cases cover what we shipped fixes for:

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
