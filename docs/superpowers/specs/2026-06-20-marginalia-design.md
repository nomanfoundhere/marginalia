# Margin Notes — design spec

Date: 2026-06-20
Status: approved for planning
Name: Margin Notes (flavor alias: Marginalia). Both resolve to the `margin-`
skill prefix, so the display name can change without touching the commands.

## Problem

Two-way review of plans and writeups needs a way to leave precise, span-level
feedback on Markdown without leaving Markdown, and without the failure modes of
the previous attempt (Roughdraft): a cramped side panel, an ugly surface, and a
live socket whose keepalive clock timed out mid-review. The replacement must let
a reviewer read a document at leisure, highlight exact words, attach notes, pass
the result to other reviewers across several rounds, and hand it back for the
author to act on.

## Non-negotiables (the scoring ruler)

1. App-independence. Works in any browser, on any OS, with native zoom. Not
   bound to a single editor, terminal, or note app.
2. Bulletproof reliability. No persistent connection of any kind, so the
   timeout/socket failure class cannot occur. A reviewer can sit with the file
   for an hour, walk away, return, and lose nothing.
3. Clean round-trip. Each note anchors to the exact words it concerns, and the
   feedback reads back unambiguously with no guessing about which text it meant.
4. Takeaway / handoff. The entire review is a portable artifact that can be
   paused, resumed, or passed to additional reviewers, then returned to the
   author.

"Pleasant to read, panels allowed" ranks below these four and may be traded
against them.

## Architecture

Three pieces. The template is the only real code.

- `template.html` — one self-contained file: a small bundled Markdown renderer,
  the highlight and note UI, and the save logic. No build step, no npm, no
  server, ever.
- `<doc>-view.html` — the working artifact. Produced by baking a document's raw
  Markdown into a copy of the template. Self-contained: it carries the rendered
  document and, after saving, the reviewers' notes, in one file.
- Two thin Claude Code skills: `/margin-send <file.md>` (bake and open) and `/margin-collect`
  (read the embedded notes back and act on them).

The source `<doc>.md` is only ever an input. It is never edited by the reviewer
and never mutated by the viewer. When the author acts on feedback, the author
edits `<doc>.md` and regenerates the view.

## Data flow

1. `/margin-send plan.md` reads `template.html`, injects `plan.md` as a string into a
   `<script id="margin-source" type="text/markdown">` block, writes
   `plan-view.html`, and opens it in Helium (`open -a Helium`). The command does
   string injection only: no Markdown-to-HTML conversion by the model, no server.
2. Helium opens the single self-contained file. The bundled renderer paints the
   document full-window on load. JavaScript is required for the annotation UI
   regardless, so rendering client-side costs nothing extra.
3. The reviewer selects text, a floating "+ note" button appears, and a margin
   card opens anchored to the selection. The reviewer types. The span highlights.
4. Save bakes the current note set into a `<script id="margin-notes"
   type="application/json">` block inside `plan-view.html`, written in place via
   the File System Access API. Any non-Chromium browser falls back to a download.
5. The reviewer passes the one file to the next reviewer, who opens it, sees all
   prior notes rendered in place, adds their own, and saves again. The file is a
   growing ledger across rounds.
6. `/margin-collect` extracts only the `margin-notes` JSON from `plan-view.html`,
   presents each unresolved note with its quoted anchor and thread, and acts:
   the author edits `plan.md`, appends replies into the notes block authored as
   "Claude", marks notes resolved, and regenerates the view while preserving the
   ledger.

## Notes data model

```json
{
  "schemaVersion": 1,
  "doc": "plan.md",
  "notes": [
    {
      "id": "n1",
      "author": "Aeva",
      "color": "#6ea0ff",
      "created": "2026-06-20T19:40:00Z",
      "anchor": { "quote": "full timeline", "prefix": "and pull the ", "suffix": " then dump to" },
      "thread": [
        { "author": "Aeva",   "ts": "2026-06-20T19:40:00Z", "body": "too crude, want bigrams" },
        { "author": "Claude", "ts": "2026-06-20T19:55:00Z", "body": "done, added bigrams and trigrams" }
      ],
      "resolved": false
    }
  ]
}
```

## Anchoring mechanism

A highlight is stored as a text-quote selector: the exact quoted words plus a
short prefix and suffix of surrounding text (about thirty characters each).
Character offsets are not used because they shatter on any edit.

Repaint on open: locate occurrences of the quote in the rendered text, and where
a quote appears more than once, disambiguate by matching the stored prefix and
suffix. Wrap the matched range and align its margin card.

Graceful degradation is the load-bearing reliability property. The truth of a
note is the pair {quoted words, comment}. If repaint ever fails to relocate a
span on a heavily edited document, the note is listed at the top of the margin as
unanchored with its quote shown, and the comment still reaches the author intact.
The channel degrades to readable text. It never breaks.

