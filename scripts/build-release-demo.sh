#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
source="$root/samples/release-demo.md"
ledger="$root/samples/release-demo.notes.json"
view="${source%.md}-view.html"
merged="$(mktemp)"
trap 'rm -f "$merged"' EXIT

python3 "$root/build-view.py" "$source" >/dev/null
python3 "$root/merge-ledgers.py" "$ledger" --out "$merged" --view "$view" >/dev/null
printf '%s\n' "$view"
