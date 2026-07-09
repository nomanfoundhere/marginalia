# Marginalia v3 — foundation and flow

Date: 2026-07-05 · Status: draft for review · Branch: claude/execute-plan-3louox

## Problem

The return leg of the round-trip runs on a vibe: `distill.py` emits rendered-text
quotes, and the collect skill tells the model to find the matching source span
"best-effort", falling back to reading the whole `.md` on a miss. The review
history has no durable home: notes live only inside the view HTML, outside git.
The workflow's success case produces its failure state: revising a flagged span
changes its quoted text, so the acted-on note unanchors and becomes
indistinguishable from one orphaned by accident. On the capture side, the only
gesture is highlight-with-note; there is no wordless way to flag a span, and the
first in-place save routes through a save-picker that demands re-finding the
open file plus an OS "Replace?" confirm.

The view file already carries the exact source snapshot the notes were made
against (`<script id="margin-source">`, base64). Every plumbing fix below
derives from that fact: the quote→source mapping needs no browser, no model,
and no current `.md`.

## Data model — schema v2

`{"schemaVersion": 2, "notes": [...]}` with per-note fields:

| field | values | notes |
|---|---|---|
| `kind` | `comment` \| `highlight` \| `underline` \| `strike` | v1 notes lack the field and read as `comment` |
| `color` | `yellow` \| `green` \| `pink` | highlights only |
| `srcCheck` | `found` \| `missing` | stamped by build-view on each rebuild |
| existing | `id`, `author`, `anchor{quote,prefix,suffix}`, `thread[]`, `resolved`, `savedAt` | unchanged |

Readers (viewer, distill) accept both versions; writers emit v2. A standalone
mark is a note with an empty thread; adding a message to it later promotes it
to a threaded note with no schema change. Resolve and delete apply uniformly.

## Plumbing

### P1 — source anchoring in distill

For each note, locate `anchor.quote` in the baked source snapshot and emit a
source address in the digest line:

    [m3 · aeva · open] plan.md:45-48 "the quoted span"

