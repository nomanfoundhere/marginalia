#!/usr/bin/env python3
import argparse
import base64
import copy
import datetime
import hashlib
import json
import pathlib
import re
import sys

PRIORITY_RANK = {"refinement": 1, "important": 2, "critical": 3}
NOTES_RE = re.compile(r'(<script id="margin-notes" type="text/plain">)(.*?)(</script>)', re.DOTALL)
SOURCE_RE = re.compile(r'<script id="margin-source" type="text/plain">(.*?)</script>', re.DOTALL)

def _digest(value) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _anchor_key(note: dict) -> tuple:
    anchor = note.get("anchor") or {}
    return (anchor.get("quote", ""), anchor.get("prefix", ""), anchor.get("suffix", ""))

def _entry_key(note: dict, entry: dict, index: int) -> str:
    if entry.get("id"):
        return "id:" + str(entry["id"])
    return "legacy:" + _digest({"note": note.get("id"), "index": index,
                                 "author": entry.get("author"), "ts": entry.get("ts"),
                                 "body": entry.get("body"), "draft": entry.get("draft", False)})

def _same_note(left: dict, right: dict) -> bool:
    if _anchor_key(left) != _anchor_key(right):
        return False
    left_created, right_created = left.get("created"), right.get("created")
    return not left_created or not right_created or left_created == right_created

def _merge_threads(left: dict, right: dict) -> list:
    entries = []
    seen = set()
    for note in (left, right):
        for index, entry in enumerate(note.get("thread") or []):
            key = _entry_key(note, entry, index)
            if key not in seen:
                seen.add(key)
                entries.append(copy.deepcopy(entry))
    return sorted(entries, key=lambda entry: (entry.get("ts") or "", entry.get("id") or ""))

def _later(left, right):
    return max(left or "", right or "") or None

def merge_note(left: dict, right: dict) -> dict:
    merged = copy.deepcopy(left)
    merged["thread"] = _merge_threads(left, right)
    merged["resolved"] = bool(left.get("resolved") and right.get("resolved"))
    if merged["resolved"]:
        merged["resolvedAt"] = _later(left.get("resolvedAt"), right.get("resolvedAt"))
    else:
        merged.pop("resolvedAt", None)
    if left.get("srcCheck") == "missing" or right.get("srcCheck") == "missing":
        merged["srcCheck"] = "missing"
    elif left.get("srcCheck") or right.get("srcCheck"):
        merged["srcCheck"] = "found"
    left_priority, right_priority = left.get("priority"), right.get("priority")
    if PRIORITY_RANK.get(right_priority, 0) > PRIORITY_RANK.get(left_priority, 0):
        merged["priority"] = right_priority
    merged["updatedAt"] = _later(left.get("updatedAt"), right.get("updatedAt"))
    return merged

def _unique_conflict_id(note: dict, used: set) -> str:
    base = str(note.get("id") or "legacy-note")
    candidate = base + "-merge-" + _digest(note)[:8]
    suffix = 2
    while candidate in used:
        candidate = base + "-merge-" + _digest(note)[:8] + "-" + str(suffix)
        suffix += 1
    return candidate

def merge_ledgers(ledgers: list[dict]) -> dict:
    if not ledgers:
        raise ValueError("at least one ledger is required")
    first = ledgers[0]
    doc_name, source_sha = first.get("docName"), first.get("sourceSha256")
    for ledger in ledgers[1:]:
        if ledger.get("docName") != doc_name or ledger.get("sourceSha256") != source_sha:
            raise ValueError("ledgers must review the same document and source snapshot")
    merged_notes, index_by_id = [], {}
    for ledger in ledgers:
        for note in ledger.get("notes") or []:
            candidate = copy.deepcopy(note)
            note_id = str(candidate.get("id") or "")
            if note_id and note_id in index_by_id:
                position = index_by_id[note_id]
                existing = merged_notes[position]
                if _same_note(existing, candidate):
                    merged_notes[position] = merge_note(existing, candidate)
                    continue
                candidate["id"] = _unique_conflict_id(candidate, set(index_by_id))
                note_id = candidate["id"]
            elif not note_id:
                candidate["id"] = _unique_conflict_id(candidate, set(index_by_id))
                note_id = candidate["id"]
            index_by_id[note_id] = len(merged_notes)
            merged_notes.append(candidate)
    return {
        "docName": doc_name,
        "sourceSha256": source_sha,
        "extractedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "schemaVersion": max(int(ledger.get("schemaVersion", 1)) for ledger in ledgers),
        "notes": merged_notes,
    }

def apply_ledger_to_view(ledger: dict, view_path: str) -> None:
    path = pathlib.Path(view_path)
    html = path.read_text(encoding="utf-8")
    source_match = SOURCE_RE.search(html)
    notes_match = NOTES_RE.search(html)
    if not source_match or not notes_match:
        raise ValueError("view is missing a Margin Notes source or ledger block")
    try:
        source = base64.b64decode(source_match.group(1).strip()).decode("utf-8")
    except Exception as error:
        raise ValueError("view source block could not be read") from error
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != ledger.get("sourceSha256"):
        raise ValueError("merged ledger reviews a different source snapshot than this view")
    payload = {"schemaVersion": ledger.get("schemaVersion", 2), "notes": ledger.get("notes", [])}
    encoded = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("ascii")
    path.write_text(NOTES_RE.sub(lambda match: match.group(1) + encoded + match.group(3), html, count=1),
                    encoding="utf-8")

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Merge Margin Notes sidecar ledgers safely.")
    parser.add_argument("ledgers", nargs="+", help="<doc>.notes.json files from separate reviewers")
    parser.add_argument("--out", required=True, help="path for the merged ledger")
    parser.add_argument("--view", help="matching <doc>-view.html to receive the merged notes")
    args = parser.parse_args(argv)
    try:
        ledgers = [json.loads(pathlib.Path(path).read_text(encoding="utf-8")) for path in args.ledgers]
        merged = merge_ledgers(ledgers)
        if args.view:
            apply_ledger_to_view(merged, args.view)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print("ledger merge failed: %s" % error, file=sys.stderr)
        return 2
    pathlib.Path(args.out).write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
