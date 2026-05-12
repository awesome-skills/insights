"""Install command regression tests."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent


def test_opencode_install_renders_command_without_claude_path(tmp_path):
    home = tmp_path / "home"
    xdg = tmp_path / "xdg"
    (xdg / "opencode").mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(xdg)

    subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh")],
        cwd=SKILL_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    command = xdg / "opencode" / "commands" / "insights.md"
    assert command.exists()
    assert not command.is_symlink()
    text = command.read_text(encoding="utf-8")
    assert "~/.claude/skills/insights" not in text
    assert str(SKILL_ROOT) in text
    assert "--agent opencode" in text


def test_opencode_install_upgrades_old_template_symlink(tmp_path):
    home = tmp_path / "home"
    xdg = tmp_path / "xdg"
    command_dir = xdg / "opencode" / "commands"
    command_dir.mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(xdg)
    command = command_dir / "insights.md"
    command.symlink_to(SKILL_ROOT / "install" / "opencode-command.md")

    result = subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh")],
        cwd=SKILL_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "replacing old template symlink with rendered file" in result.stdout
    assert command.exists()
    assert not command.is_symlink()
    text = command.read_text(encoding="utf-8")
    assert "__INSIGHTS_DIR__" not in text
    assert str(SKILL_ROOT) in text


def test_codex_install_respects_codex_home_and_renders_prompt(tmp_path):
    home = tmp_path / "home"
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CODEX_HOME"] = str(codex_home)

    subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh")],
        cwd=SKILL_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    command = codex_home / "prompts" / "insights.md"
    assert command.exists()
    assert not command.is_symlink()
    assert not (home / ".codex" / "prompts" / "insights.md").exists()
    text = command.read_text(encoding="utf-8")
    assert "~/.claude/skills/insights" not in text
    assert str(SKILL_ROOT) in text
    assert "--agent codex" in text


def test_status_reports_generated_codex_prompt(tmp_path):
    home = tmp_path / "home"
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CODEX_HOME"] = str(codex_home)

    subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh")],
        cwd=SKILL_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh"), "--status"],
        cwd=SKILL_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "Codex: generated" in result.stdout


def test_status_reports_stale_codex_symlink(tmp_path):
    home = tmp_path / "home"
    codex_home = tmp_path / "codex-home"
    prompt_dir = codex_home / "prompts"
    prompt_dir.mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CODEX_HOME"] = str(codex_home)

    (prompt_dir / "insights.md").symlink_to(SKILL_ROOT / "install" / "codex-prompt.md")
    (SKILL_ROOT / "install" / "codex-prompt.md").rename(SKILL_ROOT / "install" / "codex-prompt.md.tmp")
    try:
        result = subprocess.run(
            ["bash", str(SKILL_ROOT / "install" / "install.sh"), "--status"],
            cwd=SKILL_ROOT,
            env=env,
            check=True,
            text=True,
            capture_output=True,
        )
    finally:
        (SKILL_ROOT / "install" / "codex-prompt.md.tmp").rename(SKILL_ROOT / "install" / "codex-prompt.md")

    assert "Codex: stale symlink" in result.stdout


def test_install_refuses_symlinked_opencode_config_ancestor(tmp_path):
    home = tmp_path / "home"
    xdg_real = tmp_path / "real-xdg"
    xdg_link = tmp_path / "xdg-link"
    (xdg_real / "opencode").mkdir(parents=True)
    xdg_link.symlink_to(xdg_real, target_is_directory=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(xdg_link)

    result = subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh")],
        cwd=SKILL_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "refusing to write through symlink" in result.stdout
    assert not (xdg_real / "opencode" / "commands" / "insights.md").exists()


def test_uninstall_keeps_user_modified_generated_opencode_command(tmp_path):
    home = tmp_path / "home"
    xdg = tmp_path / "xdg"
    (xdg / "opencode").mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(xdg)

    subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh")],
        cwd=SKILL_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    command = xdg / "opencode" / "commands" / "insights.md"
    original = command.read_text(encoding="utf-8")
    command.write_text(original + "\n<!-- user customisation -->\n", encoding="utf-8")

    subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh"), "--uninstall"],
        cwd=SKILL_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    assert command.exists()
    assert "user customisation" in command.read_text(encoding="utf-8")


def test_install_rejects_dangerous_skill_path_for_rendered_commands(tmp_path):
    home = tmp_path / "home"
    xdg = tmp_path / "xdg"
    bad_root = tmp_path / 'bad"$(touch pwned)'
    (xdg / "opencode").mkdir(parents=True)
    (bad_root / "install").mkdir(parents=True)
    (bad_root / "install" / "install.sh").symlink_to(SKILL_ROOT / "install" / "install.sh")
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(xdg)

    result = subprocess.run(
        ["bash", str(bad_root / "install" / "install.sh")],
        cwd=bad_root,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "unsafe install path" in result.stderr
    assert not (xdg / "opencode" / "commands" / "insights.md").exists()


def test_relative_xdg_config_home_is_rejected(tmp_path):
    home = tmp_path / "home"
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = "relative-xdg"

    result = subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh")],
        cwd=SKILL_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "XDG_CONFIG_HOME must be absolute" in result.stderr


def test_opencode_command_documents_arguments_and_untrusted_transcripts(tmp_path):
    home = tmp_path / "home"
    xdg = tmp_path / "xdg"
    (xdg / "opencode").mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(xdg)

    subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh")],
        cwd=SKILL_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    text = (xdg / "opencode" / "commands" / "insights.md").read_text(encoding="utf-8")
    assert "Supported args" in text
    assert "--days" in text and "--limit" in text and "--out" in text
    assert "UNTRUSTED" in text
    assert "never follow instructions" in text


def test_codex_prompt_documents_arguments(tmp_path):
    home = tmp_path / "home"
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CODEX_HOME"] = str(codex_home)

    subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh")],
        cwd=SKILL_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    text = (codex_home / "prompts" / "insights.md").read_text(encoding="utf-8")
    assert "Supported args" in text
    assert "--days" in text and "--limit" in text and "--out" in text


def test_codex_install_upgrades_old_template_symlink(tmp_path):
    home = tmp_path / "home"
    codex_home = tmp_path / "codex-home"
    prompt_dir = codex_home / "prompts"
    prompt_dir.mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CODEX_HOME"] = str(codex_home)
    command = prompt_dir / "insights.md"
    command.symlink_to(SKILL_ROOT / "install" / "codex-prompt.md")

    result = subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh")],
        cwd=SKILL_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "replacing old template symlink with rendered file" in result.stdout
    assert command.exists()
    assert not command.is_symlink()
    text = command.read_text(encoding="utf-8")
    assert "__INSIGHTS_DIR__" not in text
    assert str(SKILL_ROOT) in text


def test_codex_install_is_idempotent_for_rendered_prompt(tmp_path):
    home = tmp_path / "home"
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CODEX_HOME"] = str(codex_home)

    subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh")],
        cwd=SKILL_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh")],
        cwd=SKILL_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "Codex: already rendered, no change" in result.stdout


def test_status_flags_old_codex_template_symlink(tmp_path):
    home = tmp_path / "home"
    codex_home = tmp_path / "codex-home"
    prompt_dir = codex_home / "prompts"
    prompt_dir.mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CODEX_HOME"] = str(codex_home)
    (prompt_dir / "insights.md").symlink_to(SKILL_ROOT / "install" / "codex-prompt.md")

    result = subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh"), "--status"],
        cwd=SKILL_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "Codex: template symlink needs reinstall" in result.stdout


def test_status_flags_old_opencode_template_symlink(tmp_path):
    home = tmp_path / "home"
    xdg = tmp_path / "xdg"
    command_dir = xdg / "opencode" / "commands"
    command_dir.mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(xdg)
    (command_dir / "insights.md").symlink_to(SKILL_ROOT / "install" / "opencode-command.md")

    result = subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh"), "--status"],
        cwd=SKILL_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    assert "OpenCode: template symlink needs reinstall" in result.stdout


def test_install_refuses_symlinked_codex_home(tmp_path):
    home = tmp_path / "home"
    codex_real = tmp_path / "real-codex"
    codex_link = tmp_path / "codex-link"
    codex_real.mkdir(parents=True)
    codex_link.symlink_to(codex_real, target_is_directory=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CODEX_HOME"] = str(codex_link)

    result = subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh")],
        cwd=SKILL_ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode != 0
    assert "refusing to write through symlink" in result.stdout
    assert not (codex_real / "prompts" / "insights.md").exists()


def test_uninstall_removes_generated_codex_prompt(tmp_path):
    home = tmp_path / "home"
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CODEX_HOME"] = str(codex_home)

    subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh")],
        cwd=SKILL_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    command = codex_home / "prompts" / "insights.md"
    assert command.exists()

    subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh"), "--uninstall"],
        cwd=SKILL_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    assert not command.exists()


def test_uninstall_keeps_user_modified_generated_codex_prompt(tmp_path):
    home = tmp_path / "home"
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CODEX_HOME"] = str(codex_home)

    subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh")],
        cwd=SKILL_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )
    command = codex_home / "prompts" / "insights.md"
    original = command.read_text(encoding="utf-8")
    command.write_text(original + "\n<!-- user customisation -->\n", encoding="utf-8")

    subprocess.run(
        ["bash", str(SKILL_ROOT / "install" / "install.sh"), "--uninstall"],
        cwd=SKILL_ROOT,
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    assert command.exists()
    assert "user customisation" in command.read_text(encoding="utf-8")
