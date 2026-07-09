# Margin Notes

Zero-server, single-file Markdown annotation. Bake a `.md` into a self-contained
`-view.html`, highlight spans and leave margin notes in any Chromium browser
(verified in Helium), save in place, and pull the feedback back as a digest.

The viewer ships two themes (it follows your OS preference and remembers a
manual toggle), aligns each note card to its highlight in the margin, and
fetches nothing at runtime — system fonts only, no network, fully offline.

Each note opens as a draft with an explicit Post button, then becomes a thread:
reviewers reply, resolve, delete, or edit their own messages. A reviewer sets a
name once through an inline chip (no browser prompt), and a colored monogram then
marks every message they leave. A note whose quoted text no longer matches the
document stays visible as unanchored, retaining its original quote instead of
vanishing; select its replacement span and reattach it.

Selecting text offers Critical, Important, Refinement, and Strike. Critical,
Important, and Refinement create a priority note and apply its matching red,
amber, or blue highlight. Strike is a standalone deletion instruction. There are
no wordless highlights: every coloured span has review intent. The margin filters
All, Critical, Important, Refinements, and Deletions; one note expands into a
replyable discussion while the rest remain compact, source-aligned rows. Keys
`1`, `2`, `3`, and `X` create Critical, Important, Refinement, and Strike from a
live selection.

The collect step groups feedback by priority and deletion, prints each item with
its source line address, states whether the `.md` has moved since the review, and
writes a git-friendly `<doc>.notes.json` sidecar. `--packet` emits the same review
as compact structured operations for an AI that can read the source file. Separate
reviewers can merge matching sidecars with `merge-ledgers.py`, then apply the
merged ledger back into the matching view.

<!-- SCREENSHOT: light theme — docs/screenshots/light.png (capture in a browser) -->
<!-- SCREENSHOT: dark theme  — docs/screenshots/dark.png  (capture in a browser) -->
<!-- DEMO: short gif/mp4 of select → note → save → collect round-trip -->
> _Screenshots and demo are captured in a browser and added before release._

## Browser support
Saving in place uses the [File System Access API][fsa], so the file overwrites
itself with no re-download:

- **Chromium (Chrome, Edge, Helium, Brave, …):** full in-place save. Arm it
  once by dragging the file onto its own window (or picking it once — the
  bar shows the exact path); after that it is a single click.
- **Firefox / Safari:** the API is unavailable, so Save falls back to a normal
  download of the updated `-view.html`, which you keep in place of the original.

Autosave to local storage, the unsaved-changes guard, and ⌘S work everywhere.

[fsa]: https://developer.mozilla.org/en-US/docs/Web/API/File_System_API

## Install the skills
Symlink the three skills into your Claude Code skills directory:

    ln -s "$PWD/skills/margin-send"    ~/.claude/skills/margin-send
    ln -s "$PWD/skills/margin-collect" ~/.claude/skills/margin-collect
    ln -s "$PWD/skills/margin-merge"   ~/.claude/skills/margin-merge

## Round-trip
1. `/margin-send plan.md` — builds `plan-view.html`, opens it in Helium.
2. Reviewer selects text → Critical, Important, Refinement, or Strike → Post
   comment → Save. Passes the one file on; it accumulates each reviewer's notes.
3. `/margin-collect plan-view.html` — distills unresolved notes; use
   `python3 distill.py --packet plan-view.html` when the receiving AI can read
   `plan.md` directly, then regenerate after revision.
4. `/margin-merge reviewer-a.notes.json reviewer-b.notes.json --view plan-view.html`
   merges parallel reviews against the same source snapshot.

## Tests
    node --test tests/*.mjs     # JS: anchoring, reconstruction, vendor
    python3 -m pytest tests/    # Python: build-view, distill
