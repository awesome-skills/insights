"""CLI orchestration regression tests."""
from __future__ import annotations

import argparse
import json
import os
from types import SimpleNamespace

import insights
from common import ParsedSession, SessionMetadata


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
        def parse_session(_path, metadata_only=False):
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
