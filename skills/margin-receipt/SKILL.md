---
name: margin-receipt
description: Record an agent's note-by-note revision outcomes back into a Marginalia review view without resolving reviewer feedback. Use after applying a revision packet.
---

# margin-receipt

Record what happened to each reviewed note after revising the Markdown source.

1. Read the revision packet from `python3 <root>/distill.py --packet <doc>-view.html`.
2. Revise the Markdown source. Do not resolve reviewer notes automatically.
3. Create a receipt JSON file containing a list or `{ "receipts": [...] }`. Each
   receipt needs `noteId`, `outcome`, and `reason`.
   - `outcome` is one of `applied`, `partially-applied`, `declined`, or
     `needs-clarification`.
   - Use `newLocation` when the result has a useful source heading path or line
     range.
4. Run:

       python3 <root>/record-receipts.py <doc>-view.html receipts.json \
         --author "Agent" --source <doc>.md

5. Tell the reviewer that receipts describe the agent's action but leave the note
   open. The reviewer decides whether to resolve it.

Never write `resolved: true` as part of recording a receipt.
