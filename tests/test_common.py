"""Tests for shared utilities. These guard the most regression-prone code:
system-injection filter (corrupts headline metrics if wrong) and Bash path
extraction (affects language histogram accuracy).
"""
import common


# ------------- is_system_injection -------------

class TestSystemInjection:
    def test_developer_and_system_roles_always_filtered(self):
        assert common.is_system_injection("developer", "anything")
        assert common.is_system_injection("system", "anything")

    def test_codex_xml_wrappers_filtered(self):
        assert common.is_system_injection("user", "<environment_context>cwd</environment_context>")
        assert common.is_system_injection("user", "<user_instructions>foo")
        assert common.is_system_injection("user", "<permissions_instructions>foo")
        assert common.is_system_injection("user", "<subagent_notification>x")

    def test_claude_code_slash_command_wrappers_filtered(self):
        assert common.is_system_injection("user", "<command-name>/foo</command-name>")
        assert common.is_system_injection("user", "<command-message>foo</command-message>")
        assert common.is_system_injection("user", "<system-reminder>SessionStart</system-reminder>")
        assert common.is_system_injection("user", "<local-command-stdout>...</local-command-stdout>")

    def test_slash_command_body_template_filtered(self):
        assert common.is_system_injection("user", "The user just ran /insights to generate a usage report")
        assert common.is_system_injection("user", "The user ran the /foo command")

    def test_agents_md_prefix_filtered(self):
        assert common.is_system_injection("user", "# AGENTS.md instructions for /home/dev/foo")

    def test_leading_whitespace_does_not_evade_filter(self):
        assert common.is_system_injection("user", "\n  <environment_context>x")
        assert common.is_system_injection("user", "   <command-name>x")

    def test_legit_user_text_not_filtered(self):
        # The regression we're guarding: prior version filtered any "<system" prefix.
        assert not common.is_system_injection("user", "<system> please refactor my code")
        assert not common.is_system_injection("user", "<skill> test")
        assert not common.is_system_injection("user", "Use <system> tag in your code")
        assert not common.is_system_injection("user", "I want a <command-name> design pattern")
        assert not common.is_system_injection("user", "normal user message")
        assert not common.is_system_injection("user", "")

    def test_empty_or_none_text(self):
        assert not common.is_system_injection("user", "")
        assert not common.is_system_injection("user", None)  # type: ignore[arg-type]


# ------------- extract_tool_input -------------

class TestExtractToolInput:
    def test_command_field(self):
        cmd, fp = common.extract_tool_input({"command": "ls -la"})
        assert cmd == "ls -la"
        assert fp == ""

    def test_file_path_snake_case(self):
        cmd, fp = common.extract_tool_input({"file_path": "/tmp/foo.py"})
        assert cmd == "/tmp/foo.py"
        assert fp == "/tmp/foo.py"

    def test_file_path_camel_case_opencode(self):
        cmd, fp = common.extract_tool_input({"filePath": "/tmp/foo.ts"})
        assert cmd == "/tmp/foo.ts"
        assert fp == "/tmp/foo.ts"

    def test_path_fallback(self):
        cmd, fp = common.extract_tool_input({"path": "/tmp/bar"})
        assert cmd == "/tmp/bar"
        assert fp == "/tmp/bar"

    def test_list_command_joined(self):
        cmd, fp = common.extract_tool_input({"command": ["python3", "foo.py"]})
        assert cmd == "python3 foo.py"

    def test_non_dict_returns_empty(self):
        assert common.extract_tool_input(None) == ("", "")
        assert common.extract_tool_input("string") == ("", "")
        assert common.extract_tool_input([1, 2]) == ("", "")

    def test_empty_dict(self):
        assert common.extract_tool_input({}) == ("", "")


# ------------- extract_bash_paths -------------

class TestExtractBashPaths:
    def test_python_script(self):
        assert common.extract_bash_paths("python3 foo.py") == ["foo.py"]

    def test_absolute_path(self):
        assert common.extract_bash_paths("python3 /home/dev/main.py --flag") == ["/home/dev/main.py"]

    def test_multiple_files(self):
        result = common.extract_bash_paths("cat README.md src/main.rs")
        assert "README.md" in result
        assert "src/main.rs" in result

    def test_no_extension_returns_empty(self):
        assert common.extract_bash_paths("echo hello") == []
        assert common.extract_bash_paths("curl https://example.com") == []

    def test_glob_pattern_not_a_path(self):
        # `*.py` inside a find -name argument shouldn't be a captured path.
        result = common.extract_bash_paths('find . -name "*.py" -exec rm {} \\;')
        assert result == []

    def test_limit_caps_output(self):
        many = " ".join(f"file{i}.py" for i in range(20))
        result = common.extract_bash_paths(many, limit=5)
        assert len(result) == 5


# ------------- extract_patch_paths -------------

