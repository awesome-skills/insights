"""Render the aggregated report.json into a single-file HTML.

The HTML is self-contained (no JS framework, inline CSS). It mirrors the
section structure of Claude Code's /insights output.
"""
from __future__ import annotations

import html
import json
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


_BAR_COLOR_CYCLE = ("c1", "c2", "c3", "c4", "c5")


def _bar_chart(title: str, counts: dict[str, int], top_n: int = 8, color_class: str | None = None) -> str:
    """Render a horizontal bar chart card.

    `color_class`: if provided, all bars share that colour (kept for callers
    that want consistent per-section accent). If None, cycle through
    `_BAR_COLOR_CYCLE` so the top bars get visual differentiation — closer to
    the original /insights aesthetic.
    """
    if not counts:
        return ""
    items = sorted(counts.items(), key=lambda x: -x[1])[:top_n]
    if not items:
        return ""
    max_v = max(v for _, v in items) or 1
    rows = []
    for idx, (k, v) in enumerate(items):
        pct = int(round(v / max_v * 100))
        cc = color_class or _BAR_COLOR_CYCLE[idx % len(_BAR_COLOR_CYCLE)]
        rows.append(
            f'<div class="bar-row">'
            f'<span class="bar-label">{_esc(k)}</span>'
            f'<span class="bar-track"><span class="bar-fill {cc}" style="width:{pct}%"></span></span>'
            f'<span class="bar-value">{v}</span></div>'
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


def _glance(report: dict) -> str:
    g = report.get("at_a_glance") or {}
    if not g:
        return ""
    parts = []
    for label, key in [
        ("✅ What's working", "whats_working"),
        ("⚠️ What's hindering", "whats_hindering"),
        ("⚡ Quick wins", "quick_wins"),
        ("🚀 Ambitious workflows", "ambitious_workflows"),
    ]:
        if g.get(key):
            parts.append(
                f'<div class="glance-section"><strong>{_esc(label)}:</strong> {_esc(g[key])}</div>'
            )
    if not parts:
        return ""
    return (
        '<div class="at-a-glance"><div class="glance-title">At a Glance</div>'
        + "".join(parts)
        + "</div>"
    )


def _project_areas(report: dict) -> str:
    # Accept either {"project_areas": {"areas": [...]}} or {"project_areas": [...]}.
    raw = report.get("project_areas")
    if isinstance(raw, dict):
        pa = raw.get("areas") or []
    elif isinstance(raw, list):
        pa = raw
    else:
        pa = []
    if not pa:
        return ""
    rows = []
    for a in pa:
        rows.append(
            '<div class="project-area">'
            '<div class="area-header">'
            f'<span class="area-name">{_esc(a.get("name", ""))}</span>'
            f'<span class="area-count">{_esc(a.get("session_count", "?"))} sessions</span>'
            '</div>'
            f'<div class="area-desc">{_esc(a.get("description", ""))}</div>'
            '</div>'
        )
    return "".join(rows)


def _interaction(report: dict) -> str:
    i = report.get("interaction_style") or {}
    if not i:
        return ""
    n = (i.get("narrative") or "").strip()
    # split paragraphs on blank lines
    paras = [p.strip() for p in n.split("\n\n") if p.strip()]
    body = "".join(f"<p>{_esc(p)}</p>" for p in paras) if paras else f"<p>{_esc(n)}</p>"
    insight = ""
    if i.get("key_pattern"):
        insight = f'<div class="key-insight"><strong>Key pattern:</strong> {_esc(i["key_pattern"])}</div>'
    return f'<div class="narrative">{body}{insight}</div>'


def _what_works(report: dict) -> str:
    w = report.get("what_works") or {}
    intro = w.get("intro") or ""
    items = w.get("impressive_workflows") or []
    body = ""
    if intro:
        body += f'<p class="section-intro">{_esc(intro)}</p>'
    for it in items:
        body += (
            '<div class="big-win">'
            f'<div class="big-win-title">{_esc(it.get("title", ""))}</div>'
            f'<div class="big-win-desc">{_esc(it.get("description", ""))}</div>'
            '</div>'
        )
    return body


def _friction(report: dict) -> str:
    f = report.get("friction_analysis") or {}
    body = ""
    if f.get("intro"):
        body += f'<p class="section-intro">{_esc(f["intro"])}</p>'
    for c in f.get("categories") or []:
        ex_html = ""
        if c.get("examples"):
            ex_html = '<ul class="friction-examples">' + "".join(
                f"<li>{_esc(x)}</li>" for x in c["examples"]
            ) + "</ul>"
        body += (
            '<div class="friction-category">'
            f'<div class="friction-title">{_esc(c.get("category", ""))}</div>'
            f'<div class="friction-desc">{_esc(c.get("description", ""))}</div>'
            f'{ex_html}</div>'
        )
    return body


def _suggestions(report: dict) -> str:
    s = report.get("suggestions") or {}
    body = ""

    cm = s.get("claude_md_additions") or []
    if cm:
        items = "".join(
            '<div class="claude-md-item">'
            f'<code class="cmd-code">{_esc(it.get("addition", ""))}</code>'
            f'<div class="cmd-why"><strong>Why:</strong> {_esc(it.get("why", ""))}</div>'
            "</div>"
            for it in cm
        )
        body += (
            '<div class="claude-md-section">'
            "<h3>Suggested CLAUDE.md / AGENTS.md additions</h3>"
            f"{items}</div>"
        )

    ft = s.get("features_to_try") or []
    for it in ft:
        ex = ""
        if it.get("example_code"):
            ex = f'<div class="prompt-label">Example</div><pre class="feature-code"><code>{_esc(it["example_code"])}</code></pre>'
        body += (
            '<div class="feature-card">'
            f'<div class="feature-title">{_esc(it.get("feature", ""))}</div>'
            f'<div class="feature-oneliner">{_esc(it.get("one_liner", ""))}</div>'
            f'<div class="feature-why">{_esc(it.get("why_for_you", ""))}</div>'
            f"{ex}</div>"
        )

    up = s.get("usage_patterns") or []
    for it in up:
        prompt = ""
        if it.get("copyable_prompt"):
            prompt = f'<div class="prompt-label">Copyable prompt</div><pre class="copyable-prompt">{_esc(it["copyable_prompt"])}</pre>'
        body += (
            '<div class="pattern-card">'
            f'<div class="pattern-title">{_esc(it.get("title", ""))}</div>'
            f'<div class="pattern-summary">{_esc(it.get("suggestion", ""))}</div>'
            f'<div class="pattern-detail">{_esc(it.get("detail", ""))}</div>'
            f"{prompt}</div>"
        )

    return body


def _horizon(report: dict) -> str:
    h = report.get("on_the_horizon") or {}
    body = ""
    if h.get("intro"):
        body += f'<p class="section-intro">{_esc(h["intro"])}</p>'
    for op in h.get("opportunities") or []:
        prompt = ""
        if op.get("copyable_prompt"):
            prompt = f'<div class="prompt-label">Copyable prompt</div><pre class="copyable-prompt">{_esc(op["copyable_prompt"])}</pre>'
        how = ""
        if op.get("how_to_try"):
            how = f'<div class="feature-why" style="margin-top:8px;"><strong>How to try:</strong> {_esc(op["how_to_try"])}</div>'
        body += (
            '<div class="horizon-card">'
            f'<div class="horizon-title">{_esc(op.get("title", ""))}</div>'
            f'<div class="horizon-possible">{_esc(op.get("whats_possible", ""))}</div>'
            f"{how}{prompt}</div>"
        )
    return body


def _stats_row(report: dict) -> str:
    h = report.get("header") or {}
    items = [
        ("Sessions", h.get("total_sessions")),
        ("Analyzed", h.get("analyzed_sessions")),
        ("Messages", h.get("messages")),
        ("Hours", h.get("hours")),
        ("Commits", h.get("commits")),
        ("Tokens (M)", _short_tokens(h.get("tokens"))),
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


def _charts(report: dict) -> str:
    s = report.get("stats") or {}
    parts = []
    # color_class=None lets _bar_chart cycle through the palette for visual
    # contrast inside each chart, matching the original /insights look.
    if s.get("tool_counts"):
        parts.append(_bar_chart("Top tools", s["tool_counts"]))
    if s.get("language_counts"):
        parts.append(_bar_chart("Languages", s["language_counts"]))
    if s.get("goal_categories"):
        parts.append(_bar_chart("Goal categories", s["goal_categories"]))
    if s.get("friction_counts"):
        parts.append(_bar_chart("Friction patterns", s["friction_counts"]))
    if not parts:
        return ""
    grid = '<div class="charts-row">' + "".join(parts) + "</div>"
    return grid


def _fun(report: dict) -> str:
    f = report.get("fun_ending") or {}
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
    header = data.get("header") or {}
    explicit = header.get("lang")
    if explicit:
        return str(explicit)
    sample = " ".join([
        str((data.get("at_a_glance") or {}).get("whats_working", "")),
        str((data.get("interaction_style") or {}).get("narrative", "")),
        str((data.get("friction_analysis") or {}).get("intro", "")),
        str(header.get("title", "")),
    ])[:2000]
    if not sample:
        return "en"
    cjk = sum(1 for ch in sample if "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿")
    return "zh" if cjk / max(len(sample), 1) > 0.25 else "en"


def render(data_path: str, out_path: str) -> int:
    data = json.loads(Path(data_path).expanduser().read_text(encoding="utf-8"))
    header = data.get("header", {})
    title = header.get("title") or f"{header.get('agent', 'Agent').replace('-', ' ').title()} Insights"
    lang = _detect_lang(data)
    subtitle_parts = []
    if header.get("agent"):
        subtitle_parts.append(_esc(header["agent"]))
    if header.get("date_range"):
        subtitle_parts.append(_esc(header["date_range"]))
    if header.get("total_sessions"):
        subtitle_parts.append(f"{header['total_sessions']} sessions")
    subtitle = " · ".join(subtitle_parts)

    # Pre-compute each section's body so we can build an accurate TOC.
    section_specs = [
        ("project-areas", "Project Areas", _project_areas(data)),
        ("interaction", "Interaction Style", _interaction(data)),
        ("what-works", "Impressive Things You Did", _what_works(data)),
        ("friction", "Where Things Go Wrong", _friction(data)),
        ("suggestions", "Suggestions", _suggestions(data)),
        ("on-the-horizon", "On the Horizon", _horizon(data)),
        ("charts", "Charts", _charts(data)),
    ]
    present = [(a, t) for a, t, b in section_specs if b and b.strip()]

    body = []
    body.append(f"<h1>{_esc(title)}</h1>")
    if subtitle:
        body.append(f'<div class="subtitle">{subtitle}</div>')
    body.append(_toc(present))
    body.append(_stats_row(data))
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
