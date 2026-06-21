# Marginalia — visual redesign and save-flow overhaul (v2)

Date: 2026-06-21
Status: approved for planning (visual direction approved from mockups)
Builds on: `2026-06-20-marginalia-design.md`, which stays authoritative for
architecture, anchoring, the single-file ledger, and token efficiency. Nothing
in the data flow or file format changes here.

## What changes, what does not

The presentation layer of the viewer and the save experience change. The tested
machinery does not: `build-view.py` assembly, `margin-core.js`
(`locateAnchor`, `reconstructView`), `distill.py`, the two skills, the base64
payload format, and the reconstruction invariant all stay as they are. Every
change lands in `template.html` (its `<style>`, the boot `<script>`, and a small
`<head>` init script) plus one new build-time assertion. The no-npm, no-server,
single-file, offline constraints hold throughout.

## Non-negotiables carried forward

Unchanged from v1: no build step or server in the end-user path; one
self-contained `<doc>-view.html`; source `.md` is input-only; in-place save via
the File System Access API with a download fallback; the reconstruction
invariant (save rebuilds from the pristine page HTML captured at load, swapping
only the `margin-notes` block, never the live DOM); text-quote anchoring with
ambiguous matches degrading to unanchored; `/margin-collect` reads only the
digest.

One constraint is added: **offline fonts**. The artifact fetches nothing at
runtime, so the type system is the platform stack only (`-apple-system`,
`Segoe UI`, `system-ui` for text; `ui-monospace` for ids and metadata). No web
fonts, no `@font-face` URL, no `<link>` to a font host. This keeps the file
self-contained and is enforced by a build check (below).

## Visual system

Colour, type, depth, and spacing resolve through CSS custom properties on
`<html>`, switched by a `data-theme` attribute. Two themes ship: dark (a
mid-charcoal desk `#1a1d24` carrying lighter panels `#23272f`) and light (a
light-grey desk `#f3f4f6` carrying white panels). Tokens cover surface, ink at
three weights, hairlines at two weights, highlight tints, the per-theme shadows,
the field fill, the accent, and the reviewer colours.

Depth comes from hard, no-blur offset shadows: roughly `5–6px` on the document,
`4px` on note cards, `2px` on buttons. The offset and opacity are tuned per
theme so the shadow reads against its own background: a near-black offset on the
mid-charcoal desk in dark, a soft grey offset on the light desk in light. The
desk in dark is deliberately not near-black, because a black offset shadow has
nothing to read against on near-black. This shadow is the primary device that
gives every panel a recognisable boundary.

Highlights render as an author-coloured underline over a faint tint, the colour
taken from the existing `colorFor(author)` hash so a highlight and its note card
share one hue.

## Theme switching

`data-theme` on `<html>` drives everything. First open follows
`prefers-color-scheme`; a toggle in the header flips it and writes the choice to
`localStorage('mn-theme')`, which wins on subsequent opens.

A tiny script at the top of `<head>`, before any body or stylesheet paint, sets
`data-theme` from `localStorage('mn-theme')` falling back to
`matchMedia('(prefers-color-scheme: dark)')`. Running before first paint removes
the light/dark flash.

Theme is per-viewer, never baked into the shared ledger. `PRISTINE` is captured
from `outerHTML` at boot and will contain whatever `data-theme` the init script
set for this viewer, but on reopen the init script re-derives the attribute from
the new viewer's own storage and OS, overriding any value carried in the file.
The load-bearing requirement: the init script runs on every load regardless of
the attribute already present.

## Identity, replacing the native prompt

The header carries an identity chip: a reviewer colour dot and the name. Clicking
it reveals an inline text input, not a browser modal. Setting a name writes
`localStorage('mn-reviewer')`.

The native `prompt()` is removed. Creating a note while no identity is set stores
the pending selection's anchor, focuses the identity input, and on submit creates
the note against the stored anchor. No note exists until a name does, and no OS
dialog ever appears.

## Note card and threading

A card is an id chip (`n3`) and two quiet icon buttons (resolve, delete) across
the top, then a thread of messages, then an inline reply composer at the foot.

Each message is one row: a monogram avatar filled with the author's colour, a
metadata line (author name, relative timestamp), and the body text. A connector
line runs avatar to avatar down the thread, continuous rather than the stub the
mockup showed. The first message is the note itself; replies are the same row
shape below it, so the card reads as a conversation rather than a body with
appendices.

Editability follows authorship, carried from the v1 fix: a message authored by
the current reviewer renders as an editable field, everyone else's as static
text. The composer is the current reviewer's avatar beside a `Reply…` field;
committing it appends a thread entry authored by that reviewer.

Three states the empty-document mockups never exercised are specified here:

- **Unanchored** (the stored quote no longer locates in the rendered text): the
  card pins to the top of the rail with an unanchored badge and its quote shown,
  and paints no highlight. The note and its quote still reach the author intact.
