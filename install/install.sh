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

MODE="install"
FORCE=0
DRY=0
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
  "OpenCode|opencode-command.md|$HOME/.config/opencode/commands/insights.md"
  "Codex|codex-prompt.md|$HOME/.codex/prompts/insights.md"
)

run() {
  if [[ $DRY == 1 ]]; then
    gray "  [dry-run] $*"
  else
    "$@"
  fi
}

agent_dir_present() {
  case "$1" in
    "Claude Code") [[ -d "$HOME/.claude" ]] ;;
    "Gemini CLI")  [[ -d "$HOME/.gemini" ]] ;;
    "OpenCode")    [[ -d "$HOME/.config/opencode" || -d "$HOME/.local/share/opencode" ]] ;;
    "Codex")       [[ -d "$HOME/.codex" ]] ;;
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
  if [[ -L "$parent" ]]; then
    red "$name: parent dir $parent is a symlink — refusing to write through it"
    return
  fi

  if [[ -e "$dst" || -L "$dst" ]]; then
    if [[ -L "$dst" && "$(readlink "$dst" 2>/dev/null)" == "$src" ]]; then
      gray "$name: already linked, no change"
      return
    fi
    if [[ $FORCE == 0 ]]; then
      yellow "$name: $dst already exists (use --force to overwrite)"
      return
    fi
    run rm -f "$dst"
  fi
  run mkdir -p "$parent"
  run ln -s "$src" "$dst"
  green "$name: linked $dst → $src"
}

uninstall_one() {
  local name="$1" src_rel="$2" dst="$3"
  if [[ ! -e "$dst" && ! -L "$dst" ]]; then
    gray "$name: nothing installed at $dst"
    return
  fi
  if [[ -L "$dst" ]]; then
    local target; target="$(readlink "$dst" 2>/dev/null || true)"
    if [[ "$target" != "$INSTALL_DIR/"* && "$target" != "$SKILL_DIR"* ]]; then
      yellow "$name: $dst is a symlink but points outside our install dir ($target). Skipping."
      return
    fi
    run rm "$dst"
    green "$name: removed $dst"
  else
    yellow "$name: $dst is a regular file (not our symlink). Skipping for safety."
  fi
}

status_one() {
  local name="$1" src_rel="$2" dst="$3"
  if [[ -L "$dst" ]]; then
    local target; target="$(readlink "$dst")"
    green "$name: linked → $target"
  elif [[ -e "$dst" ]]; then
    yellow "$name: $dst exists but is not our symlink"
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
