---
name: margin-collect
description: Read reviewer notes back from a Margin Notes view file as a token-cheap digest and act on them. Use after a reviewer has annotated and saved a <doc>-view.html.
---

# margin-collect

Pull feedback out of `<doc>-view.html` and act on it.

1. Resolve the project root and the `<doc>-view.html` path.
2. Run: `python3 <root>/distill.py <doc>-view.html`
   - The header states whether the current `.md` still matches the reviewed
     snapshot; treat "diverged" as: verify each span before editing.
   - Feedback is grouped by meaning. Each unresolved item prints as
     `[id · author · status · tag] <doc>.md:LINES "quote"` plus thread lines.
     Highlight tags are semantic (`question`, `approved`, `needs-work`);
     underline and strike remain wordless span flags.
   - A `<doc>.notes.json` sidecar is written next to the view file; commit it
     so review history lands in git. `--no-sidecar` suppresses.
3. Read ONLY that digest. Edit at the printed line addresses; on an
   `(unlocated)` note, re-run with `--context=3` instead of reading the whole file.
4. For each note: revise the source `<doc>.md` at its address.
5. After revising, regenerate the view with `/margin-send <doc>.md` so the author's changes and any replies are reflected; the existing notes ledger is preserved.
6. Optionally append a reply for the user to see in the viewer by editing the note's thread, then regenerate.

Token rule: the digest is the only thing that enters context by default.
