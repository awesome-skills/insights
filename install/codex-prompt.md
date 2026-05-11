---
description: Analyze local agent session history (Claude Code/Codex/Gemini/OpenCode) and generate an HTML usage report
---

# /insights

The full workflow lives at `~/.claude/skills/insights/SKILL.md`; this command inlines the essentials.

User extra args: $ARGUMENTS

## 5-step workflow

1. Detect host agent:
   `python3 ~/.claude/skills/insights/scripts/insights.py detect`

2. Quantitative metadata (default 60 days, ≤80 sessions, skip warmups):
   `python3 ~/.claude/skills/insights/scripts/insights.py metadata --agent codex --days 60 --limit 80 --min-messages 2 --workdir ~/.insights-workspace/codex`

3. Per-session facet extraction. For each metadata file, read its transcript and emit a facet JSON to `<workdir>/facets/<session_id>.json` per the schema in `~/.claude/skills/insights/references/facet_schema.md`. **`evidence_quote` is required** — pick a real line so the schema verifies you read the transcript.
   `python3 ~/.claude/skills/insights/scripts/insights.py transcript --agent codex --session <id> --max-chars 18000`

4. Aggregate to a `report.json` per `~/.claude/skills/insights/references/report_schema.md`.

5. Render HTML:
   `python3 ~/.claude/skills/insights/scripts/insights.py render --data <workdir>/report.json --out <workdir>/report.html`

## Quality bar — do NOT skip these

- Concrete evidence: every finding cites a session id (and ideally an `evidence_quote`). Vague claims like "user seems efficient" are useless.
- Friction is honest: name what the agent got wrong. Don't sanitise.
- Suggestions must be runnable: CLAUDE.md / AGENTS.md additions = exact text to paste; features = install/enable commands; usage patterns = copyable prompts.
- Match the user's language (中文 ↔ English).
- Use canonical `goal_categories` labels only (see facet_schema.md) so aggregation works.

## Heuristics for filling the facet

- `git_commits > 0` → leans toward `release_engineering` / shipping mindset.
- `user_interruptions > 0` plus "stop" / "wait" in transcript → `wrong_approach` or `needed_pushback`.
- `tool_errors` plus repeated "fix" → `buggy_code`.
- The last few transcript messages reveal `outcome` and `user_satisfaction_counts`.
- `tokens` semantics differ across agents — quote them, don't compare cross-agent.

Tell the user where the HTML lives at the end.
