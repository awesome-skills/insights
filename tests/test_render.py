"""Tests for HTML rendering. Guard against:
- Empty sections leaking dangling <h2> headers.
- XSS via LLM-generated content.
- Schema shape variations (project_areas as list vs dict).
"""
import json
import re
from pathlib import Path

import pytest

import render  # type: ignore
from render import _short_tokens


@pytest.fixture
def write_and_render(tmp_path):
    def _do(data: dict) -> str:
        p = tmp_path / "report.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        out = tmp_path / "report.html"
        render.render(str(p), str(out))
        return out.read_text(encoding="utf-8")
    return _do


def test_minimal_report_has_no_empty_h2(write_and_render):
    html = write_and_render({"header": {"agent": "test", "total_sessions": 1, "title": "Min"}})
    # No section bodies → no h2 anywhere (even though section_specs walks them all).
    assert re.search(r"<h2[^>]*>[^<]+</h2>", html) is None


def test_full_report_renders_all_sections(write_and_render):
    data = {
        "header": {"agent": "test", "total_sessions": 1, "title": "Full"},
        "at_a_glance": {"whats_working": "x", "whats_hindering": "y",
                        "quick_wins": "z", "ambitious_workflows": "w"},
        "project_areas": {"areas": [{"name": "A", "session_count": 1, "description": "d"}]},
        "interaction_style": {"narrative": "p1", "key_pattern": "k"},
        "what_works": {"intro": "i", "impressive_workflows": [{"title": "t", "description": "d"}]},
        "friction_analysis": {"intro": "i", "categories":
                              [{"category": "c", "description": "d", "examples": ["e1"]}]},
        "suggestions": {"claude_md_additions": [{"addition": "## X", "why": "because"}]},
        "on_the_horizon": {"intro": "i", "opportunities":
                           [{"title": "T", "whats_possible": "p"}]},
        "stats": {"tool_counts": {"Bash": 5}},
    }
    html = write_and_render(data)
    for anchor in ("project-areas", "interaction", "what-works", "friction",
                   "suggestions", "on-the-horizon", "charts"):
        assert f'id="{anchor}"' in html, f"section {anchor} missing"


def test_agent_neutral_report_fields_render(write_and_render):
    data = {
        "header": {"agent": "codex", "title": "Codex"},
        "codex_native_dimensions": {
            "instruction_handling": {"summary": "Followed AGENTS.md", "examples": ["s1"]},
            "verification_quality": {"summary": "Ran tests", "examples": ["s2"]},
        },
        "execution_strengths": {"impressive_workflows": [{"title": "Patch loop", "description": "desc"}]},
        "reliability_risks": {"categories": [{"category": "Weak verification", "description": "desc"}]},
        "suggestions": {
            "guidance_file_additions": [{"target": "AGENTS.md", "addition": "Run tests", "why": "evidence"}],
            "capabilities_to_try": [{"capability": "Codex subagents", "one_liner": "Parallel review", "example": "spawn reviewers"}],
        },
    }
    html = write_and_render(data)
    assert 'id="codex-dimensions"' in html
    assert "Instruction Handling" in html
    assert "Patch loop" in html
    assert "Weak verification" in html
    assert "Run tests" in html
    assert "Codex subagents" in html


def test_xss_payload_escaped(write_and_render):
    data = {
        "header": {"agent": "test", "title": "<script>alert(1)</script>"},
        "project_areas": {"areas":
                          [{"name": "<img src=x onerror=alert(2)>",
                            "session_count": "<svg/onload=alert(3)>",
                            "description": "</title><script>alert(4)</script>"}]},
        "stats": {"tool_counts": {"<script>alert(5)</script>": 7}},
    }
    html = write_and_render(data)
    # The dangerous tokens must never appear as live HTML.
    assert "<script>" not in html
    assert "</script>" not in html
    # The literal substrings `onerror=` / `onload=` may appear as escaped *text*
    # (e.g. inside `&lt;img src=x onerror=alert(2)&gt;`) — that's safe because
    # the surrounding `<` got escaped to `&lt;`. What we forbid is a live HTML
    # tag carrying those attributes (e.g. `<img ... onerror=...>`).
    assert not re.search(r"<\w+[^>]*\bonerror\s*=", html)
    assert not re.search(r"<\w+[^>]*\bonload\s*=", html)
    # And escaped form must be present (proving _esc ran).
    assert "&lt;script&gt;" in html


