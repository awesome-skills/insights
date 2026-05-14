"""Render the aggregated report.json into a single-file HTML.

The HTML is self-contained (no JS framework, inline CSS). It mirrors the
section structure of Claude Code's /insights output.
"""
from __future__ import annotations

import html
import json
import math
import sys
from pathlib import Path

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'PingFang SC', sans-serif;
       background: #f8fafc; color: #334155; line-height: 1.65; padding: 48px 24px; }
.container { max-width: 860px; margin: 0 auto; }
h1 { font-size: 30px; font-weight: 700; color: #0f172a; margin-bottom: 8px; }
h2 { font-size: 20px; font-weight: 600; color: #0f172a; margin-top: 44px; margin-bottom: 14px; }
.subtitle { color: #64748b; font-size: 14px; margin-bottom: 24px; }
.share-warning { background: #fff7ed; border: 1px solid #fdba74; border-radius: 8px;
                 color: #9a3412; font-size: 12.5px; line-height: 1.55;
                 padding: 10px 12px; margin: 0 0 22px 0; }
.share-warning strong { color: #7c2d12; }
.nav-toc { display: flex; flex-wrap: wrap; gap: 8px; margin: 20px 0 28px 0; padding: 14px;
           background: white; border-radius: 8px; border: 1px solid #e2e8f0; }
.nav-toc a { font-size: 12px; color: #64748b; text-decoration: none; padding: 6px 10px;
             border-radius: 6px; background: #f1f5f9; transition: all .15s; }
.nav-toc a:hover { background: #e2e8f0; color: #334155; }
.stats-row { display: flex; gap: 20px; margin-bottom: 32px; padding: 18px 0;
             border-top: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0; flex-wrap: wrap; }
.stat { text-align: center; min-width: 90px; }
.stat-value { font-size: 22px; font-weight: 700; color: #0f172a; }
.stat-label { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.5px; }
.exec-summary { background: #fffdf7; border: 1px solid #d6b16a; border-radius: 14px;
                padding: 22px; margin: 10px 0 28px 0; box-shadow: 0 10px 30px rgba(120, 83, 22, .06); }
.exec-kicker { font-size: 11px; color: #8a5a12; font-weight: 700; letter-spacing: .12em;
               text-transform: uppercase; margin-bottom: 8px; }
.exec-headline { font-size: 23px; line-height: 1.25; color: #1f2937; font-weight: 750; margin-bottom: 8px; }
.exec-one { font-size: 14px; color: #6b4f1d; margin-bottom: 16px; }
.change-card { border-top: 1px solid #ead9b3; padding-top: 14px; margin-top: 14px; }
.change-title { font-size: 15px; font-weight: 700; color: #0f172a; margin-bottom: 6px; }
.change-meta { font-size: 13px; color: #475569; line-height: 1.55; margin-bottom: 5px; }
.change-action { font-size: 13px; color: #075985; background: #f0f9ff; border: 1px solid #bae6fd;
                 border-radius: 7px; padding: 8px 10px; margin-top: 8px; }
.priority-list { background: white; border: 1px solid #dbe4ef; border-radius: 12px; padding: 16px; margin-bottom: 18px; }
.priority-intro { font-size: 13.5px; color: #475569; margin-bottom: 12px; }
.priority-item { display: grid; grid-template-columns: 42px 1fr; gap: 12px; padding: 12px 0;
                 border-top: 1px solid #eef2f7; }
.priority-item:first-of-type { border-top: none; padding-top: 0; }
.priority-rank { width: 34px; height: 34px; border-radius: 50%; background: #0f172a; color: white;
                 display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 14px; }
.priority-name { font-weight: 700; color: #0f172a; font-size: 15px; margin-bottom: 4px; }
.priority-tags { font-size: 11px; color: #64748b; margin-bottom: 4px; }
.priority-detail { font-size: 13px; color: #475569; line-height: 1.55; }
.score-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(145px, 1fr)); gap: 10px; margin: 12px 0 18px; }
.score-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 12px; }
.score-value { font-size: 24px; font-weight: 750; color: #0f172a; }
.score-dim { font-size: 13px; font-weight: 700; color: #334155; margin-bottom: 4px; }
.score-note { font-size: 12px; color: #64748b; line-height: 1.45; }
.at-a-glance { background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
               border: 1px solid #f59e0b; border-radius: 12px; padding: 18px 22px; margin-bottom: 28px; }
.glance-title { font-size: 16px; font-weight: 700; color: #92400e; margin-bottom: 12px; }
.glance-section { font-size: 14px; color: #78350f; line-height: 1.65; margin-bottom: 10px; }
.glance-section strong { color: #92400e; }
.project-area { background: white; border: 1px solid #e2e8f0; border-radius: 8px;
                padding: 14px 16px; margin-bottom: 10px; }
.area-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
.area-name { font-weight: 600; font-size: 15px; color: #0f172a; }
.area-count { font-size: 12px; color: #64748b; background: #f1f5f9; padding: 2px 8px; border-radius: 4px; }
.area-desc { font-size: 13.5px; color: #475569; line-height: 1.55; }
.narrative { background: white; border: 1px solid #e2e8f0; border-radius: 8px;
             padding: 18px; margin-bottom: 16px; }
.narrative p { margin-bottom: 10px; font-size: 14px; color: #475569; line-height: 1.7; }
.key-insight { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px;
               padding: 10px 14px; margin-top: 10px; font-size: 13.5px; color: #166534; }
.section-intro { font-size: 13.5px; color: #64748b; margin-bottom: 14px; }
.big-win { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px;
           padding: 14px; margin-bottom: 10px; }
.big-win-title { font-weight: 600; font-size: 15px; color: #166534; margin-bottom: 6px; }
.big-win-desc { font-size: 13.5px; color: #15803d; line-height: 1.55; }
.friction-category { background: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px;
                     padding: 14px; margin-bottom: 12px; }
.friction-title { font-weight: 600; font-size: 15px; color: #991b1b; margin-bottom: 6px; }
.friction-desc { font-size: 13.5px; color: #7f1d1d; margin-bottom: 8px; }
.friction-examples { margin: 0 0 0 18px; font-size: 13px; color: #334155; }
.friction-examples li { margin-bottom: 4px; }
.claude-md-section { background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px;
                     padding: 14px; margin-bottom: 16px; }
.claude-md-section h3 { font-size: 14px; font-weight: 600; color: #1e40af; margin: 0 0 10px 0; }
.claude-md-item { padding: 10px 0; border-bottom: 1px solid #dbeafe; }
.claude-md-item:last-child { border-bottom: none; }
.cmd-code { background: white; padding: 8px 12px; border-radius: 4px; font-size: 12.5px;
            color: #1e40af; border: 1px solid #bfdbfe; font-family: ui-monospace, monospace;
            display: block; white-space: pre-wrap; word-break: break-word; }
.cmd-why { font-size: 12px; color: #64748b; padding-top: 6px; }
.feature-card, .pattern-card, .horizon-card { border-radius: 8px; padding: 14px; margin-bottom: 10px; }
.feature-card { background: #f0fdf4; border: 1px solid #86efac; }
.pattern-card { background: #f0f9ff; border: 1px solid #7dd3fc; }
.horizon-card { background: linear-gradient(135deg, #faf5ff 0%, #f5f3ff 100%);
                border: 1px solid #c4b5fd; }
.feature-title, .pattern-title, .horizon-title { font-weight: 600; font-size: 15px;
                                                 color: #0f172a; margin-bottom: 6px; }
.horizon-title { color: #5b21b6; }
.feature-oneliner, .pattern-summary { font-size: 13.5px; color: #475569; margin-bottom: 6px; }
.feature-why, .pattern-detail, .horizon-possible { font-size: 13px; color: #334155; line-height: 1.55; }
.copyable-prompt, .example-code, .feature-code { background: #f8fafc; padding: 10px 12px;
                                                 border-radius: 4px; font-family: ui-monospace, monospace;
                                                 font-size: 12px; color: #334155; border: 1px solid #e2e8f0;
                                                 white-space: pre-wrap; line-height: 1.5; margin-top: 8px;
                                                 overflow-x: auto; }
.prompt-label { font-size: 11px; font-weight: 600; text-transform: uppercase;
                color: #64748b; margin-top: 8px; margin-bottom: 4px; }
.chart-card { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; margin-bottom: 14px; }
.charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 16px 0; }
.chart-title { font-size: 12px; font-weight: 600; color: #64748b;
               text-transform: uppercase; margin-bottom: 10px; letter-spacing: .5px; }
.bar-row { display: flex; align-items: center; margin-bottom: 5px; }
.bar-label { width: 110px; font-size: 11.5px; color: #475569; flex-shrink: 0;
             overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.bar-track { flex: 1; height: 6px; background: #f1f5f9; border-radius: 3px; margin: 0 8px; }
.bar-fill { height: 100%; border-radius: 3px; background: #6366f1; }
.bar-fill.c1 { background: #6366f1; } /* indigo */
.bar-fill.c2 { background: #10b981; } /* emerald */
.bar-fill.c3 { background: #f59e0b; } /* amber */
.bar-fill.c4 { background: #8b5cf6; } /* violet */
.bar-fill.c5 { background: #0891b2; } /* cyan */
.bar-value { width: 36px; font-size: 11px; font-weight: 500; color: #64748b; text-align: right; }
.fun-ending { background: linear-gradient(135deg, #fdf2f8 0%, #fce7f3 100%);
              border: 1px solid #f9a8d4; border-radius: 12px; padding: 16px 20px; margin-top: 28px; }
.fun-headline { font-weight: 700; color: #9d174d; font-size: 15px; margin-bottom: 6px; }
.fun-detail { font-size: 13px; color: #831843; line-height: 1.55; }
@media (max-width: 720px) { .charts-row { grid-template-columns: 1fr; } body { padding: 24px 16px; } }
@media print {
  body { background: white; padding: 0; }
  .nav-toc { display: none; }
  .at-a-glance, .project-area, .narrative, .big-win, .friction-category,
  .feature-card, .pattern-card, .horizon-card, .claude-md-section, .chart-card,
  .fun-ending { page-break-inside: avoid; }
}
"""


def _esc(s) -> str:
    if s is None:
        return ""
    return html.escape(str(s))


def _as_dict(v) -> dict:
    return v if isinstance(v, dict) else {}


def _as_list(v) -> list:
    return v if isinstance(v, list) else []


def _text(v) -> str:
    return "" if v is None else str(v)


_BAR_COLOR_CYCLE = ("c1", "c2", "c3", "c4", "c5")


def _bar_chart(title: str, counts: dict[str, int], top_n: int = 8, color_class: str | None = None) -> str:
    """Render a horizontal bar chart card.

    `color_class`: if provided, all bars share that colour (kept for callers
    that want consistent per-section accent). If None, cycle through
    `_BAR_COLOR_CYCLE` so the top bars get visual differentiation — closer to
    the original /insights aesthetic.
    """
    if not isinstance(counts, dict) or not counts:
        return ""
    numeric_items = []
    for k, v in counts.items():
        try:
            n = float(v)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(n) or n <= 0:
            continue
        display = int(n) if n.is_integer() else n
        numeric_items.append((k, n, display))
    items = sorted(numeric_items, key=lambda x: -x[1])[:top_n]
    if not items:
        return ""
    max_v = max(v for _, v, _ in items) or 1
    rows = []
    for idx, (k, v, display) in enumerate(items):
        pct = int(round(v / max_v * 100))
        cc = color_class or _BAR_COLOR_CYCLE[idx % len(_BAR_COLOR_CYCLE)]
        rows.append(
            f'<div class="bar-row">'
            f'<span class="bar-label">{_esc(k)}</span>'
            f'<span class="bar-track"><span class="bar-fill {cc}" style="width:{pct}%"></span></span>'
            f'<span class="bar-value">{_esc(display)}</span></div>'
        )
    return (
        f'<div class="chart-card"><div class="chart-title">{_esc(title)}</div>'
        + "".join(rows)
        + "</div>"
    )


def _section(anchor: str, title: str, body: str) -> str:
    """Wrap a section in <h2>. Returns empty string if body has no content —
    a dangling header with no body looks broken and pads the TOC."""
    if not body or not body.strip():
        return ""
    return f'<h2 id="{anchor}">{_esc(title)}</h2>\n{body}'


def _is_zh(report: dict) -> bool:
    return str(_detect_lang(report)).lower().startswith("zh")


def _agent_display(agent: object) -> str:
    raw = str(agent or "Agent")
    names = {
        "claude-code": "Claude Code",
        "codex": "Codex",
        "gemini": "Gemini CLI",
        "opencode": "OpenCode",
    }
    return names.get(raw, raw.replace("-", " ").title())


def _executive_summary(report: dict) -> str:
    ex = _as_dict(report.get("executive_summary"))
    if not ex:
        return ""
    zh = _is_zh(report)
    changes = []
    for item in _as_list(ex.get("top_changes")):
        if not isinstance(item, dict):
            continue
        parts = []
        if item.get("why_it_matters"):
            label = "为什么重要：" if zh else "Why it matters: "
            parts.append(f'<div class="change-meta"><strong>{_esc(label)}</strong>{_esc(item["why_it_matters"])}</div>')
        if item.get("evidence"):
            label = "证据：" if zh else "Evidence: "
            parts.append(f'<div class="change-meta"><strong>{_esc(label)}</strong>{_esc(item["evidence"])}</div>')
        if item.get("action"):
            label = "下一步：" if zh else "Next step: "
            parts.append(f'<div class="change-action"><strong>{_esc(label)}</strong>{_esc(item["action"])}</div>')
        changes.append(
            '<div class="change-card">'
            f'<div class="change-title">{_esc(item.get("title", ""))}</div>'
            + "".join(parts)
            + '</div>'
        )
    if not (ex.get("headline") or ex.get("one_sentence") or changes):
        return ""
    return (
        '<div class="exec-summary">'
        f'<div class="exec-kicker">{_esc("执行摘要" if zh else "Executive Summary")}</div>'
        f'<div class="exec-headline">{_esc(ex.get("headline", ""))}</div>'
        f'<div class="exec-one">{_esc(ex.get("one_sentence", ""))}</div>'
        + "".join(changes)
        + '</div>'
    )


def _priority_ladder(report: dict) -> str:
    ladder = _as_dict(report.get("priority_ladder"))
    items = _as_list(ladder.get("items"))
    if not items:
        return ""
    zh = _is_zh(report)
    rows = []
    for item in items:
        if not isinstance(item, dict):
            continue
        impact = "影响" if zh else "Impact"
        effort = "成本" if zh else "Effort"
        next_step = "下一步：" if zh else "Next step: "
        rows.append(
            '<div class="priority-item">'
            f'<div class="priority-rank">{_esc(item.get("rank", ""))}</div>'
            '<div>'
            f'<div class="priority-name">{_esc(item.get("name", ""))}</div>'
            f'<div class="priority-tags">{_esc(impact)}: {_esc(item.get("impact", ""))} · {_esc(effort)}: {_esc(item.get("effort", ""))}</div>'
            f'<div class="priority-detail">{_esc(item.get("reason", ""))}</div>'
            f'<div class="priority-detail"><strong>{_esc(next_step)}</strong>{_esc(item.get("next_step", ""))}</div>'
            '</div></div>'
        )
    intro = f'<div class="priority-intro">{_esc(ladder.get("intro", ""))}</div>' if ladder.get("intro") else ""
    return '<div class="priority-list">' + intro + "".join(rows) + '</div>'


def _scorecard(report: dict) -> str:
    scorecard = _as_dict(report.get("scorecard"))
    scores = _as_list(scorecard.get("scores"))
    if not scores:
        return ""
    intro = f'<p class="section-intro">{_esc(scorecard.get("summary", ""))}</p>' if scorecard.get("summary") else ""
    cards = []
    for s in scores:
        if not isinstance(s, dict):
            continue
        cards.append(
            '<div class="score-card">'
            f'<div class="score-value">{_esc(s.get("score", ""))}/10</div>'
            f'<div class="score-dim">{_esc(s.get("dimension", ""))}</div>'
            f'<div class="score-note">{_esc(s.get("note", ""))}</div>'
            '</div>'
        )
    return intro + '<div class="score-grid">' + "".join(cards) + '</div>'


def _glance(report: dict) -> str:
    g = _as_dict(report.get("at_a_glance"))
    if not g:
        return ""
    parts = []
    zh = _is_zh(report)
    labels = [
        ("有效模式" if zh else "What's working", "whats_working"),
        ("主要阻碍" if zh else "What's hindering", "whats_hindering"),
        ("快速改进" if zh else "Quick wins", "quick_wins"),
        ("进阶工作流" if zh else "Ambitious workflows", "ambitious_workflows"),
    ]
    for label, key in labels:
        if g.get(key):
            parts.append(
                f'<div class="glance-section"><strong>{_esc(label)}:</strong> {_esc(g[key])}</div>'
            )
    if not parts:
        return ""
    return (
        f'<div class="at-a-glance"><div class="glance-title">{_esc("快速概览" if zh else "At a Glance")}</div>'
        + "".join(parts)
        + "</div>"
    )


def _project_areas(report: dict) -> str:
    # Accept either {"project_areas": {"areas": [...]}} or {"project_areas": [...]}.
    raw = report.get("project_areas")
    if isinstance(raw, dict):
        pa = _as_list(raw.get("areas"))
    elif isinstance(raw, list):
        pa = raw
    else:
        pa = []
    if not pa:
        return ""
    zh = _is_zh(report)
    rows = []
    for a in pa:
        if not isinstance(a, dict):
            continue
        rows.append(
            '<div class="project-area">'
            '<div class="area-header">'
            f'<span class="area-name">{_esc(a.get("name", ""))}</span>'
            f'<span class="area-count">{_esc(a.get("session_count", "?"))} {"个会话" if zh else "sessions"}</span>'
            '</div>'
            f'<div class="area-desc">{_esc(a.get("description", ""))}</div>'
            '</div>'
        )
    return "".join(rows)


def _interaction(report: dict) -> str:
    i = _as_dict(report.get("interaction_style"))
    if not i:
        return ""
    n = _text(i.get("narrative")).strip()
    key_pattern = _text(i.get("key_pattern")).strip()
    if not n and not key_pattern:
        return ""
    # split paragraphs on blank lines
    paras = [p.strip() for p in n.split("\n\n") if p.strip()]
    body = "".join(f"<p>{_esc(p)}</p>" for p in paras) if paras else f"<p>{_esc(n)}</p>"
    insight = ""
    if key_pattern:
        label = "核心模式" if _is_zh(report) else "Key pattern"
        insight = f'<div class="key-insight"><strong>{_esc(label)}:</strong> {_esc(key_pattern)}</div>'
    return f'<div class="narrative">{body}{insight}</div>'


def _what_works(report: dict) -> str:
    w = _as_dict(report.get("execution_strengths")) or _as_dict(report.get("what_works"))
    intro = w.get("intro") or ""
    items = _as_list(w.get("impressive_workflows"))
    body = ""
    if intro:
        body += f'<p class="section-intro">{_esc(intro)}</p>'
    for it in items:
        if not isinstance(it, dict):
            continue
        body += (
            '<div class="big-win">'
            f'<div class="big-win-title">{_esc(it.get("title", ""))}</div>'
            f'<div class="big-win-desc">{_esc(it.get("description", ""))}</div>'
            '</div>'
        )
    return body


def _friction(report: dict) -> str:
    f = _as_dict(report.get("reliability_risks")) or _as_dict(report.get("friction_analysis"))
    body = ""
    if f.get("intro"):
        body += f'<p class="section-intro">{_esc(f["intro"])}</p>'
    for c in _as_list(f.get("categories")):
        if not isinstance(c, dict):
            continue
        ex_html = ""
        examples = _as_list(c.get("examples"))
        if examples:
            ex_html = '<ul class="friction-examples">' + "".join(
                f"<li>{_esc(x)}</li>" for x in examples
            ) + "</ul>"
        body += (
            '<div class="friction-category">'
            f'<div class="friction-title">{_esc(c.get("category", ""))}</div>'
            f'<div class="friction-desc">{_esc(c.get("description", ""))}</div>'
            f'{ex_html}</div>'
        )
    return body


def _suggestions(report: dict) -> str:
    s = _as_dict(report.get("suggestions"))
    zh = _is_zh(report)
    body = ""

    cm = [it for it in (_as_list(s.get("guidance_file_additions")) or _as_list(s.get("claude_md_additions"))) if isinstance(it, dict)]
    if cm:
        agent = _as_dict(report.get("header")).get("agent")
        if zh:
            heading = "建议加入的规则 / 命令模板"
        elif agent == "opencode":
            heading = "Suggested AGENTS.md / OpenCode guidance additions"
        else:
            heading = "Suggested guidance file additions"
        items = ""
        for it in cm:
            target = it.get("target_file") or it.get("target") or ""
            target_html = ""
            if target:
                target_html = f'<div class="cmd-why"><strong>Target:</strong> {_esc(target)}</div>'
            items += (
                '<div class="claude-md-item">'
                f'<code class="cmd-code">{_esc(it.get("addition", ""))}</code>'
                f"{target_html}"
                f'<div class="cmd-why"><strong>Why:</strong> {_esc(it.get("why", ""))}</div>'
                "</div>"
            )
        body += (
            '<div class="claude-md-section">'
            f"<h3>{_esc(heading)}</h3>"
            f"{items}</div>"
        )

    ft = _as_list(s.get("capabilities_to_try")) or _as_list(s.get("features_to_try"))
    for it in ft:
        if not isinstance(it, dict):
            continue
        ex = ""
        example = it.get("example") or it.get("example_code")
        if example:
            ex_label = "示例" if zh else "Example"
            ex = f'<div class="prompt-label">{_esc(ex_label)}</div><pre class="feature-code"><code>{_esc(example)}</code></pre>'
        body += (
            '<div class="feature-card">'
            f'<div class="feature-title">{_esc(it.get("capability") or it.get("feature", ""))}</div>'
            f'<div class="feature-oneliner">{_esc(it.get("one_liner", ""))}</div>'
            f'<div class="feature-why">{_esc(it.get("why_for_you", ""))}</div>'
            f"{ex}</div>"
        )

    up = _as_list(s.get("usage_patterns"))
    for it in up:
        if not isinstance(it, dict):
            continue
        prompt = ""
        if it.get("copyable_prompt"):
            prompt_label = "可复制提示词" if zh else "Copyable prompt"
            prompt = f'<div class="prompt-label">{_esc(prompt_label)}</div><pre class="copyable-prompt">{_esc(it["copyable_prompt"])}</pre>'
        body += (
            '<div class="pattern-card">'
            f'<div class="pattern-title">{_esc(it.get("title", ""))}</div>'
            f'<div class="pattern-summary">{_esc(it.get("suggestion", ""))}</div>'
            f'<div class="pattern-detail">{_esc(it.get("detail", ""))}</div>'
            f"{prompt}</div>"
        )

    return body


def _codex_native_dimensions(report: dict) -> str:
    dims = _as_dict(report.get("opencode_native_dimensions")) or _as_dict(report.get("codex_native_dimensions"))
    if not dims:
        return ""
    zh = _is_zh(report)
    labels = ({
        "instruction_handling": "指令遵循",
        "tool_execution": "工具执行",
        "verification_quality": "验证质量",
        "handoff_quality": "交接质量",
        "autonomy_boundary": "自主边界",
    } if zh else {
        "instruction_handling": "Instruction Handling",
        "tool_execution": "Tool Execution",
        "verification_quality": "Verification Quality",
        "handoff_quality": "Handoff Quality",
        "autonomy_boundary": "Autonomy Boundary",
    })
    body = ""
    for key, label in labels.items():
        item = _as_dict(dims.get(key))
        if not item:
            continue
        examples = _as_list(item.get("examples"))
        ex_html = ""
        if examples:
            ex_html = '<ul class="friction-examples">' + "".join(
                f"<li>{_esc(x)}</li>" for x in examples
            ) + "</ul>"
        body += (
            '<div class="project-area">'
            '<div class="area-header">'
            f'<span class="area-name">{_esc(label)}</span>'
            '</div>'
            f'<div class="area-desc">{_esc(item.get("summary", ""))}</div>'
            f'{ex_html}</div>'
        )
    return body


def _horizon(report: dict) -> str:
    h = _as_dict(report.get("on_the_horizon"))
    zh = _is_zh(report)
    body = ""
    if h.get("intro"):
        body += f'<p class="section-intro">{_esc(h["intro"])}</p>'
    for op in _as_list(h.get("opportunities")):
        if not isinstance(op, dict):
            continue
        prompt = ""
        if op.get("copyable_prompt"):
            prompt_label = "可复制提示词" if zh else "Copyable prompt"
            prompt = f'<div class="prompt-label">{_esc(prompt_label)}</div><pre class="copyable-prompt">{_esc(op["copyable_prompt"])}</pre>'
        how = ""
        if op.get("how_to_try"):
            how_label = "如何尝试：" if zh else "How to try: "
            how = f'<div class="feature-why" style="margin-top:8px;"><strong>{_esc(how_label)}</strong>{_esc(op["how_to_try"])}</div>'
        body += (
            '<div class="horizon-card">'
            f'<div class="horizon-title">{_esc(op.get("title", ""))}</div>'
            f'<div class="horizon-possible">{_esc(op.get("whats_possible", ""))}</div>'
            f"{how}{prompt}</div>"
        )
    return body


def _success_metrics(report: dict) -> str:
    metrics = _as_list(report.get("success_metrics"))
    if not metrics:
        return ""
    zh = _is_zh(report)
    intro = (
        "下一份 insights 不应该只继续给建议，而要用这些指标判断 agent 使用方式是否真的改变。"
        if zh else
        "The next insights report should judge whether usage actually changed, not just repeat suggestions."
    )
    body = f'<p class="section-intro">{_esc(intro)}</p>'
    for m in metrics:
        if not isinstance(m, dict):
            continue
        target = "目标" if zh else "Target"
        body += (
            '<div class="project-area">'
            '<div class="area-header">'
            f'<span class="area-name">{_esc(m.get("metric", ""))}</span>'
            f'<span class="area-count">{_esc(target)} {_esc(m.get("target", ""))}</span>'
            '</div>'
            f'<div class="area-desc">{_esc(m.get("how_to_measure", ""))}</div>'
            '</div>'
        )
    return body


def _stats_row(report: dict) -> str:
    h = _as_dict(report.get("header"))
    zh = _is_zh(report)
    items = [
        ("会话总数" if zh else "Sessions", h.get("total_sessions")),
        ("已分析" if zh else "Analyzed", h.get("analyzed_sessions")),
        ("消息数" if zh else "Messages", h.get("messages")),
        ("时长" if zh else "Hours", h.get("hours")),
        ("提交" if zh else "Commits", h.get("commits")),
        ("Tokens", _short_tokens(h.get("tokens"))),
    ]
    parts = []
    for label, v in items:
        if v in (None, "", 0):
            continue
        parts.append(f'<div class="stat"><div class="stat-value">{_esc(v)}</div><div class="stat-label">{_esc(label)}</div></div>')
    if not parts:
        return ""
    return f'<div class="stats-row">{"".join(parts)}</div>'


def _short_tokens(v) -> str:
    if not v:
        return ""
    try:
        n = int(v)
        if n >= 1_000_000:
            return f"{n / 1_000_000:.1f}M"
        if n >= 1_000:
            return f"{n / 1000:.0f}k"
        return str(n)
    except Exception:
        return str(v)


def _toc(present_anchors: list[tuple[str, str]]) -> str:
    if not present_anchors:
        return ""
    return '<div class="nav-toc">' + "".join(
        f'<a href="#{a}">{_esc(t)}</a>' for a, t in present_anchors
    ) + "</div>"


def _share_warning(report: dict) -> str:
    if _is_zh(report):
        return (
            '<div class="share-warning"><strong>分享前复核：</strong>'
            '这份报告可能包含本地会话里的 prompt、文件路径或工具输出。'
            '转发前请删除密钥、客户信息或内部细节。</div>'
        )
    return (
        '<div class="share-warning"><strong>Review before sharing:</strong> '
        'this report may include prompts, file paths, or tool output from your local sessions. '
        'Remove secrets or private customer/internal details before sending it elsewhere.</div>'
    )


def _charts(report: dict) -> str:
    s = _as_dict(report.get("stats"))
    parts = []
    zh = _is_zh(report)
    # color_class=None lets _bar_chart cycle through the palette for visual
    # contrast inside each chart, matching the original /insights look.
    if s.get("tool_counts"):
        parts.append(_bar_chart("工具使用" if zh else "Top tools", s["tool_counts"]))
    if s.get("language_counts"):
        parts.append(_bar_chart("文件语言" if zh else "Languages", s["language_counts"]))
    if s.get("goal_categories"):
        parts.append(_bar_chart("目标类型" if zh else "Goal categories", s["goal_categories"]))
    if s.get("friction_counts"):
        parts.append(_bar_chart("摩擦模式" if zh else "Friction patterns", s["friction_counts"]))
    if not parts:
        return ""
    grid = '<div class="charts-row">' + "".join(parts) + "</div>"
    return grid


def _fun(report: dict) -> str:
    f = _as_dict(report.get("fun_ending"))
    if not f.get("headline"):
        return ""
    return (
        '<div class="fun-ending">'
        f'<div class="fun-headline">🎈 {_esc(f.get("headline", ""))}</div>'
        f'<div class="fun-detail">{_esc(f.get("detail", ""))}</div>'
        "</div>"
    )


def _detect_lang(data: dict) -> str:
    """Honour `header.lang` if given; otherwise sample narrative text and pick
    `zh` when >25% of the characters are CJK, else `en`.

    Default `lang="en"` hurts assistive tech and browser language detection
    when the LLM wrote a Chinese report.
    """
    header = _as_dict(data.get("header"))
    explicit = header.get("lang")
    if explicit:
        return str(explicit)
    sample = " ".join([
        str(_as_dict(data.get("at_a_glance")).get("whats_working", "")),
        str(_as_dict(data.get("interaction_style")).get("narrative", "")),
        str((_as_dict(data.get("reliability_risks")) or _as_dict(data.get("friction_analysis"))).get("intro", "")),
        str(header.get("title", "")),
    ])[:2000]
    if not sample:
        return "en"
    cjk = sum(1 for ch in sample if "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿")
    return "zh" if cjk / max(len(sample), 1) > 0.25 else "en"


def render(data_path: str, out_path: str) -> int:
    data = json.loads(Path(data_path).expanduser().read_text(encoding="utf-8"))
    header = _as_dict(data.get("header"))
    title = header.get("title") or f"{_agent_display(header.get('agent'))} Insights"
    lang = _detect_lang(data)
    zh = str(lang).lower().startswith("zh")
    subtitle_parts = []
    if header.get("agent"):
        subtitle_parts.append(_esc(_agent_display(header["agent"])))
    if header.get("date_range"):
        subtitle_parts.append(_esc(header["date_range"]))
    if header.get("total_sessions"):
        subtitle_parts.append(f"{header['total_sessions']} {'个会话' if zh else 'sessions'}")
    subtitle = " · ".join(subtitle_parts)

    agent = str(header.get("agent") or "")
    dimension_title_en = "OpenCode Execution Dimensions" if agent == "opencode" else "Execution Dimensions"
    section_titles = {
        "priority-ladder": "优先级阶梯",
        "scorecard": "当前能力评分",
        "project-areas": "项目领域",
        "interaction": "协作风格",
        "codex-dimensions": "执行维度",
        "what-works": "表现突出的工作流",
        "friction": "风险与摩擦",
        "suggestions": "建议",
        "on-the-horizon": "下一步机会",
        "success-metrics": "7 天验收指标",
        "charts": "统计图表",
    } if zh else {
        "priority-ladder": "Priority Ladder",
        "scorecard": "Scorecard",
        "project-areas": "Project Areas",
        "interaction": "Interaction Style",
        "codex-dimensions": "Codex-Native Dimensions",
        "what-works": "Impressive Things You Did",
        "friction": "Where Things Go Wrong",
        "suggestions": "Suggestions",
        "on-the-horizon": "On the Horizon",
        "success-metrics": "Success Metrics",
        "charts": "Charts",
    }
    if not zh:
        section_titles["codex-dimensions"] = dimension_title_en
    # Pre-compute each section's body so we can build an accurate TOC.
    section_specs = [
        ("priority-ladder", section_titles["priority-ladder"], _priority_ladder(data)),
        ("scorecard", section_titles["scorecard"], _scorecard(data)),
        ("project-areas", section_titles["project-areas"], _project_areas(data)),
        ("interaction", section_titles["interaction"], _interaction(data)),
        ("codex-dimensions", section_titles["codex-dimensions"], _codex_native_dimensions(data)),
        ("what-works", section_titles["what-works"], _what_works(data)),
        ("friction", section_titles["friction"], _friction(data)),
        ("suggestions", section_titles["suggestions"], _suggestions(data)),
        ("on-the-horizon", section_titles["on-the-horizon"], _horizon(data)),
        ("success-metrics", section_titles["success-metrics"], _success_metrics(data)),
        ("charts", section_titles["charts"], _charts(data)),
    ]
    present = [(a, t) for a, t, b in section_specs if b and b.strip()]

    body = []
    body.append(f"<h1>{_esc(title)}</h1>")
    if subtitle:
        body.append(f'<div class="subtitle">{subtitle}</div>')
    body.append(_share_warning(data))
    body.append(_toc(present))
    body.append(_stats_row(data))
    body.append(_executive_summary(data))
    body.append(_glance(data))
    for anchor, title_, body_ in section_specs:
        body.append(_section(anchor, title_, body_))
    body.append(_fun(data))

    html_doc = f"""<!DOCTYPE html>
<html lang="{_esc(lang)}">
<head>
<meta charset="utf-8">
<title>{_esc(title)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{CSS}</style>
</head>
<body>
<div class="container">
{''.join(b for b in body if b)}
</div>
</body>
</html>"""

    out = Path(out_path).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc, encoding="utf-8")
    sys.stderr.write(f"Wrote {out}\n")
    return 0


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    raise SystemExit(render(a.data, a.out))
