#!/usr/bin/env python3
"""Distill the embedded margin-notes block into a token-cheap text digest."""
import base64, json, re, sys

NOTES_RE = re.compile(
    r'<script id="margin-notes" type="text/plain">(.*?)</script>', re.DOTALL)

def extract_notes(html_text: str) -> dict:
    m = NOTES_RE.search(html_text)
    if not m:
        raise SystemExit("no margin-notes block found")
    raw = m.group(1).strip()
    if not raw:
        return {"schemaVersion": 1, "notes": []}
    return json.loads(base64.b64decode(raw).decode("utf-8"))

def digest(data: dict, include_resolved: bool = False) -> str:
    notes = data.get("notes", [])
    lines, shown = [], 0
    for n in notes:
        if n.get("resolved") and not include_resolved:
            continue
        shown += 1
        status = "resolved" if n.get("resolved") else "open"
        quote = (n.get("anchor") or {}).get("quote", "")
        lines.append('[%s · %s · %s] "%s"' % (n.get("id", "?"), n.get("author", "?"), status, quote))
        for e in n.get("thread", []):
            body = (e.get("body") or "").strip()
            if body:
                lines.append("  %s: %s" % (e.get("author", "?"), body))
        lines.append("")
    scope = "" if include_resolved else " unresolved"
    header = "%d%s note(s) of %d total" % (shown, scope, len(notes))
    return (header + "\n\n" + "\n".join(lines)).rstrip()

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if len(args) != 1:
        print("usage: distill.py [--all] <doc-view.html>", file=sys.stderr); sys.exit(2)
    with open(args[0], encoding="utf-8") as f:
        data = extract_notes(f.read())
    print(digest(data, include_resolved="--all" in sys.argv))
