# Margin Notes

Zero-server, single-file Markdown annotation. Bake a `.md` into a self-contained
`-view.html`, highlight spans and leave margin notes in any Chromium browser
(verified in Helium), save in place, and pull the feedback back as a digest.

## Install the skills
Symlink the two skills into your Claude Code skills directory:

    ln -s "$PWD/skills/margin-send"    ~/.claude/skills/margin-send
    ln -s "$PWD/skills/margin-collect" ~/.claude/skills/margin-collect

## Round-trip
1. `/margin-send plan.md` — builds `plan-view.html`, opens it in Helium.
2. Reviewer selects text → "+ note" → types → Save. Passes the one file on; it
   accumulates each reviewer's notes.
3. `/margin-collect plan-view.html` — distills unresolved notes; the author
   revises `plan.md` and regenerates.

## Tests
    node --test tests/*.mjs     # JS: anchoring, reconstruction, vendor
    python3 -m pytest tests/    # Python: build-view, distill
