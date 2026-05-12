---
description: Analyze local agent session history (Claude Code/Codex/Gemini/OpenCode) and generate an HTML usage report
---

# /insights

This Codex prompt uses the Insights runtime installed at `__INSIGHTS_DIR__`.
The full workflow lives at `__INSIGHTS_DIR__/SKILL.md`; this prompt inlines the Codex entrypoint and Codex-specific quality bar.

User extra args: $ARGUMENTS

## Supported args

Parse `$ARGUMENTS` if present:

- `--days N` → replace the metadata `--days` value.
- `--limit N` → replace the metadata `--limit` value.
- `--out PATH` → render the final HTML to that exact path.
- Unknown args → tell the user which args are supported, then stop.

## 5-step workflow

1. Detect host agent:
   `python3 "__INSIGHTS_DIR__/scripts/insights.py" detect`

2. Quantitative metadata (default 60 days, ≤80 sessions, skip warmups):
   `python3 "__INSIGHTS_DIR__/scripts/insights.py" metadata --agent codex --days 60 --limit 80 --min-messages 2 --workdir ~/.insights-workspace/codex`

3. Per-session facet extraction. For each metadata file, read its transcript and emit a facet JSON to `<workdir>/facets/<session_id>.json` per the schema in `__INSIGHTS_DIR__/references/facet_schema.md`. **`evidence_quote` is required** — pick a real line so the schema verifies you read the transcript. In Codex, use subagents when available for independent session batches; if subagents are unavailable, process batches serially and keep final narrative aggregation in the main thread.
   `python3 "__INSIGHTS_DIR__/scripts/insights.py" transcript --agent codex --session <id> --max-chars 18000`

4. Aggregate to a `report.json` per `__INSIGHTS_DIR__/references/report_schema.md`.

5. Render HTML:
   `python3 "__INSIGHTS_DIR__/scripts/insights.py" render --data <workdir>/report.json --out <workdir>/report.html`

## Quality bar — do NOT skip these

- Concrete evidence: every finding cites a session id (and ideally an `evidence_quote`). Vague claims like "user seems efficient" are useless.
- Friction is honest: name what the agent got wrong. Don't sanitise.
- Suggestions must be runnable: guidance file additions = exact text to paste into AGENTS.md / CLAUDE.md / command files; capabilities = exact feature/command/prompt to try; usage patterns = copyable prompts.
- Use agent-neutral schema fields: `agent_helpfulness`, `guidance_file_additions`, `capabilities_to_try`. Do not emit new reports with legacy `claude_helpfulness` or `claude_md_additions`.
- In Codex reports, pay special attention to instruction handling, tool execution, verification evidence, approval/sandbox fit, subagent/code-review use, MCP/web/browser usage, and final handoff quality.
- Match the user's language (中文 ↔ English).
- Use canonical `goal_categories` labels only (see facet_schema.md) so aggregation works.

## Heuristics for filling the facet

- `git_commits > 0` → leans toward `release_engineering` / shipping mindset.
- `user_interruptions > 0` plus "stop" / "wait" in transcript → `wrong_approach` or `needed_pushback`.
- `tool_errors` plus repeated "fix" → `buggy_code`.
- The last few transcript messages reveal `outcome` and `user_satisfaction_counts`.
- `tokens` semantics differ across agents — quote them, don't compare cross-agent.

After rendering, verify that the HTML exists and is non-empty. If a browser tool is available, open the local HTML and do a quick smoke check that the title and main sections render; otherwise report the file path and the verification you did.
