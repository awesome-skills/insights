# Facet schema

Each session is reduced to a small JSON facet that captures qualitative judgement.
Inspired by Claude Code's `/insights` data model.

```json
{
  "session_id": "string — unique session ID for traceability",
  "underlying_goal": "string — one sentence: what the user really wanted to accomplish",
  "goal_categories": {
    "<canonical_label>": 1
  },
  "evidence_quote": "string — one direct quote from the transcript (last assistant or last user message preferred) that anchors your outcome judgment. Required.",
  "transcript_truncated": false,
  "outcome": "fully_achieved | mostly_achieved | partially_achieved | not_achieved | unclear_from_transcript",
  "user_satisfaction_counts": {
    "satisfied": 0,
    "likely_satisfied": 0,
    "dissatisfied": 0,
    "frustrated": 0
  },
  "claude_helpfulness": "very_helpful | moderately_helpful | unhelpful | mixed",
  "session_type": "single_task | iterative_refinement | exploration | debugging | release_pipeline | review | discussion_consultation | other",
  "friction_counts": {
    "wrong_approach": 0,
    "misunderstood_request": 0,
    "excessive_changes": 0,
    "buggy_code": 0,
    "needed_pushback": 0,
    "ignored_instructions": 0
  },
  "friction_detail": "string — one sentence about the most notable friction, or empty",
  "primary_success": "good_explanations | multi_file_changes | bug_fix | release_ship | refactoring | documentation | none | other",
  "brief_summary": "≤ 2 sentences capturing user intent, agent action, outcome"
}
```

## Tips for filling these in

- **Value semantics** — the `_counts` maps always store **integer occurrence counts** within this session. They are NOT booleans, weights, or probabilities. Examples:
  - `goal_categories: {"code_review": 1, "bug_fix": 1}` means the session covered both, each as a primary thread (use `2` if the user did code reviews on two distinct PRs).
  - `user_satisfaction_counts: {"satisfied": 0, "likely_satisfied": 1, ...}` means the LLM observed *one* moment where the user appeared likely satisfied (e.g., "looks good, ship it"). Most sessions will have a single non-zero bucket.
  - `friction_counts.wrong_approach: 3` means the user redirected the agent three times for the same root reason.
- `outcome` is judged against `underlying_goal`. If user ended satisfied with a smaller scope, that's `mostly_achieved`, not `fully_achieved`.
- `claude_helpfulness` rubric — judge the *primary* contribution:
  - `very_helpful`: agent shipped the user's goal with minimal friction OR produced an insight/artefact the user clearly valued.
  - `moderately_helpful`: meaningful progress but required noticeable correction or fell short of goal.
  - `mixed`: clear value AND clear harm (e.g., shipped feature but introduced regression).
  - `unhelpful`: agent failed to make progress, blocked the user, or actively harmed.
- `transcript_truncated: true` when the transcript shown to you was cut by `--max-chars`/`--mode head_tail` and you can tell the real session ended later than what you read. Use this together with `outcome: unclear_from_transcript` so downstream knows why.
- `goal_categories` MUST use the canonical labels below — free-form labels break aggregation.
  **Canonical set** (pick 1-3): `code_review`, `feature_implementation`, `bug_fix`, `refactor`,
  `documentation_editing`, `architecture_review`, `release_engineering`, `discussion_consultation`,
  `multi_agent_orchestration`, `debugging`, `exploration`, `skill_creation`, `infra_devops`,
  `data_analysis`, `ui_design`, `testing`, `migration`, `meeting_minutes`, `email_drafting`,
  `other`. If nothing fits, use `other` + add `other_label` to the facet with a free-form string.
- `evidence_quote` is REQUIRED. Pick the single line from the transcript that most strongly justifies
  your `outcome`. A facet without this field signals the LLM didn't actually read the transcript.
- `friction_counts` should be **counts within this session**, not booleans. A session where the user interrupted you 3 times to redirect would have `wrong_approach: 3`.
  Anti-example: filling all counts as 0 + empty `friction_detail` for a non-trivial session — that's almost certainly the LLM skipping the transcript. Default to "0" only for genuine warmup/empty sessions; otherwise, find at least one specific friction or explain why none existed.
- `friction_detail` is the one line you'd put in a summary slide. Anchor it on a specific incident.
- `claude_helpfulness` reflects your honest read on whether agent's *primary contribution* was net-positive. "Mixed" is fine when there was real value but also notable harm.
- `brief_summary` is what goes into the per-session line of the report; keep it crisp.

## Skip rules

If `user_message_count < 2` AND `tool_counts is empty` → likely warmup/info-only; emit `outcome: unclear_from_transcript`, `claude_helpfulness: unhelpful`, `session_type: other` and a one-line `brief_summary` saying "session was [warmup/empty]". Don't fabricate findings for empty sessions.
