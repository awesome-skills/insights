#!/usr/bin/env bash
# Install / uninstall the /insights command into each detected agent.
#
# Usage:
#   install.sh              # install (skip if already present)
#   install.sh --force      # install, overwriting any existing file/link
#   install.sh --uninstall  # remove the symlinks
#   install.sh --dry-run    # print actions without doing them
#   install.sh --status     # show what's currently installed
#
# Combine with --dry-run, e.g. `install.sh --uninstall --dry-run`.
set -e

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INSTALL_DIR="$SKILL_DIR/install"
OPENCODE_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}/opencode"
CODEX_CONFIG_HOME="${CODEX_HOME:-${OPENAI_CODEX_HOME:-$HOME/.codex}}"

case "$SKILL_DIR" in
  *[\`\"\$]*)
    echo "unsafe install path: $SKILL_DIR" >&2
    exit 1
    ;;
esac

if [[ -n "${XDG_CONFIG_HOME:-}" && "$XDG_CONFIG_HOME" != /* ]]; then
  echo "XDG_CONFIG_HOME must be absolute" >&2
  exit 1
fi
if [[ -n "${CODEX_HOME:-}" && "$CODEX_HOME" != /* ]]; then
  echo "CODEX_HOME must be absolute" >&2
  exit 1
fi
if [[ -n "${OPENAI_CODEX_HOME:-}" && "$OPENAI_CODEX_HOME" != /* ]]; then
  echo "OPENAI_CODEX_HOME must be absolute" >&2
  exit 1
fi

MODE="install"
FORCE=0
DRY=0
FAILED=0
for arg in "$@"; do
  case "$arg" in
    --uninstall) MODE="uninstall" ;;
    --status)    MODE="status" ;;
    --force)     FORCE=1 ;;
    --dry-run)   DRY=1 ;;
    -h|--help)
      sed -n '2,11p' "$0"
      exit 0
      ;;
    *)
      echo "unknown arg: $arg" >&2
      exit 2
      ;;
  esac
done

green()  { printf "\033[32m%s\033[0m\n" "$1"; }
yellow() { printf "\033[33m%s\033[0m\n" "$1"; }
red()    { printf "\033[31m%s\033[0m\n" "$1"; }
gray()   { printf "\033[90m%s\033[0m\n" "$1"; }

# Targets: <human-name>|<source-relative-to-INSTALL_DIR>|<destination-absolute>
TARGETS=(
  "Claude Code|skill|$HOME/.claude/skills/insights"
  "Gemini CLI|gemini-command.toml|$HOME/.gemini/commands/insights.toml"
  "OpenCode|opencode-command.md|$OPENCODE_CONFIG_HOME/commands/insights.md"
  "Codex|codex-prompt.md|$CODEX_CONFIG_HOME/prompts/insights.md"
)

run() {
  if [[ $DRY == 1 ]]; then
    gray "  [dry-run] $*"
  else
    "$@"
  fi
}

render_template() {
  local src="$1" dst="$2"
  if [[ $DRY == 1 ]]; then
    gray "  [dry-run] render $src → $dst"
  else
    python3 - "$src" "$dst" "$SKILL_DIR" <<'PY'
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
skill_dir = sys.argv[3]
text = src.read_text(encoding="utf-8").replace("__INSIGHTS_DIR__", skill_dir)
dst.write_text(text, encoding="utf-8")
PY
  fi
}

generated_matches_template() {
  local src="$1" dst="$2"
  python3 - "$src" "$dst" "$SKILL_DIR" <<'PY'
import sys
from pathlib import Path

src = Path(sys.argv[1])
dst = Path(sys.argv[2])
skill_dir = sys.argv[3]
expected = src.read_text(encoding="utf-8").replace("__INSIGHTS_DIR__", skill_dir)
current = dst.read_text(encoding="utf-8")
raise SystemExit(0 if current == expected else 1)
PY
}

is_rendered_agent() {
  [[ "$1" == "OpenCode" || "$1" == "Codex" ]]
}

has_symlink_ancestor() {
  local path="$1"
  while [[ "$path" != "/" && "$path" != "." ]]; do
    if [[ -L "$path" ]]; then
      return 0
    fi
    path="$(dirname "$path")"
  done
  return 1
}

agent_dir_present() {
  case "$1" in
    "Claude Code") [[ -d "$HOME/.claude" ]] ;;
    "Gemini CLI")  [[ -d "$HOME/.gemini" ]] ;;
    "OpenCode")    [[ -d "$OPENCODE_CONFIG_HOME" || -d "$HOME/.local/share/opencode" ]] ;;
    "Codex")       [[ -d "$CODEX_CONFIG_HOME" ]] ;;
  esac
}

resolve_src() {
  local src="$1"
  if [[ "$src" == "skill" ]]; then
    echo "$SKILL_DIR"
  else
    echo "$INSTALL_DIR/$src"
  fi
}

install_one() {
  local name="$1" src_rel="$2" dst="$3"
  if ! agent_dir_present "$name"; then
    gray "$name: not detected, skipping"
    return
  fi
  local src; src="$(resolve_src "$src_rel")"

  # Claude Code: skip symlink if SKILL_DIR is already inside ~/.claude/skills/.
  if [[ "$name" == "Claude Code" && "$SKILL_DIR" == "$HOME/.claude/skills/"* ]]; then
    green "$name: already discoverable at $SKILL_DIR"
    return
  fi

  # Refuse to write through symlinked parent dirs — protects against attacks
  # where `~/.gemini/commands` (etc.) is replaced with a link to /etc/.
  local parent; parent="$(dirname "$dst")"
  if has_symlink_ancestor "$parent"; then
    red "$name: parent path $parent has symlink ancestor — refusing to write through symlink"
    FAILED=1
    return
  fi

  if [[ -e "$dst" || -L "$dst" ]]; then
    if is_rendered_agent "$name"; then
      if [[ -L "$dst" && "$(readlink "$dst" 2>/dev/null)" == "$src" ]]; then
        gray "$name: replacing old template symlink with rendered file"
        run rm -f "$dst"
      elif [[ ! -L "$dst" ]] && generated_matches_template "$src" "$dst"; then
        gray "$name: already rendered, no change"
        return
      elif [[ $FORCE == 0 ]]; then
        yellow "$name: $dst already exists (use --force to overwrite)"
        return
      else
        run rm -f "$dst"
      fi
    elif [[ -L "$dst" && "$(readlink "$dst" 2>/dev/null)" == "$src" ]]; then
      gray "$name: already linked, no change"
      return
    elif [[ $FORCE == 0 ]]; then
      yellow "$name: $dst already exists (use --force to overwrite)"
      return
    else
      run rm -f "$dst"
    fi
  fi
  run mkdir -p "$parent"
  if is_rendered_agent "$name"; then
    render_template "$src" "$dst"
    green "$name: rendered $dst → $src"
  else
    run ln -s "$src" "$dst"
    green "$name: linked $dst → $src"
  fi
}

uninstall_one() {
  local name="$1" src_rel="$2" dst="$3"
  local src; src="$(resolve_src "$src_rel")"
  if [[ ! -e "$dst" && ! -L "$dst" ]]; then
    gray "$name: nothing installed at $dst"
    return
  fi
  if [[ -L "$dst" ]]; then
    local target; target="$(readlink "$dst" 2>/dev/null || true)"
    if [[ "$target" != "$INSTALL_DIR/"* && "$target" != "$SKILL_DIR"* ]]; then
      yellow "$name: $dst is a symlink but points outside our install dir ($target). Skipping."
      FAILED=1
      return
    fi
    run rm "$dst"
    green "$name: removed $dst"
  elif is_rendered_agent "$name" && generated_matches_template "$src" "$dst"; then
    run rm "$dst"
    green "$name: removed generated command $dst"
  else
    yellow "$name: $dst is a regular file (not our symlink). Skipping for safety."
  fi
}

status_one() {
  local name="$1" src_rel="$2" dst="$3"
  local src; src="$(resolve_src "$src_rel")"
  if [[ -L "$dst" ]]; then
    local target; target="$(readlink "$dst")"
    if is_rendered_agent "$name" && [[ "$target" == "$src" && -e "$dst" ]]; then
      yellow "$name: template symlink needs reinstall → $target"
    elif [[ "$target" == "$src" && -e "$dst" ]]; then
      green "$name: linked → $target"
    elif [[ "$target" == "$src" ]]; then
      red "$name: stale symlink → $target"
    else
      yellow "$name: linked outside expected source → $target"
    fi
  elif [[ -e "$dst" ]]; then
    if is_rendered_agent "$name" && generated_matches_template "$src" "$dst"; then
      green "$name: generated → $dst"
    else
      yellow "$name: $dst exists but is not managed by this install"
    fi
  else
    gray "$name: not installed"
  fi
}

FLAGS=""
[[ $FORCE == 1 ]] && FLAGS+=" (force)"
[[ $DRY == 1 ]] && FLAGS+=" (dry-run)"
echo "Skill source: $SKILL_DIR"
echo "Mode: $MODE$FLAGS"
echo ""

for spec in "${TARGETS[@]}"; do
  IFS='|' read -r name src dst <<< "$spec"
  case "$MODE" in
    install)   install_one "$name" "$src" "$dst" ;;
    uninstall) uninstall_one "$name" "$src" "$dst" ;;
    status)    status_one "$name" "$src" "$dst" ;;
  esac
done

echo ""
case "$MODE" in
  install)   green "Done. Try /insights in any installed agent." ;;
  uninstall) green "Uninstalled." ;;
  status)    green "Status report complete." ;;
esac
exit "$FAILED"
