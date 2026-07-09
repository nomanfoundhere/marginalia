---
name: margin-send
description: Bake a Markdown file into a self-contained annotation view and open it in Helium for priority-based review of a plan, writeup, or ordinary text output.
---

# margin-send

Turn `<doc>.md` into `<doc>-view.html` and open it for review.

1. Resolve the project root (the `marginalia/` checkout) and the target `.md` path from the user.
2. Run: `python3 <root>/build-view.py <path-to-doc.md>`
   - This writes `<doc>-view.html` next to the source and prints its path.
   - If a `<doc>-view.html` already exists, its notes are carried forward and
     each is stamped against the new source: notes whose quoted span no longer
     appears show as "text changed" in the viewer — the usual sign the span
     was revised in response.
3. Open it: `open -a Helium <printed-path>`
4. Tell the user: select text, then choose Critical, Important, Refinement, or
   Strike. Priority creates a note draft and applies the red, amber, or blue
   source highlight; Strike records a direct deletion. Keys `1`, `2`, `3`, and
   `X` do the same without reaching for the toolbar. Clicking a note span opens
   its focused discussion. To enable in-place saving, drag the file from Finder
   onto its own window once; after that saving is one click.

Do not edit `<doc>.md` here. This skill only produces and opens the view.