def test_project_areas_list_shape(write_and_render):
    """LLM may emit project_areas as a list directly. Should not crash."""
    data = {
        "header": {"agent": "test"},
        "project_areas": [{"name": "X", "session_count": 5, "description": "d"}],
    }
    html = write_and_render(data)
    assert 'class="area-name"' in html
    assert "X" in html


def test_project_areas_dict_with_areas(write_and_render):
    data = {
        "header": {"agent": "test"},
        "project_areas": {"areas": [{"name": "Y", "session_count": 2, "description": "d"}]},
    }
    html = write_and_render(data)
    assert "Y" in html


def test_toc_only_lists_present_sections(write_and_render):
    """TOC should not link to sections that don't render."""
    html = write_and_render({
        "header": {"agent": "test"},
        "interaction_style": {"narrative": "p", "key_pattern": "k"},
    })
    # only "Interaction Style" should be in toc; project-areas anchor absent.
    assert 'href="#interaction"' in html
    assert 'href="#project-areas"' not in html


def test_empty_lists_dont_render_section(write_and_render):
    html = write_and_render({
        "header": {"agent": "test"},
        "project_areas": {"areas": []},
        "what_works": {"intro": "", "impressive_workflows": []},
    })
    assert 'id="project-areas"' not in html
    assert 'id="what-works"' not in html


def test_bar_chart_cycles_colors(write_and_render):
    html = write_and_render({
        "header": {"agent": "test"},
        "stats": {"tool_counts": {"a": 5, "b": 4, "c": 3}},
    })
    # Expect at least 2 distinct colour classes in the same chart.
    classes = set(re.findall(r'bar-fill (c\d)', html))
    assert len(classes) >= 2


def test_bar_chart_color_cycle_covers_top_n(write_and_render):
    # The cycle must have at least as many entries as the default top_n (=8),
    # otherwise the top of a busy chart shows two bars with the same colour
    # and the colour stops being a category cue.
    html = write_and_render({
        "header": {"agent": "test"},
        "stats": {"tool_counts": {f"tool_{i}": 10 - i for i in range(8)}},
    })
    classes = re.findall(r'bar-fill (c\d)', html)
    assert len(set(classes)) >= 8, classes


def test_print_color_adjust_in_css(write_and_render):
    html = write_and_render({"header": {"agent": "test", "title": "x"}})
    # Coloured cards must survive print / PDF export.
    assert "print-color-adjust" in html
    assert "-webkit-print-color-adjust" in html


def test_executive_summary_listed_in_toc(write_and_render):
    html = write_and_render({
        "header": {"agent": "test", "title": "x"},
        "executive_summary": {
            "headline": "Worked great",
            "one_sentence": "Shipped 3 things this week.",
        },
    })
    assert 'id="exec-summary"' in html
    assert 'href="#exec-summary"' in html


def test_executive_summary_anchor_absent_when_no_data(write_and_render):
    html = write_and_render({"header": {"agent": "test", "title": "x"}})
    # No exec-summary content → no anchor and no TOC entry for it.
    assert 'id="exec-summary"' not in html
    assert 'href="#exec-summary"' not in html


def test_at_a_glance_listed_in_toc(write_and_render):
    html = write_and_render({
        "header": {"agent": "test", "title": "x"},
        "at_a_glance": {"whats_working": "user ships fast"},
    })
    assert 'id="at-a-glance"' in html
    assert 'href="#at-a-glance"' in html


def test_at_a_glance_anchor_absent_when_no_data(write_and_render):
    html = write_and_render({"header": {"agent": "test", "title": "x"}})
    assert 'id="at-a-glance"' not in html
    assert 'href="#at-a-glance"' not in html


def test_html_lang_chinese_detected(write_and_render):
    data = {
        "header": {"title": "中文报告"},
        "at_a_glance": {"whats_working": "用户最近在搭跨 agent skill，效率不错。"},
        "interaction_style": {"narrative": "用户驱动节奏稳健，多用 subagent 校验。", "key_pattern": "高层指挥"},
    }
    html = write_and_render(data)
    assert '<html lang="zh">' in html


