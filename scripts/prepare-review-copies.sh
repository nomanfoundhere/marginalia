#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  printf 'usage: %s <doc-view.html> <reviewer> [reviewer ...]\n' "$0" >&2
  exit 2
fi

view="$1"
shift
if [[ ! -f "$view" ]]; then
  printf 'view not found: %s\n' "$view" >&2
  exit 2
fi

directory="$(cd "$(dirname "$view")" && pwd)"
name="$(basename "$view")"
stem="${name%-view.html}"
if [[ "$stem" == "$name" ]]; then
  printf 'view must end in -view.html: %s\n' "$view" >&2
  exit 2
fi

for reviewer in "$@"; do
  slug="$(printf '%s' "$reviewer" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-')"
  slug="${slug#-}"
  slug="${slug%-}"
  if [[ -z "$slug" ]]; then
    printf 'reviewer name has no usable filename characters: %s\n' "$reviewer" >&2
    exit 2
  fi
  output="$directory/$stem-$slug-view.html"
  if [[ -e "$output" ]]; then
    printf 'refusing to replace existing review copy: %s\n' "$output" >&2
    exit 1
  fi
  cp "$view" "$output"
  printf '%s\n' "$output"
done
