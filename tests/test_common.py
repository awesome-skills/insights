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