class TestExtractPatchPaths:
    def test_apply_patch_headers(self):
        patch = """*** Begin Patch
*** Add File: src/new_feature.py
+print("ok")
*** Update File: README.md
*** Move to: docs/README.md
@@
-old
+new
*** Delete File: obsolete.txt
*** End Patch
"""
        assert common.extract_patch_paths(patch) == [
            "src/new_feature.py",
            "README.md",
            "docs/README.md",
            "obsolete.txt",
        ]


# ------------- count_git_actions -------------

class TestGitActions:
    def test_commit_counted(self):
        c, p = common.count_git_actions("git commit -m 'foo'")
        assert c == 1
        assert p == 0

    def test_push_counted(self):
        c, p = common.count_git_actions("git push origin main")
        assert (c, p) == (0, 1)

    def test_chained_commands(self):
        c, p = common.count_git_actions("git add . && git commit -m x && git push")
        assert (c, p) == (1, 1)

    def test_no_git_command(self):
        assert common.count_git_actions("echo nothing") == (0, 0)
        assert common.count_git_actions("") == (0, 0)


# ------------- safe_session_id -------------

class TestSafeSessionId:
    def test_normal_id_passthrough(self):
        assert common.safe_session_id("abc-123_xyz.456") == "abc-123_xyz.456"

    def test_path_traversal_neutralized(self):
        sid = common.safe_session_id("../../etc/passwd")
        assert "/" not in sid
        assert ".." not in sid

    def test_absolute_path_neutralized(self):
        sid = common.safe_session_id("/etc/passwd")
        assert "/" not in sid

    def test_pure_dots_falls_back(self):
        # None has no identity to preserve → collapses to the bare fallback.
        assert common.safe_session_id(None) == "unknown"  # type: ignore[arg-type]
        # "" / "." / ".." each carry distinct identity and must not collide,
        # so they get a digest suffix rather than the literal "unknown".
        for raw in ("", ".", ".."):
            sid = common.safe_session_id(raw)
            assert sid.startswith("unknown-"), sid
            assert ".." not in sid
            assert "/" not in sid

    def test_excessive_length_capped(self):
        sid = common.safe_session_id("a" * 1000)
        assert len(sid) <= 128

    def test_unicode_replaced(self):
        # CJK characters aren't filename-safe across all platforms; replace.
        sid = common.safe_session_id("会话/01")
        assert "/" not in sid
        assert sid != ""

    def test_sanitized_ids_do_not_collide_with_safe_ids(self):
        assert common.safe_session_id("a/b") != common.safe_session_id("a_b")
        assert common.safe_session_id("/a_b") != common.safe_session_id("a/b")

    def test_truncated_ids_keep_collision_resistant_suffix(self):
        sid1 = common.safe_session_id("a" * 200 + "1")
        sid2 = common.safe_session_id("a" * 200 + "2")
        assert sid1 != sid2
        assert len(sid1) <= 128
        assert len(sid2) <= 128

    def test_cleaned_empty_ids_do_not_collide_with_fallback(self):
        assert common.safe_session_id("///") != common.safe_session_id("unknown")
        assert common.safe_session_id("///") != common.safe_session_id("\\\\\\")

    def test_special_dot_inputs_do_not_collide(self):
        # "" / "." / ".." used to all return the literal "unknown" sans digest,
        # causing two malformed upstream sessions to overwrite each other's
        # metadata cache file. Each must now resolve to a distinct id.
        empty = common.safe_session_id("")
        dot = common.safe_session_id(".")
        dotdot = common.safe_session_id("..")
        assert empty != dot
        assert dot != dotdot
        assert empty != dotdot
        # None still collapses to bare fallback (no identity to preserve).
        assert common.safe_session_id(None) == "unknown"  # type: ignore[arg-type]
        # And distinct from any of the digest-suffixed variants.
        assert common.safe_session_id(None) != empty  # type: ignore[arg-type]


# ------------- parse_iso -------------

class TestParseIso:
    def test_none_returns_none(self):
        assert common.parse_iso(None) is None

    def test_bool_rejected(self):
        # bool is a subclass of int; True must not parse to a 1970 timestamp.
        assert common.parse_iso(True) is None
        assert common.parse_iso(False) is None

    def test_nan_inf_rejected(self):
        assert common.parse_iso(float("nan")) is None
        assert common.parse_iso(float("inf")) is None
        assert common.parse_iso(float("-inf")) is None

    def test_iso_string_parses(self):
        dt = common.parse_iso("2024-01-15T12:34:56Z")
        assert dt is not None
        assert dt.year == 2024 and dt.month == 1 and dt.day == 15

    def test_invalid_string_returns_none(self):
        assert common.parse_iso("not-a-date") is None

    def test_epoch_seconds(self):
        dt = common.parse_iso(1_700_000_000)  # 2023-11-14
        assert dt is not None
        assert dt.year == 2023

    def test_epoch_millis(self):
        dt = common.parse_iso(1_700_000_000_000)
        assert dt is not None
        assert dt.year == 2023

    def test_overflow_returns_none(self):
        # Extremely large values that pass the > 1e12 ms branch but still overflow.
        assert common.parse_iso(1e30) is None