Matching runs in two passes. Exact `str.find` against the raw source first.
On a miss, a normalized pass: strip markdown syntax line-by-line (`**`, `*`,
`` ` ``, heading markers, `[text](url)` → `text`) while keeping a per-character
offset map back to raw lines, then search the normalized text. Multiple hits
disambiguate by prefix/suffix affix scoring with a strict-winner rule, ported
from `locateAnchor` in `margin-core.js`; shared fixtures assert JS/Python
parity. An unlocatable quote emits with no address and an `unlocated` tag,
never silently dropped.

`--context N` appends N raw source lines around each located anchor, so the
collect step edits from the digest alone instead of re-reading the `.md`.

### P2 — staleness stamp

distill resolves the current source (`DOC_NAME` sibling of the view file;
`--source PATH` overrides). Header states one of:

- `source matches the reviewed snapshot` (byte-identical), or
- `source has diverged since review` — and each note's quote is re-checked
  against the *current* source, tagging `(span changed in current source)`
  where it no longer appears.

The collect skill treats a diverged stamp as "verify the span before editing".

### P3 — sidecar ledger

Every distill run writes `<doc>.notes.json` next to the view file (suppress
with `--no-sidecar`): the decoded ledger pretty-printed, plus `docName`,
`sourceSha256` of the snapshot, and `extractedAt`. Committing it lands review
history in git; deleting a view file no longer destroys the conversation. The
sidecar is an export, not a second source of truth: the view file remains
authoritative, and the sidecar is regenerated on each collect.

### P4 — revision semantics in build-view

On rebuild with carried-forward notes, build-view stamps each note's
`srcCheck` by running the P1 matcher against the new source. The viewer
renders `missing` notes in a distinct "text changed since this note" state
(old quote preserved, styled apart from anchor-failure unanchoring), and
distill reports them the same way. The stamp is an approximation (raw-source
matching, not rendered-text), and errs toward flagging: a span reported
changed when only formatting moved costs one glance; the reverse costs a
misdirected edit.

## Surface

### S1 — mark toolbar

Selecting text raises a compact popover: three highlight color dots, underline,
strikethrough, comment. Mark tools create a standalone mark in one click;
comment opens the existing card-and-textarea flow. Standalone marks render in
the rail as thin entries (kind icon, color, quote snippet) that expand for
reply/resolve/delete. In-document styling: `mark.mn-hl` gains per-color
classes; underline and strike use text-decoration on the same span structure.
Overlap behavior for all kinds inherits the current highlight collision rule.
Both themes get color variants tuned for contrast.

Digest lines for standalone marks carry the kind in the bracket:

    [m4 · bob · open · highlight-yellow] plan.md:52 "another span"

A bare mark is a wordless flag; the thread remains the place to say why.

### S2 — first-save: drag-to-arm

Existing machinery (IndexedDB handle persistence, permission re-verify,
explainer panel) stays. Changes on top:

- **Arm at open.** When FSA is available and no stored handle verifies, a slim
  dismissible bar offers arming up front: "To let this file save itself, drag
  it from Finder onto this window — it lives at `<decoded location.pathname>`
  — or choose it once." Arming is decoupled from the first save.
- **Drag-to-arm.** `drop` on the window takes the dragged file via
  `DataTransferItem.getAsFileSystemHandle()`: no picker, no "Replace?"
  confirm. The dropped file's name must equal `SAVE_NAME`; a mismatch shows an
  inline "that is a different file" notice and does not arm.
- **Open-picker fallback.** The picker path switches `showSaveFilePicker` →
  `showOpenFilePicker` (same `id`, so the OS reopens the last directory),
  eliminating the Replace confirm. The explainer shows the full real path.
- **Degradation.** Handle persistence over `file://` is the shakiest link in
  Helium; if a stored handle fails verification the flow re-arms via the same
  bar. Firefox/Safari keep the download fallback untouched.

Verification is a browser checklist in Helium: drag-arm, picker-arm, handle
survival across reload and relaunch, mismatched-file drop.

### S3 — save-state chip

The Save button's three-state label grows into an explicit status chip beside
it, `aria-live="polite"`:

- `In file` — disk matches state
- `Safe on this Mac — not yet in the file` — autosaved to localStorage, file
  stale; the wording carries the handoff semantics (the file write is what
  travels)
- `Saving…` / `Not saved` as today

### S4 — native prompts out

The two `confirm()` calls shipped in the P1 batch conflict with the locked
no-native-prompt decision and are replaced:

- Delete: immediate removal plus a 6-second inline "Note m3 deleted — Undo"
  pill in the rail slot; undo restores the note object intact.
- Corrupt-ledger overwrite: an explainer-style in-page panel with explicit
  "Overwrite" / "Cancel" buttons replaces the native confirm in `save()`.

### S5 — keyboard path

With a non-empty selection and focus outside editable elements: `H` highlight
(last-used color), `U` underline, `S` strike, `C` comment, `Esc` dismisses the
popover. Card-to-card arrow navigation stays out of scope.

## Error handling

- Unlocatable quotes: digest emits `unlocated`, never drops the note (P1).
- Missing current source: staleness stamp reports `source file not found`,
  per-note re-check skipped (P2).
- Sidecar write failure (permissions, read-only dir): warning to stderr, exit
  code unchanged — distill's digest remains the primary output (P3).
- Drop of a non-file or wrong file: inline notice, state unchanged (S2).
- Undo pill expiry: the deleted note is gone from state; autosave and dirty
  tracking proceed as for any edit (S4).

## Testing

- Python: P1 matcher (exact, formatted spans, ambiguous, unlocatable),
  offset-map correctness, staleness stamp, sidecar content, `--context`.
- Parity: shared JSON fixtures run through both `locateAnchor` (node) and the
  Python port; identical verdicts required.
- JS: v1→v2 migration, digest rendering of marks, undo restore, srcCheck
  states in the rail.
- Browser (Helium, manual checklist): S2 flows, toolbar on both themes,
  aria-live chip announcements.

## Out of scope

Plugin packaging and skill ergonomics (Phase 2), fuzzy re-anchoring, parallel
review merge, arrow-key card navigation, dark-theme avatar contrast, vendored
marked update path.

## Decision record

- Distill-side source mapping over capture-time source offsets: works
  retroactively on existing view files, touches no render code, and the
  snapshot guarantees mapping against the version the reviewer saw.
- Drag-to-arm as the primary first-save gesture, picker demoted to fallback:
  the only path that avoids both folder navigation and the Replace confirm.
- Standalone marks are feedback signals in the digest, not visual-only ink.
- Sidecar is derived output, not a second writable store: one source of truth.
