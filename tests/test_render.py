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
