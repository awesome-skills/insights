# insights

A portable `/insights` command for **Claude Code**, **Codex**, **Gemini CLI**, and **OpenCode**.
Reads your local session history, then produces a self-contained HTML report covering project
areas, interaction style, friction patterns, suggested CLAUDE.md / AGENTS.md additions, and
future workflow opportunities — modelled after Claude Code's built-in `/insights`, but agent-agnostic.

> Inspired by Claude Code's `/insights` — this skill makes the same workflow available wherever
> you talk to an AI coding agent locally.

## What you get

A single `report.html` with:

- **At a glance** — 4 short observations: what's working, what's getting in the way, quick wins, longer-term plays
- **Project areas** — clustering of your sessions by what you were actually working on
- **Interaction style** — narrative analysis of how you drive the agent
- **Impressive things you did** — workflow patterns worth keeping
- **Where things go wrong** — recurring friction with concrete examples
- **Suggestions** — paste-ready `CLAUDE.md` / `AGENTS.md` additions, features to try, copyable prompts
- **On the horizon** — ambitious workflows your usage hints at
- **Charts** — tools, languages, goal categories, friction patterns

## Supported agents

| Agent | Session storage |
|---|---|
| Claude Code | `~/.claude/projects/<encoded-cwd>/*.jsonl` |
| Codex | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` |
| Gemini CLI | `~/.gemini/tmp/<project>/chats/session-*.json` |
| OpenCode | `~/.local/share/opencode/opencode.db` (SQLite) |

The Python part is mechanical (discover sessions, extract metadata, render HTML). The
narrative part (writing the at-a-glance / friction / suggestions sections) is done by the
host LLM — same agent you're talking to.

## Install

```bash
git clone https://github.com/awesome-skills/insights.git ~/.claude/skills/insights
bash ~/.claude/skills/insights/install/install.sh
```

The installer drops a `/insights` command into each agent it detects:

- Claude Code: discovered automatically at `~/.claude/skills/insights`
- Gemini CLI: `~/.gemini/commands/insights.toml`
- OpenCode: `~/.config/opencode/commands/insights.md`
- Codex: `~/.codex/prompts/insights.md`

Other useful flags:

```bash
install.sh --status     # show what's installed
install.sh --uninstall  # remove the symlinks
install.sh --force      # overwrite existing entries
install.sh --dry-run    # print actions without doing them
```

## Use

In any installed agent:

```
/insights
```

The agent will:
1. Detect itself, pick a workspace under `~/.insights-workspace/<agent>/`.
2. Run mechanical metadata extraction (~seconds; cached by mtime on subsequent runs).
3. Read transcripts for representative sessions and write per-session JSON facets.
4. Aggregate everything into a `report.json`.
5. Render `report.html`.

It'll then tell you the file path. Open it in a browser.

## Requirements

- Python 3.8+ (stdlib only — no third-party dependencies)
- For OpenCode: the SQLite stdlib module (always present)
- For tests: `pytest` (optional)

## Architecture

```
insights/
├── SKILL.md                    # workflow the host LLM follows
├── scripts/
│   ├── insights.py             # CLI entry: detect / list-agents / discover / metadata / transcript / render
│   ├── common.py               # shared types, system-injection filter, tool-input extractor
│   ├── render.py               # report.json → self-contained HTML
│   └── adapters/
│       ├── claude_code.py      # JSONL per session, skip sub-agent rollouts + sidechain events
│       ├── codex.py            # JSONL per session, skip sub-agent rollouts (payload.source.subagent)
│       ├── gemini.py           # single JSON per session, with file-size + non-dict guards
│       └── opencode.py         # SQLite, read-only, max-of-(input + cache.read) for tokens
├── references/
│   ├── facet_schema.md         # per-session JSON shape the LLM must produce
│   └── report_schema.md        # final aggregated shape consumed by render
├── install/
│   ├── install.sh              # idempotent install/uninstall/dry-run/force/status
│   ├── gemini-command.toml
│   ├── opencode-command.md
│   └── codex-prompt.md
└── tests/                      # pytest suite — guards against regressions
    ├── test_common.py
    ├── test_adapters.py
    └── test_render.py
```

## What the report doesn't do

- **No cross-agent comparison.** Token semantics differ per agent (Codex stores cumulative
  totals, OpenCode tracks per-turn fresh input, Claude Code reports per-message), so the
  `header.tokens` figure is intentionally a single number, not a leaderboard.
- **No remote upload.** Everything stays on your machine. The generated HTML loads no
  external resources, so it's safe to share via email/Slack.
- **No automatic scheduling.** Run `/insights` when you want a report; it does nothing in
  the background.

## Adding a new agent

Each adapter exposes two functions:

```python
def list_sessions(since: datetime | None = None, root: Path = DEFAULT_ROOT) -> list[dict]: ...
def parse_session(path: str, metadata_only: bool = False) -> ParsedSession: ...
```

Drop a new module in `scripts/adapters/`, register it in `insights.py:ADAPTER_MODULES`, and
optionally add an env-var probe in `common.detect_agent_from_env`. See the four existing
adapters for working references — typical adapter is ~150–250 lines.

## Tests

```bash
pip install pytest
pytest insights/tests/
```

46 cases cover system-injection filtering, sub-agent rollout exclusion, slash-command body
extraction, token-counting semantics per agent, HTML escaping / XSS, schema-shape variations,
and edge cases like broken JSON or missing databases.

## License

MIT — see [LICENSE](LICENSE).
