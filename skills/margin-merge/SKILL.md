---
name: margin-merge
description: Merge Margin Notes sidecars from parallel reviewers and apply the combined ledger to the matching standalone view.
---

# margin-merge

Combine independent reviews of the same Markdown snapshot without copying notes
between browser files by hand.

Create separate reviewer copies before parallel work:

    bash <root>/scripts/prepare-review-copies.sh <doc>-view.html aria mina

Each reviewer saves their own copy, then runs collection in that copy's directory
to produce a sidecar for merge.

1. Resolve the project root, the matching `<doc>-view.html`, and each reviewer
   sidecar (`<doc>.notes.json`). All sidecars must have the same document name
   and `sourceSha256`.
2. Run:

       python3 <root>/merge-ledgers.py reviewer-a.notes.json reviewer-b.notes.json \
         --out <doc>.notes.json --view <doc>-view.html

3. The command preserves independent notes, unions thread entries for the same
   globally identified note, retains the highest priority when copies disagree,
   and keeps a note open until every merged copy resolves it. A legacy `n1`
   collision with different anchors is retained as two notes, never collapsed.
4. Open the view normally. The command verifies the embedded source hash before
   writing the merged ledger, so it refuses to apply feedback to a different
   document revision.
