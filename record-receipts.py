#!/usr/bin/env python3
import argparse
import base64
import datetime
import hashlib
import json
import pathlib
import re
import sys
import uuid

import distill

OUTCOMES = {"applied", "partially-applied", "declined", "needs-clarification"}
NOTES_RE = re.compile(r'(<script id="margin-notes" type="text/plain">)(.*?)(</script>)', re.DOTALL)

def _utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

def _receipt_items(payload):
    items = payload.get("receipts") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("receipt input must be a list or an object with a receipts list")
    return items

def record_receipts(view_path: str, payload, author: str = "Agent", current_source: str | None = None):
    path = pathlib.Path(view_path)
    html = path.read_text(encoding="utf-8")
    data = distill.extract_notes(html)
    snapshot = distill.extract_source(html)
    doc_name = distill.extract_doc_name(html)
    source = current_source if current_source is not None else snapshot
    source_sha = hashlib.sha256((source or "").encode("utf-8")).hexdigest()
    notes = {str(note.get("id")): note for note in data.get("notes", [])}
    added = 0
    for item in _receipt_items(payload):
        if not isinstance(item, dict):
            raise ValueError("each receipt must be an object")
        note_id = str(item.get("noteId") or "")
        if note_id not in notes:
            raise ValueError("receipt references an unknown note: %s" % note_id)
        outcome = item.get("outcome")
        if outcome not in OUTCOMES:
            raise ValueError("receipt outcome must be one of: %s" % ", ".join(sorted(OUTCOMES)))
        reason = (item.get("reason") or "").strip()
        if not reason:
            raise ValueError("receipt reason is required")
        expected_sha = item.get("sourceSha256")
        if expected_sha and expected_sha != source_sha:
            raise ValueError("receipt source hash does not match the supplied current source")
        receipt = {
            "id": item.get("id") or "receipt-" + str(uuid.uuid4()),
            "author": item.get("author") or author,
            "outcome": outcome,
            "reason": reason,
            "recordedAt": item.get("recordedAt") or _utc_now(),
            "sourceSha256": source_sha,
        }
        if item.get("newLocation") is not None:
            if not isinstance(item["newLocation"], dict):
                raise ValueError("receipt newLocation must be an object")
            receipt["newLocation"] = item["newLocation"]
        stored = notes[note_id].setdefault("receipts", [])
        if any(existing.get("id") == receipt["id"] for existing in stored):
            continue
        stored.append(receipt)
        added += 1
    data["schemaVersion"] = max(int(data.get("schemaVersion", 1)), 3)
    encoded = base64.b64encode(json.dumps(data, ensure_ascii=False).encode("utf-8")).decode("ascii")
    if not NOTES_RE.search(html):
        raise ValueError("view is missing a Margin Notes ledger block")
    path.write_text(NOTES_RE.sub(lambda match: match.group(1) + encoded + match.group(3), html, count=1),
                    encoding="utf-8")
    distill.write_sidecar(str(path), data, snapshot, doc_name)
    return added

def main(argv=None):
    parser = argparse.ArgumentParser(description="Record agent revision receipts without resolving reviewer notes.")
    parser.add_argument("view", help="<doc>-view.html to receive receipts")
    parser.add_argument("receipts", help="JSON list or {receipts:[...]} input")
    parser.add_argument("--author", default="Agent", help="default receipt author")
    parser.add_argument("--source", help="current Markdown source used for the receipt hash")
    args = parser.parse_args(argv)
    try:
        payload = json.loads(pathlib.Path(args.receipts).read_text(encoding="utf-8"))
        current = pathlib.Path(args.source).read_text(encoding="utf-8") if args.source else None
        count = record_receipts(args.view, payload, author=args.author, current_source=current)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print("receipt recording failed: %s" % error, file=sys.stderr)
        return 2
    print("recorded %d receipt(s)" % count)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