def test_html_lang_english_default(write_and_render):
    data = {
        "header": {"title": "English Report"},
        "at_a_glance": {"whats_working": "User ships fast across multiple agents."},
    }
    html = write_and_render(data)
    assert '<html lang="en">' in html


def test_html_lang_explicit_override(write_and_render):
    """header.lang takes precedence even if content suggests otherwise."""
    data = {
        "header": {"title": "中文标题", "lang": "ja"},
        "at_a_glance": {"whats_working": "全部都是中文内容"},
    }
    html = write_and_render(data)
    assert '<html lang="ja">' in html


def test_schema_drift_does_not_crash_renderer(write_and_render):
    data = {
        "header": {"agent": "test", "title": "Drift"},
        "project_areas": ["bad item", None, {"name": "Ok", "session_count": "2", "description": "kept"}],
        "what_works": {"impressive_workflows": ["bad", {"title": "Win", "description": "desc"}]},
        "friction_analysis": {"categories": [None, "bad", {"category": "c", "examples": "not-a-list"}]},
        "suggestions": {
            "claude_md_additions": ["bad", {"addition": "Do X", "why": "reason"}],
            "features_to_try": [None, {"feature": "Feature", "example_code": "x"}],
            "usage_patterns": ["bad", {"title": "Pattern", "copyable_prompt": "prompt"}],
        },
        "on_the_horizon": {"opportunities": ["bad", {"title": "Next", "whats_possible": "thing"}]},
        "stats": {"tool_counts": {"Bash": "5", "Bad": "NaN", "Negative": -1}},
    }
    html = write_and_render(data)
    assert "Ok" in html
    assert "Win" in html
    assert "Bash" in html


def test_html_contains_privacy_share_warning(write_and_render):
    html = write_and_render({"header": {"agent": "test", "title": "Report"}})
    assert "Review before sharing" in html
    assert "may include prompts, file paths, or tool output" in html


def test_stats_row_renders_schema_hours_field(write_and_render):
    html = write_and_render({"header": {"agent": "test", "title": "Report", "hours": 12.5}})
    assert "12.5" in html
    assert "Hours" in html


@pytest.mark.parametrize("n,expected", [
    (0, ""),
    (None, ""),
    (500, "500"),
    (999, "999"),
    (1000, "1k"),
    (1500, "1.5k"),
    (9499, "9.5k"),
    (9999, "10k"),
    (10000, "10k"),
    (15499, "15k"),
    # k/M boundary: promote only when round(n/1000) reaches 1000, so the label
    # never goes backwards across the threshold (949_999 and 950_000 both 950k).
    (949_999, "950k"),
    (950_000, "950k"),
    (999_499, "999k"),
    (999_999, "1.0M"),
    (1_000_000, "1.0M"),
    (1_500_000, "1.5M"),
    ("badvalue", "badvalue"),
])
def test_short_tokens_granularity(n, expected):
    assert _short_tokens(n) == expected


def test_scalar_schema_drift_does_not_crash_renderer(write_and_render):
    html = write_and_render({
        "header": {"agent": "test", "title": "Scalar Drift"},
        "interaction_style": {"narrative": 123, "key_pattern": True},
        "at_a_glance": "bad-shape",
    })
    assert "123" in html
    assert "True" in html


def test_guidance_file_additions_alias_and_opencode_heading(write_and_render):
    html = write_and_render({
        "header": {"agent": "opencode", "title": "OpenCode Report"},
        "suggestions": {"guidance_file_additions": [
            {"target_file": "AGENTS.md", "addition": "Use subagents for review", "why": "repeated reviews"}
        ]},
    })
    assert "Suggested AGENTS.md / OpenCode guidance additions" in html
    assert "Use subagents for review" in html
    assert "AGENTS.md" in html


def test_empty_schema_drift_does_not_render_empty_cards(write_and_render):
    html = write_and_render({
        "header": {"agent": "test"},
        "interaction_style": {"narrative": "", "key_pattern": ""},
        "suggestions": {"claude_md_additions": ["bad", None]},
    })
    assert 'id="interaction"' not in html
    assert "Suggested CLAUDE.md" not in html