- **Resolved**: the card greys and collapses to its header; a header
  hide-resolved control removes resolved cards from the rail.
- **Empty**: a quiet rail message, "Select text in the document to leave a note."

The floating selection affordance (the "+ note" button) is restyled into the
skin; its behaviour is unchanged.

## Layout and anchor alignment

The document is a centred reading column with notes in the right margin. Cards
align vertically to their anchored highlight rather than stacking as a flat list.

Placement algorithm: for each anchored, visible note, measure the top offset of
its highlight within the document. Sort by offset. Place greedily into an
absolutely-positioned rail the height of the document, each card at
`max(anchorTop, previousCardBottom + gap)`, so a card never overlaps the one
above and drifts downward only under crowding. Unanchored cards (pinned top) and
hidden-resolved cards are excluded from the pass. Recompute on note change and on
resize. The known cost: on a long document with many clustered anchors, cards
drift below their highlight; this is acceptable for v2, and a leader line from
card to highlight is deferred.

Below an `~880px` breakpoint the layout collapses to one column: notes render
after the document as a full-width stacked list, anchor-alignment drops, and the
header controls wrap. Sizing uses relative units so the layout holds under native
browser zoom, which is a v1 non-negotiable.

## Save-flow overhaul

The weak point today: the first save makes the reviewer locate and overwrite the
exact `file://` page they are viewing through the OS picker, which is confusing
and produces `<doc>-view(1).html` on a misclick.

The redesign keeps the proven in-place mechanism and removes the navigation pain:

- The Save button shows three states: `Saved` (clean), `● Save` (dirty), and a
  transient `Saving…`.
- First save presents a one-time in-skin explainer (an inline panel, not a
  modal) that names the exact file to choose and says it happens once, then calls
  `showSaveFilePicker` with the suggested name and a stable `id` so the picker
  reopens in the same directory.
- After the first grant, the `FileSystemFileHandle` persists in IndexedDB keyed
  by document name. Later sessions retrieve it and re-save behind a single
  `requestPermission()` gesture, with no folder navigation.

Handle persistence across `file://` loads is the one assumption that needs
evidence: a `file://` origin is opaque, and storage partitioning may make
IndexedDB persistence unreliable there. A spike (mirroring the 2026-06-20
FS-Access spike) verifies it in Helium before the feature is built. If it fails,
the flow degrades to guided-first-save-only: the explainer and button states
stay, and each session re-picks the file once. That degrade is graceful, not a
blocker.

Autosave to localStorage, the beforeunload guard, the ⌘S accelerator, the
`savedAt`-gated hydrate, and the non-Chromium download fallback all carry forward
unchanged.

## Accessibility floor

Visible keyboard focus is preserved, not stripped. `prefers-reduced-motion`
disables the theme and press transitions. Controls (save, theme, resolve, delete,
reply) carry ARIA labels; the rail is a complementary region and notes are
articles. Colour is never the only signal, since every author dot sits beside the
author name. Text tokens meet WCAG AA contrast in both themes.

## How this stays within the constraints

CSS and JS live in `template.html` and are inlined offline by `build-view.py`;
system fonts mean nothing is fetched. The base64 payloads and the `</script>`
escape are untouched. The reconstruction invariant holds: `PRISTINE` is captured
before mutation, only the notes block is swapped, and theme is re-derived per
load rather than baked.

One build-time assertion is added: the assembled artifact contains no external
resource reference (no `http(s)` `<link>`, no `@import url(http…)`, no runtime
`fetch`), so the offline guarantee is checked by test rather than by inspection.

## GitHub release prep

A documentation track, independent of the viewer code, shippable after it:
a README carrying light and dark screenshots and a short demo, a LICENSE (MIT),
and a browser-support note (Chromium saves in place, others download). The
`.gitignore` already excludes session and OS artifacts.

## Testing

The existing Node and Python suites stay green, since their logic is untouched.
New automated coverage, where it is feasible without npm: the build-view test
asserts no external resource reference, that the five script closes still hold
(the escape), and that the theme init script is present. Everything
selection-, DOM-, and save-driven is a manual Helium matrix: both themes plus OS
default and toggle persistence; identity-chip first run; create, reply, resolve,
delete; unanchored and empty states; anchor-aligned stacking and collision;
the responsive breakpoint and native zoom; the save flow (first-save explainer,
persisted re-save, fallback); and the a11y checks (keyboard focus, reduced
motion). The save-flow spike runs first and its binary outcome selects the
persistence path or the fallback.

## Out of scope for v2

Leader lines from card to highlight; filter, search, and tags; manual highlight
colours; export-to-Markdown; the range-splitting highlighter for selections that
cross an element boundary. These remain deferred or cut as in v1.
