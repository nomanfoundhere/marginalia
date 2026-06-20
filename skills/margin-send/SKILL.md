---
name: margin-send
description: Bake a Markdown file into a self-contained annotation view and open it in Helium for span-level review. Use when the author wants a reviewer to leave precise margin notes on a plan or writeup.
---

# margin-send

Turn `<doc>.md` into `<doc>-view.html` and open it for review.

1. Resolve the project root (the `marginalia/` checkout) and the target `.md` path from the user.
2. Run: `python3 <root>/build-view.py <path-to-doc.md>`
   - This writes `<doc>-view.html` next to the source and prints its path.
   - If a `<doc>-view.html` already exists, its notes are carried forward; the doc content is refreshed from the current `.md`.
3. Open it: `open -a Helium <printed-path>`
4. Tell the user: select text, click "+ note", type, and click Save when a round is done; the file can be passed to other reviewers and accumulates their notes.

Do not edit `<doc>.md` here. This skill only produces and opens the view.
