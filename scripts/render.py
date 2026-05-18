"""Render the aggregated report.json into a single-file HTML.

The HTML is self-contained (no JS framework, inline CSS). It mirrors the
section structure of Claude Code's /insights output. CSS lives in
`render_css.py` so this module stays focused on Python rendering logic.
"""
from __future__ import annotations

import html
import json
import math
import sys
from pathlib import Path

from render_css import CSS  # type: ignore[import-not-found]


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


_BAR_COLOR_CYCLE = ("c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8")


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
        '<div class="exec-summary" id="exec-summary">'
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
        f'<div class="at-a-glance" id="at-a-glance"><div class="glance-title">{_esc("快速概览" if zh else "At a Glance")}</div>'
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
    except Exception:
        return str(v)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        # Round to thousands first; only promote to "M" if that rounded value
        # would spill into a 4-digit k label (e.g. 999_999 → 1000k). This keeps
        # the k→M transition monotonic — 949_999 and 950_000 both render as
        # "950k", and the jump to "1.0M" only fires once round() reaches 1000.
        thousands = round(n / 1000)
        if thousands >= 1000:
            return f"{n / 1_000_000:.1f}M"
        return f"{thousands}k"
    if n >= 1_000:
        # 1k–10k: keep one decimal so 1500 reads as "1.5k" rather than "2k",
        # but trim a trailing ".0" so 1000 still reads as "1k".
        formatted = f"{n / 1000:.1f}"
        if formatted.endswith(".0"):
            formatted = formatted[:-2]
        return f"{formatted}k"
    return str(n)


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
        "exec-summary": "执行摘要",
        "at-a-glance": "快速概览",
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
        "exec-summary": "Executive Summary",
        "at-a-glance": "At a Glance",
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
    exec_summary_html = _executive_summary(data)
    glance_html = _glance(data)
    present = []
    if exec_summary_html:
        present.append(("exec-summary", section_titles["exec-summary"]))
    if glance_html:
        present.append(("at-a-glance", section_titles["at-a-glance"]))
    present.extend((a, t) for a, t, b in section_specs if b and b.strip())

    body = []
    body.append(f"<h1>{_esc(title)}</h1>")
    if subtitle:
        body.append(f'<div class="subtitle">{subtitle}</div>')
    body.append(_share_warning(data))
    body.append(_toc(present))
    body.append(_stats_row(data))
    body.append(exec_summary_html)
    body.append(glance_html)
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
