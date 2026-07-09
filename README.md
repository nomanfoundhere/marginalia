# Margin Notes

Zero-server, single-file Markdown annotation. Bake a `.md` into a self-contained
`-view.html`, highlight spans and leave margin notes in any Chromium browser
(verified in Helium), save in place, and pull the feedback back as a digest.

The viewer ships two themes (it follows your OS preference and remembers a
manual toggle), aligns each note card to its highlight in the margin, and
fetches nothing at runtime — system fonts only, no network, fully offline.

Each comment opens as a draft with an explicit Post button, then becomes a
thread: reviewers reply, resolve, delete, or edit their own messages. A reviewer
sets a name once through an inline chip (no browser prompt), and a colored
monogram then marks every message they leave. A note whose quoted text no longer
matches the document shows as unanchored, keeping its quote, instead of
vanishing.

Selecting text raises a small toolbar: yellow Question, green Looks good, pink
Needs work, underline, strikethrough, and Comment. Clicking an existing mark
opens mark controls in the document, so a reviewer can comment on the marked span
without making a duplicate note. Bare marks travel to the author as wordless
flags on their exact span; comments carry threads. The collect step groups
feedback by meaning, prints each item with its source line address, states
whether the `.md` has moved since the review, and writes a git-friendly
`<doc>.notes.json` sidecar so the conversation survives the view file.

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
Symlink the two skills into your Claude Code skills directory:

    ln -s "$PWD/skills/margin-send"    ~/.claude/skills/margin-send
    ln -s "$PWD/skills/margin-collect" ~/.claude/skills/margin-collect

## Round-trip
1. `/margin-send plan.md` — builds `plan-view.html`, opens it in Helium.
2. Reviewer selects text → "Comment" → types → Post comment → Save. Passes the one file on; it
   accumulates each reviewer's notes.
3. `/margin-collect plan-view.html` — distills unresolved notes; the author
   revises `plan.md` and regenerates.

## Tests
    node --test tests/*.mjs     # JS: anchoring, reconstruction, vendor
    python3 -m pytest tests/    # Python: build-view, distill