## Save model

The decision of when to save is made low-stakes by ensuring work cannot be lost
between saves.

- localStorage autosave: every note and edit persists to the browser instantly,
  keyed to the document, so a closed tab or a crash loses nothing.
- Physical Save button in the header, primary affordance, showing the unsaved
  state. Save overwrites `<doc>-view.html` in place via the File System Access
  API, baking the notes into the embedded block. This is the deliberate
  seal-this-round, ready-to-hand-off action.
- ⌘S is a secondary accelerator that calls `preventDefault` so it triggers our
  save rather than the browser's Save-Page-As dialog.
- A beforeunload guard warns when closing with unsaved changes.

The File System Access API requires a first user gesture to grant a write handle,
so round one's first Save shows the browser's confirm for `plan-view.html`; after
that, saves are silent. This is a browser security rule, not a design choice.

Reconstruction invariant. Save must rebuild the file from static parts: the
template shell, the untouched source-Markdown block, and the freshly serialized
notes block. It must never serialize the live, mutated DOM (the rendered
Markdown, the highlight wraps, the injected margin cards), because re-opening
such a file would render on top of already-rendered content and double-initialise
the UI. Because a `file://` page cannot fetch itself, the save function holds the
shell as a JavaScript string template and assembles output as shell + unchanged
source + updated notes JSON. Stated this way, the doubling bug cannot occur by
construction.

This invariant depended on a platform fact, now verified. A spike on 2026-06-20
confirmed that `showSaveFilePicker` is present in Helium and that the File System
Access API writes successfully to disk from a double-clicked `file://` page, on
the real delivery path. The single-file ledger and in-place save model stand on
evidence.

The download-only fallback remains documented for non-Chromium browsers. It does
not overwrite in place (browsers emit `plan-view(1).html`, `plan-view(2).html`,
and so on), so it does not preserve the single-file ledger; it is a degraded path
for portability to other machines, not the primary transport.

## Features

Essential:
- Select text to create a note, via a floating button on selection.
- Margin note card with author, body, and timestamp; edit and delete own note.
- Reply thread inside a note, for author replies and reviewer-to-reviewer
  exchange.
- Resolve toggle that collapses or greys a handled note.
- Reviewer identity set once and remembered; notes colour-coded by author.
- Save, backed by the three-layer safety net above.

Worth it, low cost:
- Hide-resolved toggle.
- Click a highlight to scroll its card into view, and the reverse.
- Header readout: document name, note count, current reviewer.

Cut from v1 (reinstate on request):
- Filter-by-author, search, tags or categories on notes.
- Manual highlight colours (auto colour-by-author already separates reviewers).
- Export-notes-as-Markdown (the model reads the embedded JSON directly).

Each cut item is annotation surface area that adds bug risk without serving a
real review round. Leanness here is a reliability decision.

## Multi-round handoff semantics

Notes always bake into the html itself, never into a loose `.json` and never a
zip. Each reviewer opens the same file, sees every prior comment, adds theirs,
and saves. Notes carry author and timestamp, so the ledger accumulates across
one round or several without overwriting earlier reviewers. Regeneration by the
author preserves the existing notes block: `/margin-send` over an existing
`<doc>-view.html` carries the ledger forward rather than discarding it.

## Token-efficiency invariant

`/margin-collect` never reads the raw embedded JSON into context. A local extraction
script shipped with the skill parses the `margin-notes` block on disk and
emits a minimal, model-facing digest: for each note, only the quoted span, the
comment thread, the author, and the resolved flag. It strips the viewer machinery
the model never reasons over (ids, colours, timestamps, and the prefix/suffix
anchoring context), and by default filters to unresolved notes. Only that digest
enters the context window; the full JSON stays on disk for the viewer. The disk
format is therefore complete (the viewer needs anchors and styling) while the
context format carries meaning alone, and the script runs locally so none of the
stripped envelope ever touches the context window. The source document is read
only when acting
on a specific note, and then by jumping to the quoted anchor rather than reading
the whole file. The quote is captured from rendered text, so it may not match the
Markdown source verbatim where formatting intervened (`**bold**`, links, table
cells), which makes the source jump best-effort: on a miss, acting on that note
falls back to reading a wider slice. Correctness is unaffected, since the note
and its quote are already in hand; only the efficiency claim narrows for those
notes. Re-read cost scales with how much the reviewers wrote, never with
the document's length. Conversion cost is zero: string injection plus client-side
render, both deterministic.

## Known risks to resolve in the plan

- Rendered-text anchoring when a quoted phrase occurs more than once; prefix and
  suffix disambiguation must be specified precisely, including the all-identical
  case.
- File System Access first-gesture flow and the download fallback path.
- Render performance on long documents.
- Overlapping or adjacent highlights and how their margin cards stack.
- Carrying the notes ledger forward correctly when the author regenerates the
  view after editing the source.
