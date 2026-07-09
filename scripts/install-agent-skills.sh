#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
install_claude=true
install_codex=true

case "${1:---all}" in
  --all) ;;
  --claude) install_codex=false ;;
  --codex) install_claude=false ;;
  *)
    printf 'usage: %s [--all|--claude|--codex]\n' "$0" >&2
    exit 2
    ;;
esac

link_skill() {
  local target="$1"
  local source="$2"

  mkdir -p "$(dirname "$target")"
  if [[ -L "$target" ]]; then
    if [[ "$(readlink "$target")" == "$source" ]]; then
      printf 'already linked: %s\n' "$target"
      return
    fi
    printf 'refusing to replace existing link: %s\n' "$target" >&2
    exit 1
  fi
  if [[ -e "$target" ]]; then
    printf 'refusing to replace existing path: %s\n' "$target" >&2
    exit 1
  fi
  ln -s "$source" "$target"
  printf 'linked: %s\n' "$target"
}

if $install_claude; then
  link_skill "$HOME/.claude/skills/marginalia" "$root"
fi

if $install_codex; then
  for skill in margin-send margin-collect margin-merge; do
    link_skill "$HOME/.codex/skills/$skill" "$root/skills/$skill"
  done
fi
