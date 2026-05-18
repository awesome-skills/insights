"""CLI orchestration regression tests."""
from __future__ import annotations

import argparse
import json
import os
from types import SimpleNamespace

import pytest

import insights
from common import ParsedSession, SessionMetadata


def test_head_ratio_cli_accepts_valid_float():
    parser = insights.build_parser()
    args = parser.parse_args(["transcript", "--session", "ses_1", "--head-ratio", "0.6"])
    assert args.head_ratio == pytest.approx(0.6)
    assert args.mode == "head_tail"  # default unchanged
    assert args.max_chars == 20000


def test_head_ratio_cli_default_is_three_tenths():
    parser = insights.build_parser()
    args = parser.parse_args(["transcript", "--session", "ses_1"])
    assert args.head_ratio == pytest.approx(0.3)


@pytest.mark.parametrize("bad_value", ["0", "1", "1.5", "-0.1", "abc"])
def test_head_ratio_cli_rejects_out_of_range_or_garbage(bad_value, capsys):
    parser = insights.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["transcript", "--session", "ses_1", "--head-ratio", bad_value])
    err = capsys.readouterr().err
    assert "--head-ratio" in err


def test_metadata_cache_without_version_is_reparsed(tmp_path, monkeypatch):
    calls = {"parse": 0}

    class FakeAdapter:
        @staticmethod
        def list_sessions(**_kwargs):
            return [{
                "session_id": "ses_1",
                "path": "opaque",
                "mtime": "2026-05-01T10:00:00+00:00",
            }]

        @staticmethod
        def parse_one(_ref, metadata_only=False):
            calls["parse"] += 1
            assert metadata_only is True
            return ParsedSession(
                metadata=SessionMetadata(
                    session_id="ses_1",
                    agent="claude-code",
                    user_message_count=3,
                ),
                messages=[],
            )

    monkeypatch.setattr(insights, "_load_adapter", lambda _agent: FakeAdapter)
    workdir = tmp_path / "work"
    meta_dir = workdir / "metadata"
    meta_dir.mkdir(parents=True)
    cached = meta_dir / "ses_1.json"
    cached.write_text(json.dumps({
        "session_id": "ses_1",
        "agent": "claude-code",
        "user_message_count": 1,
    }), encoding="utf-8")
    os.utime(cached, (4102444800, 4102444800))

    args = argparse.Namespace(
        agent="claude-code",
        workdir=str(workdir),
        root=None,
        session=None,
        days=None,
        limit=None,
        no_cache=False,
        min_messages=0,
        out=None,
    )

    assert insights.cmd_metadata(args) == 0
    assert calls["parse"] == 1
    data = json.loads(cached.read_text(encoding="utf-8"))
    assert data["user_message_count"] == 3
    assert data["_cache_version"] == insights.METADATA_CACHE_VERSION
