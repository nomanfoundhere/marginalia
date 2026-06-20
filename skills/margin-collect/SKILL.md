---
name: margin-collect
description: Read reviewer notes back from a Margin Notes view file as a token-cheap digest and act on them. Use after a reviewer has annotated and saved a <doc>-view.html.
---

# margin-collect

Pull feedback out of `<doc>-view.html` and act on it.

1. Resolve the project root and the `<doc>-view.html` path.
2. Run: `python3 <root>/distill.py <doc>-view.html`
   - Prints only unresolved notes as `[id · author · status] "quote"` plus thread lines.
   - Add `--all` to include resolved notes.
3. Read ONLY that digest. Do not read the raw `.html` or the whole `.md` to understand the feedback; each note carries its quoted span.
4. For each note: revise the source `<doc>.md` (jump to the quoted span; it is rendered text, so the source jump is best-effort — widen the read only on a miss).
5. After revising, regenerate the view with `/margin-send <doc>.md` so the author's changes and any replies are reflected; the existing notes ledger is preserved.
6. Optionally append a reply for the user to see in the viewer by editing the note's thread, then regenerate.

Token rule: the digest is the only thing that enters context by default.
