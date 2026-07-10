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
   - Feedback is grouped as Critical, Important, Refinements, and Deletions.
     Each unresolved item prints as `[id · author · status · tag]
     <doc>.md:LINES "quote"` plus thread lines. `delete` is an explicit removal;
     the other tags are priority levels for written feedback.
   - A `<doc>.notes.json` sidecar is written next to the view file; commit it
     so review history lands in git. `--no-sidecar` suppresses.
   - Use `--priority=critical,important` to work the urgent queue first, or
     `--status` for a compact machine-readable summary.
3. When the agent can read the current `<doc>.md`, prefer
   `python3 <root>/distill.py --packet <doc>-view.html`. The packet carries
   operation, priority, review round, heading paths, quote/prefix/suffix anchors,
   source hashes, receipts, and span status without duplicating the document text
   into context.
4. Read ONLY the digest or packet by default. Edit at the printed line addresses;
   on an `(unlocated)` note, select its replacement span in the viewer and use
   Reattach rather than guessing which rewritten passage it meant.
5. Apply `delete` operations directly. Apply Critical before Important, then
   Refinement. The written comment supplies the requested change.
6. Record an outcome with `/margin-receipt` after revising. Do not resolve the
   reviewer’s note automatically: a receipt states what happened while the
   reviewer retains that decision.
7. After revising, regenerate the view with `/margin-send <doc>.md` so the author's changes and any replies are reflected; the existing notes ledger is preserved.
8. Optionally append a reply for the user to see in the viewer by editing the note's thread, then regenerate.

Token rule: the digest or packet is the only review data that enters context by
default. The source enters only when the agent cannot already read the current file.
