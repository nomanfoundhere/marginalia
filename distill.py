#!/usr/bin/env python3
"""Distill the embedded margin-notes block into a token-cheap text digest."""
import base64, json, re, sys

NOTES_RE = re.compile(
    r'<script id="margin-notes" type="text/plain">(.*?)</script>', re.DOTALL)

import importlib.util, pathlib
_spec = importlib.util.spec_from_file_location(
    "margin_anchor", pathlib.Path(__file__).resolve().parent / "margin_anchor.py")
margin_anchor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(margin_anchor)

SOURCE_RE = re.compile(
    r'<script id="margin-source" type="text/plain">(.*?)</script>', re.DOTALL)
TITLE_RE = re.compile(r'<title>Margin Notes — (.*?)</title>')

def extract_source(html_text: str):
    m = SOURCE_RE.search(html_text)
    if not m or not m.group(1).strip():
        return None
    try:
        return base64.b64decode(m.group(1).strip()).decode("utf-8")
    except Exception:
        return None

def extract_doc_name(html_text: str) -> str:
    m = TITLE_RE.search(html_text)
    return m.group(1) if m else "source"

def find_current_source(view_path: str, html_text: str, override=None):
    """Path of the current .md, or None. The sibling guess runs only on a real
    title match: the doc-name fallback would otherwise read any file that
    happens to be named "source" next to the view."""
    if override:
        return override if pathlib.Path(override).exists() else None
    if not TITLE_RE.search(html_text):
        return None
    cand = pathlib.Path(view_path).resolve().parent / extract_doc_name(html_text)
    return str(cand) if cand.exists() else None

def staleness(snapshot: str, current) -> str:
    if current is None:
        return "current source not found alongside view; pass --source"
    if current == snapshot:
        return "source matches the reviewed snapshot"
    return "source has diverged since review"

def extract_notes(html_text: str) -> dict:
    m = NOTES_RE.search(html_text)
    if not m:
        raise SystemExit("no margin-notes block found")
    raw = m.group(1).strip()
    if not raw:
        return {"schemaVersion": 1, "notes": []}
    return json.loads(base64.b64decode(raw).decode("utf-8"))

def digest(data: dict, include_resolved: bool = False,
           source: str = None, doc_name: str = "source", context: int = 0, current_source: str = None) -> str:
    notes = data.get("notes", [])
    lines, shown = [], 0
    for n in notes:
        if n.get("resolved") and not include_resolved:
            continue
        shown += 1
        status = "resolved" if n.get("resolved") else "open"
        anchor = n.get("anchor") or {}
        quote = anchor.get("quote", "")
        tag = ""
        kind = n.get("kind", "comment")
        if kind != "comment":
            tag = " · " + kind + ("-" + n["color"] if n.get("color") else "")
        addr, span = "", None
        if source is not None:
            span = margin_anchor.locate_in_source(source, anchor)
            addr = (" %s:%s" % (doc_name, margin_anchor.line_range(source, span[0], span[1]))
                    if span else " (unlocated)")
        if current_source is not None and current_source != source and quote:
            if margin_anchor.locate_in_source(current_source, anchor) is None:
                addr += " (span changed in current source)"
        lines.append('[%s · %s · %s%s]%s "%s"'
                     % (n.get("id", "?"), n.get("author", "?"), status, tag, addr, quote))
        for e in n.get("thread", []):
            body = (e.get("body") or "").strip()
            if body:
                lines.append("  %s: %s" % (e.get("author", "?"), body))
        if context and span:
            src_lines = source.splitlines()
            first = source.count("\n", 0, span[0]) + 1
            last = source.count("\n", 0, max(span[0], span[1] - 1)) + 1
            lo, hi = max(1, first - context), min(len(src_lines), last + context)
            for ln in range(lo, hi + 1):
                lines.append("    %d: %s" % (ln, src_lines[ln - 1]))
        lines.append("")
    scope = "" if include_resolved else " unresolved"
    header = "%d%s note(s) of %d total" % (shown, scope, len(notes))
    return (header + "\n\n" + "\n".join(lines)).rstrip()

if __name__ == "__main__":
    flags = [a for a in sys.argv[1:] if a.startswith("-")]
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if len(args) != 1:
        print("usage: distill.py [--all] [--context N] <doc-view.html>", file=sys.stderr); sys.exit(2)
    context = 0
    for f in flags:
        if f.startswith("--context="):
            context = int(f.split("=", 1)[1])
    with open(args[0], encoding="utf-8") as f:
        html = f.read()
    data = extract_notes(html)
    snapshot = extract_source(html)
    doc_name = extract_doc_name(html)
    override = None
    for f in flags:
        if f.startswith("--source="):
            override = f.split("=", 1)[1]
    src_path = find_current_source(args[0], html, override)
    current = None
    if src_path is not None:
        current = pathlib.Path(src_path).read_text(encoding="utf-8")
    out = digest(data, include_resolved="--all" in flags, source=snapshot,
                 doc_name=doc_name, context=context, current_source=current)
    if snapshot is not None:
        out = staleness(snapshot, current) + "\n" + out
    print(out)
