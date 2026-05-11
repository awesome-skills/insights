# report.json schema

The final aggregated artifact consumed by `render.py`. Fields are all optional;
`render.py` skips empty sections gracefully.

```json
{
  "header": {
    "title": "Optional title — defaults to '<Agent> Insights'",
    "agent": "claude-code | codex | gemini | opencode",
    "total_sessions": 87,
    "analyzed_sessions": 65,
    "messages": 1022,
    "hours": 2347,
    "commits": 99,
    "tokens": 12345678,
    "date_range": "2026-03-19 to 2026-05-11"
  },

  "at_a_glance": {
    "whats_working": "1-3 sentences",
    "whats_hindering": "1-3 sentences",
    "quick_wins": "1-3 sentences",
    "ambitious_workflows": "1-3 sentences"
  },

  "project_areas": {
    "areas": [
      {
        "name": "Multi-Agent Orchestration & Code Review",
        "session_count": 15,
        "description": "1-2 sentences."
      }
    ]
  },

  "interaction_style": {
    "narrative": "2-3 paragraphs separated by blank lines. Use \\n\\n.",
    "key_pattern": "One sentence."
  },

  "what_works": {
    "intro": "1 sentence framing.",
    "impressive_workflows": [
      {
        "title": "Short title",
        "description": "1-3 sentences with concrete evidence."
      }
    ]
  },

  "friction_analysis": {
    "intro": "1 sentence framing.",
    "categories": [
      {
        "category": "Acting before fully understanding the request",
        "description": "1-2 sentences.",
        "examples": ["session-anchored example 1", "session-anchored example 2"]
      }
    ]
  },

  "suggestions": {
    "claude_md_additions": [
      {
        "addition": "## Analysis vs Action\\nWhen asked...",
        "why": "1 sentence with evidence from sessions."
      }
    ],
    "features_to_try": [
      {
        "feature": "Custom Skills",
        "one_liner": "Reusable markdown-defined commands",
        "why_for_you": "1-2 sentences tied to user's actual patterns",
        "example_code": "Optional snippet"
      }
    ],
    "usage_patterns": [
      {
        "title": "Separate plan from execute",
        "suggestion": "1 sentence rule",
        "detail": "1-2 sentences with evidence",
        "copyable_prompt": "Phase 1 (analysis only): ..."
      }
    ]
  },

  "on_the_horizon": {
    "intro": "1 sentence framing.",
    "opportunities": [
      {
        "title": "Title",
        "whats_possible": "1-3 sentences",
        "how_to_try": "1 sentence pointer",
        "copyable_prompt": "Build me X that does Y..."
      }
    ]
  },

  "fun_ending": {
    "headline": "One-line punchy moment",
    "detail": "1-2 sentences with the context"
  },

  "stats": {
    "tool_counts": {"Bash": 543, "Read": 218},
    "language_counts": {"python": 12, "typescript": 8},
    "goal_categories": {"code_review": 10, "bug_fix": 8},
    "friction_counts": {"wrong_approach": 25, "buggy_code": 12}
  }
}
```

## Aggregation hints

- `stats.tool_counts` — sum across all metadata's `tool_counts`. Cap to top ~20 if needed; render bar chart auto-trims to top 8.
- `stats.language_counts` — sum across metadata's `languages`.
- `stats.goal_categories` — sum across facets' `goal_categories`.
- `stats.friction_counts` — sum across facets' `friction_counts`.
- `header.messages` — sum of `user_message_count + assistant_message_count`.
- `header.hours` — sum of `duration_minutes` / 60, rounded.
- `header.tokens` — sum of `input_tokens + output_tokens`. Render auto-formats to "1.2M" etc.
- `header.commits` — sum of `git_commits`.
- `header.date_range` — min start_time .. max end_time, formatted YYYY-MM-DD.

The narrative blocks (`at_a_glance`, `interaction_style.narrative`, `friction_analysis.examples`) are the **point** of the skill. Spend tokens there, not on stats.
