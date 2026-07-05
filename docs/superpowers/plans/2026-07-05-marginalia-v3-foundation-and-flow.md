# Marginalia v3 — Foundation and Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the v3 spec (docs/superpowers/specs/2026-07-05-marginalia-v3-foundation-and-flow-design.md): source-anchored digests, sidecar ledger, revision stamping, mark toolbar, drag-to-arm saving, and native prompts removed.

**Architecture:** A new `margin_anchor.py` module ports `locateAnchor` from `margin-core.js` and adds markdown-normalized source mapping; `distill.py` and `build-view.py` both consume it. Viewer changes live entirely in `template.html`'s inline script and CSS. Parity between the JS and Python locate logic is enforced by a shared JSON fixture file run by both test suites.

**Tech Stack:** Python 3 stdlib only. Browser JS in the existing ES5-flavored idiom (`var`, `function`, no build step). Tests: `pytest` and `node --test`.

## Global Constraints

- Viewer fetches nothing at runtime: no CDN, no web fonts, no network.
- No native browser prompts (`alert`/`confirm`/`prompt`) in the viewer — in-page panels only.
- Every UI change must work in both `data-theme="light"` and `data-theme="dark"`.
- Match the template's existing code style: `var`, `function` declarations, no semicolonless lines, comments explain constraints not narration.
- `template.html` line numbers below are as of commit `7e5effe` and drift as tasks land — locate edit sites by the quoted code, not the line number.
- After any `template.html` change, rebuild the demo (`python3 build-view.py samples/demo.md`) and run both suites; the built file must open without console errors.
- Digest output stays token-lean: no decorative framing, one line per fact.

---

## Milestone A — plumbing (Python, viewer untouched)

### Task 1: `margin_anchor.py` — port `locateAnchor` with JS/Python parity fixtures

**Files:**
- Create: `margin_anchor.py`
- Create: `tests/fixtures/anchor_cases.json`
- Create: `tests/test_margin_anchor.py`
- Modify: `tests/test_anchor.mjs` (append parity block)

**Interfaces:**
- Produces: `locate_anchor(text: str, anchor: dict) -> int` — start index of the best-matching occurrence of `anchor["quote"]` in `text`, or `-1`. Must return exactly what `MarginCore.locateAnchor` returns for the same inputs.

- [ ] **Step 1: Write the shared fixture file**

`tests/fixtures/anchor_cases.json`:

```json
[
  {"name": "absent quote",        "text": "aaa bbb ccc", "anchor": {"quote": "zzz"}, "expected": -1},
  {"name": "empty anchor",        "text": "aaa bbb ccc", "anchor": {}, "expected": -1},
  {"name": "single hit",          "text": "aaa bbb ccc", "anchor": {"quote": "bbb"}, "expected": 4},
  {"name": "prefix disambiguates","text": "The cat sat. The cat ran.", "anchor": {"quote": "The cat", "prefix": "sat. ", "suffix": " ran"}, "expected": 13},
  {"name": "suffix disambiguates","text": "x cat y. z cat w.", "anchor": {"quote": "cat", "prefix": "", "suffix": " w"}, "expected": 11},
  {"name": "ambiguous no winner", "text": "ab ab", "anchor": {"quote": "ab", "prefix": "", "suffix": ""}, "expected": -1},
  {"name": "unicode multibyte",   "text": "naïve café naïve bar", "anchor": {"quote": "naïve", "prefix": "café ", "suffix": " bar"}, "expected": 11}
]
```

- [ ] **Step 2: Write the failing Python test**

`tests/test_margin_anchor.py`:

```python
import importlib.util, json, pathlib

BASE = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("margin_anchor", BASE / "margin_anchor.py")
margin_anchor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(margin_anchor)

CASES = json.loads((BASE / "tests" / "fixtures" / "anchor_cases.json").read_text())

def test_locate_anchor_matches_fixtures():
    for c in CASES:
        got = margin_anchor.locate_anchor(c["text"], c["anchor"])
        assert got == c["expected"], "%s: got %d want %d" % (c["name"], got, c["expected"])
```

- [ ] **Step 3: Run to verify it fails**

Run: `python3 -m pytest tests/test_margin_anchor.py -q`
Expected: FAIL (`FileNotFoundError: margin_anchor.py`)

- [ ] **Step 4: Implement `margin_anchor.py`**

A line-for-line port of `locateAnchor` from `margin-core.js:22-41` — same affix scoring, same strict-winner rule:

```python
"""Anchor location shared by distill.py and build-view.py.

locate_anchor is a port of MarginCore.locateAnchor (margin-core.js); the two
must stay in lockstep — tests/fixtures/anchor_cases.json is run against both.
"""

def _common_prefix_len(a: str, b: str) -> int:
    n = min(len(a), len(b)); k = 0
    while k < n and a[k] == b[k]: k += 1
    return k

def _common_suffix_len(a: str, b: str) -> int:
    n = min(len(a), len(b)); k = 0
    while k < n and a[len(a) - 1 - k] == b[len(b) - 1 - k]: k += 1
    return k

def locate_anchor(text: str, anchor: dict) -> int:
    quote = (anchor or {}).get("quote")
    if not quote:
        return -1
    hits, start = [], 0
    while True:
        i = text.find(quote, start)
        if i == -1: break
        hits.append(i); start = i + 1
    if not hits:
        return -1
    if len(hits) == 1:
        return hits[0]
    prefix = anchor.get("prefix", "") or ""
    suffix = anchor.get("suffix", "") or ""
    best_idx, best, second = -1, -1, -1
    for idx in hits:
        before = text[max(0, idx - len(prefix)):idx]
        after = text[idx + len(quote):idx + len(quote) + len(suffix)]
        score = _common_suffix_len(before, prefix) + _common_prefix_len(after, suffix)
        if score > best:
            second = best; best = score; best_idx = idx
        elif score > second:
            second = score
    return best_idx if best > second else -1
```

- [ ] **Step 5: Run Python test to verify it passes**

Run: `python3 -m pytest tests/test_margin_anchor.py -q`
Expected: PASS

- [ ] **Step 6: Append the parity block to the JS test**

At the end of `tests/test_anchor.mjs` (it already imports `node:test`, `assert`, and `MarginCore` — reuse its imports; add `fs`/`path`/`url` imports only if not present):

```js
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const casesPath = join(dirname(fileURLToPath(import.meta.url)), 'fixtures', 'anchor_cases.json');
const parityCases = JSON.parse(readFileSync(casesPath, 'utf8'));

test('locateAnchor matches shared parity fixtures', () => {
  for (const c of parityCases) {
    assert.equal(MarginCore.locateAnchor(c.text, c.anchor), c.expected, c.name);
  }
});
```

- [ ] **Step 7: Run both suites**

Run: `node --test tests/*.mjs && python3 -m pytest tests/ -q`
Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add margin_anchor.py tests/fixtures/anchor_cases.json tests/test_margin_anchor.py tests/test_anchor.mjs
git commit -m "feat: python port of locateAnchor with JS/Py parity fixtures"
```

---

### Task 2: markdown normalization and source location (`margin_anchor.py`)

**Files:**
- Modify: `margin_anchor.py`
- Modify: `tests/test_margin_anchor.py`

**Interfaces:**
- Consumes: `locate_anchor` (Task 1).
- Produces:
  - `normalize_markdown(source: str) -> tuple[str, list[int]]` — normalized text plus `offset_map` where `offset_map[i]` is the raw-source index of normalized char `i`.
  - `locate_in_source(source: str, anchor: dict) -> tuple[int, int] | None` — raw `(start, end)` span of the quote in markdown source, or `None`.
  - `line_range(source: str, start: int, end: int) -> str` — 1-based `"12-15"`, or `"12"` when one line.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_margin_anchor.py`:

```python
SRC = """# Title

We **authenticate** via `twikit` and pull the [full timeline](https://x.com).

Then we parse each tweet. The cat sat. The cat ran.
"""

def test_normalize_strips_syntax_and_maps_back():
    norm, omap = margin_anchor.normalize_markdown(SRC)
    assert "**" not in norm and "`" not in norm and "](" not in norm
    i = norm.find("authenticate")
    assert i != -1
    assert SRC[omap[i]:omap[i] + len("authenticate")] == "authenticate"

def test_locate_in_source_exact():
    span = margin_anchor.locate_in_source(SRC, {"quote": "parse each tweet"})
    assert span is not None
    assert SRC[span[0]:span[1]] == "parse each tweet"

def test_locate_in_source_through_formatting():
    # Rendered text has no ** or backticks or link syntax.
    span = margin_anchor.locate_in_source(
        SRC, {"quote": "authenticate via twikit and pull the full timeline"})
    assert span is not None
    assert SRC[span[0]:span[1]].startswith("authenticate")
    assert SRC[span[0]:span[1]].endswith("timeline")

def test_locate_in_source_ambiguous_uses_affixes():
    span = margin_anchor.locate_in_source(
        SRC, {"quote": "The cat", "prefix": "sat. ", "suffix": " ran"})
    assert span is not None
    assert SRC.index("The cat ran") == span[0]

def test_locate_in_source_missing():
    assert margin_anchor.locate_in_source(SRC, {"quote": "not present"}) is None

def test_line_range():
    start = SRC.index("authenticate")
    assert margin_anchor.line_range(SRC, start, start + 5) == "3"
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_margin_anchor.py -q`
Expected: FAIL (`AttributeError: normalize_markdown`)

- [ ] **Step 3: Implement**

Append to `margin_anchor.py`:

```python
import re

# Inline markdown that the renderer strips: the rendered quote will not contain
# these characters, so the normalized source must not either. Each entry is
# (pattern, replacement-group): the group's text is kept, the rest dropped.
_MD_TOKENS = re.compile(
    r"(!?\[(?P<label>[^\]]*)\]\([^)]*\))"   # [text](url) / ![alt](url) -> text
    r"|(?P<fence>^```[^\n]*$)"              # fence line (dropped whole)
    r"|(?P<head>^#{1,6}[ \t]+)"             # heading marker
    r"|(?P<bold>\*\*|__)"                   # bold delimiters
    r"|(?P<em>[*_])"                        # emphasis delimiters
    r"|(?P<code>`+)",                       # backticks
    re.MULTILINE)

def normalize_markdown(source: str):
    out, omap, pos = [], [], 0
    for m in _MD_TOKENS.finditer(source):
        for k in range(pos, m.start()):
            out.append(source[k]); omap.append(k)
        if m.group("label") is not None:
            label_at = m.start() + m.group(0).index("[" ) + 1
            for j, ch in enumerate(m.group("label")):
                out.append(ch); omap.append(label_at + j)
        pos = m.end()
    for k in range(pos, len(source)):
        out.append(source[k]); omap.append(k)
    return "".join(out), omap

def locate_in_source(source: str, anchor: dict):
    quote = (anchor or {}).get("quote")
    if not quote:
        return None
    idx = locate_anchor(source, anchor)
    if idx >= 0:
        return (idx, idx + len(quote))
    norm, omap = normalize_markdown(source)
    idx = locate_anchor(norm, anchor)
    if idx < 0 or not omap:
        return None
    last = idx + len(quote) - 1
    return (omap[idx], omap[last] + 1)

def line_range(source: str, start: int, end: int) -> str:
    first = source.count("\n", 0, start) + 1
    last = source.count("\n", 0, max(start, end - 1)) + 1
    return str(first) if first == last else "%d-%d" % (first, last)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_margin_anchor.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add margin_anchor.py tests/test_margin_anchor.py
git commit -m "feat: markdown-normalized source location with offset map"
```

---

### Task 3: digest source addresses, kind tags, `--context`

**Files:**
- Modify: `distill.py`
- Modify: `tests/test_distill.py`

**Interfaces:**
- Consumes: `locate_in_source`, `line_range` (Task 2).
- Produces:
  - `extract_source(html_text: str) -> str | None` — decoded baked source, `None` if block missing/corrupt.
  - `extract_doc_name(html_text: str) -> str` — from `<title>Margin Notes — X</title>`, fallback `"source"`.
  - `digest(data, include_resolved=False, source=None, doc_name="source", context=0) -> str`.
  - Digest line format consumed by the collect skill and later tasks:
    `[id · author · status] doc.md:12-15 "quote"` — with ` · kind-color` inside the bracket for `kind != "comment"`, `(unlocated)` in place of the address when mapping fails.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_distill.py` (the `_html` helper exists; add a source-carrying variant):

```python
SRC_MD = "# Plan\n\nWe authenticate via twikit and pull the full timeline.\n"

def _html_full(notes, source=SRC_MD, title="plan.md"):
    npay = base64.b64encode(json.dumps({"schemaVersion": 2, "notes": notes}).encode()).decode()
    spay = base64.b64encode(source.encode()).decode()
    return ('<title>Margin Notes — %s</title>' % title
            + '<script id="margin-source" type="text/plain">' + spay + '</script>'
            + '<script id="margin-notes" type="text/plain">' + npay + '</script>')

def test_digest_emits_source_address():
    notes = [{"id": "n1", "author": "Aeva", "resolved": False,
              "anchor": {"quote": "full timeline"}, "thread": []}]
    html = _html_full(notes)
    out = distill.digest(distill.extract_notes(html),
                         source=distill.extract_source(html),
                         doc_name=distill.extract_doc_name(html))
    assert "plan.md:3" in out

def test_digest_tags_unlocated():
    notes = [{"id": "n1", "author": "Aeva", "resolved": False,
              "anchor": {"quote": "no such text"}, "thread": []}]
    html = _html_full(notes)
    out = distill.digest(distill.extract_notes(html),
                         source=distill.extract_source(html),
                         doc_name=distill.extract_doc_name(html))
    assert "(unlocated)" in out and "no such text" in out

def test_digest_kind_tag_for_marks():
    notes = [{"id": "n2", "author": "Bob", "resolved": False, "kind": "highlight",
              "color": "yellow", "anchor": {"quote": "twikit"}, "thread": []}]
    html = _html_full(notes)
    out = distill.digest(distill.extract_notes(html),
                         source=distill.extract_source(html),
                         doc_name=distill.extract_doc_name(html))
    assert "highlight-yellow" in out

def test_digest_context_lines():
    notes = [{"id": "n1", "author": "Aeva", "resolved": False,
              "anchor": {"quote": "full timeline"}, "thread": []}]
    html = _html_full(notes)
    out = distill.digest(distill.extract_notes(html),
                         source=distill.extract_source(html),
                         doc_name=distill.extract_doc_name(html), context=1)
    assert "3: We authenticate" in out

def test_digest_without_source_unchanged():
    out = distill.digest(distill.extract_notes(_html(DATA)))
    assert "full timeline" in out and ":" not in out.splitlines()[2].split("]")[1].split('"')[0]
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_distill.py -q`
Expected: FAIL (`AttributeError: extract_source`)

- [ ] **Step 3: Implement in `distill.py`**

Add after `NOTES_RE`:

```python
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
```

Replace `digest()` with:

```python
def digest(data: dict, include_resolved: bool = False,
           source: str = None, doc_name: str = "source", context: int = 0) -> str:
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
```

Update `__main__` to wire the new pieces (full replacement of the block):

```python
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
    print(digest(data, include_resolved="--all" in flags,
                 source=extract_source(html), doc_name=extract_doc_name(html),
                 context=context))
```

(`--context=N` form only — one parsing rule, no space-separated variant.)

- [ ] **Step 4: Run all Python tests**

Run: `python3 -m pytest tests/ -q`
Expected: PASS (old digest tests keep passing: `source=None` preserves the old line shape)

- [ ] **Step 5: Commit**

```bash
git add distill.py tests/test_distill.py
git commit -m "feat: digest emits source line addresses, mark kind tags, --context"
```

---

### Task 4: staleness stamp and `--source`

**Files:**
- Modify: `distill.py`
- Modify: `tests/test_distill.py`

**Interfaces:**
- Consumes: `extract_source`, `extract_doc_name`, `locate_in_source`.
- Produces: `staleness(snapshot: str, current: str | None) -> str` header fragment; digest gains `current_source=None` parameter; per-note `(span changed in current source)` tag.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_distill.py`:

```python
def test_staleness_match():
    assert distill.staleness(SRC_MD, SRC_MD) == "source matches the reviewed snapshot"

def test_staleness_diverged_and_missing():
    assert distill.staleness(SRC_MD, SRC_MD + "x") == "source has diverged since review"
    assert "not found" in distill.staleness(SRC_MD, None)

def test_digest_marks_changed_spans_when_diverged():
    notes = [{"id": "n1", "author": "Aeva", "resolved": False,
              "anchor": {"quote": "full timeline"}, "thread": []}]
    html = _html_full(notes)
    current = SRC_MD.replace("full timeline", "entire history")
    out = distill.digest(distill.extract_notes(html),
                         source=distill.extract_source(html),
                         doc_name="plan.md", current_source=current)
    assert "(span changed in current source)" in out
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_distill.py -q`
Expected: FAIL (`AttributeError: staleness`)

- [ ] **Step 3: Implement**

Add to `distill.py`:

```python
def staleness(snapshot: str, current) -> str:
    if current is None:
        return "current source not found alongside view; pass --source"
    if current == snapshot:
        return "source matches the reviewed snapshot"
    return "source has diverged since review"
```

In `digest()`: add parameter `current_source: str = None`; inside the note loop, after computing `addr`, add:

```python
        if current_source is not None and current_source != source and quote:
            if margin_anchor.locate_in_source(current_source, anchor) is None:
                addr += " (span changed in current source)"
```

In `__main__`: resolve the current source and prepend the stamp to the header. After reading `html`:

```python
    snapshot = extract_source(html)
    doc_name = extract_doc_name(html)
    src_path = None
    for f in flags:
        if f.startswith("--source="):
            src_path = f.split("=", 1)[1]
    if src_path is None:
        cand = pathlib.Path(args[0]).resolve().parent / doc_name
        src_path = str(cand) if cand.exists() else None
    current = None
    if src_path and pathlib.Path(src_path).exists():
        current = pathlib.Path(src_path).read_text(encoding="utf-8")
    out = digest(data, include_resolved="--all" in flags, source=snapshot,
                 doc_name=doc_name, context=context, current_source=current)
    if snapshot is not None:
        out = staleness(snapshot, current) + "\n" + out
    print(out)
```

- [ ] **Step 4: Run all Python tests**

Run: `python3 -m pytest tests/ -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add distill.py tests/test_distill.py
git commit -m "feat: staleness stamp and changed-span tags against current source"
```

---

### Task 5: sidecar ledger

**Files:**
- Modify: `distill.py`
- Modify: `tests/test_distill.py`

**Interfaces:**
- Consumes: `extract_notes`, `extract_source`, `extract_doc_name`.
- Produces: `write_sidecar(view_path: str, data: dict, snapshot: str | None, doc_name: str) -> str | None` — writes `<stem>.notes.json` next to the view file, returns the path written or `None` on failure. CLI writes it by default; `--no-sidecar` suppresses.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_distill.py`:

```python
def test_sidecar_written_next_to_view(tmp_path):
    notes = [{"id": "n1", "author": "Aeva", "resolved": False,
              "anchor": {"quote": "full timeline"}, "thread": []}]
    view = tmp_path / "plan-view.html"
    view.write_text(_html_full(notes))
    data = distill.extract_notes(view.read_text())
    p = distill.write_sidecar(str(view), data, SRC_MD, "plan.md")
    side = json.loads(pathlib.Path(p).read_text())
    assert p == str(tmp_path / "plan.notes.json")
    assert side["docName"] == "plan.md"
    assert side["notes"][0]["id"] == "n1"
    assert len(side["sourceSha256"]) == 64
    assert "extractedAt" in side
```

Add `import pathlib` to the test file's imports if missing.

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_distill.py -q`
Expected: FAIL (`AttributeError: write_sidecar`)

- [ ] **Step 3: Implement**

Add to `distill.py` (extend the imports line with `hashlib, datetime`):

```python
def write_sidecar(view_path: str, data: dict, snapshot, doc_name: str):
    """Durable, git-diffable copy of the ledger. Derived output only: the view
    file stays authoritative and this file is regenerated on every collect."""
    out = {
        "docName": doc_name,
        "sourceSha256": hashlib.sha256((snapshot or "").encode("utf-8")).hexdigest(),
        "extractedAt": datetime.datetime.now(datetime.timezone.utc)
                        .isoformat(timespec="seconds"),
        "schemaVersion": data.get("schemaVersion", 1),
        "notes": data.get("notes", []),
    }
    p = pathlib.Path(view_path).resolve().parent / (
        pathlib.Path(doc_name).stem + ".notes.json")
    try:
        p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                     encoding="utf-8")
        return str(p)
    except OSError as e:
        print("sidecar not written: %s" % e, file=sys.stderr)
        return None
```

In `__main__`, before `print(out)`:

```python
    if "--no-sidecar" not in flags:
        write_sidecar(args[0], data, snapshot, doc_name)
```

- [ ] **Step 4: Run all Python tests**

Run: `python3 -m pytest tests/ -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add distill.py tests/test_distill.py
git commit -m "feat: git-friendly sidecar ledger written on every collect"
```

---

### Task 6: revision stamping in `build-view.py`

**Files:**
- Modify: `build-view.py`
- Modify: `tests/test_build_view.py`

**Interfaces:**
- Consumes: `locate_in_source` (Task 2).
- Produces: on rebuild, every carried-forward note gains `srcCheck: "found" | "missing"` (checked against the NEW source) and the payload's `schemaVersion` becomes 2. `EMPTY_NOTES` becomes `{"schemaVersion":2,"notes":[]}`. A payload that fails to decode is carried through byte-identical (the viewer's boot guard owns that case).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_build_view.py` (follow the file's existing import/tmp_path conventions — it already imports `build_view` via `importlib`, `base64`, `json`, `pathlib`):

```python
def _notes_payload(notes, version=1):
    return base64.b64encode(json.dumps(
        {"schemaVersion": version, "notes": notes}).encode()).decode()

def _read_payload(view_path):
    import re
    m = re.search(r'<script id="margin-notes" type="text/plain">(.*?)</script>',
                  view_path.read_text(), re.DOTALL)
    return json.loads(base64.b64decode(m.group(1)).decode())

def test_rebuild_stamps_srccheck(tmp_path):
    doc = tmp_path / "plan.md"
    doc.write_text("alpha bravo charlie\n")
    view = tmp_path / "plan-view.html"
    build_view.build(str(doc), str(BASE))
    notes = [
        {"id": "n1", "author": "A", "anchor": {"quote": "bravo"}, "thread": [], "resolved": False},
        {"id": "n2", "author": "A", "anchor": {"quote": "vanished"}, "thread": [], "resolved": False},
    ]
    html = view.read_text()
    import re
    html = re.sub(r'(<script id="margin-notes" type="text/plain">)(.*?)(</script>)',
                  lambda m: m.group(1) + _notes_payload(notes) + m.group(3), html,
                  count=1, flags=re.DOTALL)
    view.write_text(html)
    build_view.build(str(doc), str(BASE))
    data = _read_payload(view)
    assert data["schemaVersion"] == 2
    by_id = {n["id"]: n for n in data["notes"]}
    assert by_id["n1"]["srcCheck"] == "found"
    assert by_id["n2"]["srcCheck"] == "missing"

def test_corrupt_payload_carried_verbatim(tmp_path):
    doc = tmp_path / "plan.md"
    doc.write_text("alpha\n")
    view = tmp_path / "plan-view.html"
    build_view.build(str(doc), str(BASE))
    html = view.read_text()
    import re
    html = re.sub(r'(<script id="margin-notes" type="text/plain">)(.*?)(</script>)',
                  lambda m: m.group(1) + "!!!corrupt!!!" + m.group(3), html,
                  count=1, flags=re.DOTALL)
    view.write_text(html)
    build_view.build(str(doc), str(BASE))
    assert "!!!corrupt!!!" in view.read_text()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_build_view.py -q`
Expected: FAIL (`KeyError: 'srcCheck'` or schemaVersion assertion)

- [ ] **Step 3: Implement**

In `build-view.py`:

Change `EMPTY_NOTES` to `'{"schemaVersion":2,"notes":[]}'`.

Add imports `json` and the anchor module (same `importlib` pattern as distill; `build-view.py` has a hyphen so it cannot be imported normally — tests already load it via importlib):

```python
import importlib.util, json
_spec = importlib.util.spec_from_file_location(
    "margin_anchor", pathlib.Path(__file__).resolve().parent / "margin_anchor.py")
margin_anchor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(margin_anchor)
```

Add the stamping function:

```python
def _stamp_src_checks(notes_b64: str, new_source: str) -> str:
    """Revision semantics: a carried-forward note whose quote no longer appears
    in the new source is the workflow's most informative signal (its span was
    probably revised in response). Stamp, do not drop. A payload that fails to
    decode is returned untouched — the viewer's boot guard owns corruption."""
    try:
        data = json.loads(base64.b64decode(notes_b64).decode("utf-8"))
        notes = data["notes"]
    except Exception:
        return notes_b64
    for n in notes:
        found = margin_anchor.locate_in_source(new_source, n.get("anchor") or {})
        n["srcCheck"] = "found" if found else "missing"
    data["schemaVersion"] = 2
    return _b64(json.dumps(data, ensure_ascii=False))
```

In `build()`, after `notes_payload = _existing_notes_payload(out_path)` add:

```python
    notes_payload = _stamp_src_checks(notes_payload, source_md)
```

- [ ] **Step 4: Run all tests**

Run: `python3 -m pytest tests/ -q && node --test tests/*.mjs`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add build-view.py tests/test_build_view.py
git commit -m "feat: rebuild stamps srcCheck revision state on carried-forward notes"
```

---

## Milestone B — viewer surface (`template.html`)

Template tasks share a verification recipe instead of unit tests (the boot
script is not importable). After each task:

```bash
python3 build-view.py samples/demo.md
node --check <(python3 - <<'EOF'
import re, sys
html = open('samples/demo-view.html').read()
print(re.findall(r'<script>\n\(function \(\) \{.*?\}\)\(\);\n</script>', html, re.S)[0][8:-9])
EOF
) && node --test tests/*.mjs && python3 -m pytest tests/ -q
```

Expected: `node --check` silent, both suites PASS. Interactive behavior is
verified once, in Task 13's browser checklist.

### Task 7: viewer schema v2 + "text changed" state

**Files:**
- Modify: `template.html` (boot normalization; `renderRail`; CSS)

**Interfaces:**
- Produces: every in-memory note has `kind` (default `"comment"`); `serialize()` emits `schemaVersion: 2`; rail renders `srcCheck === "missing"` cards with a `text changed` badge and dotted border. Later tasks rely on `n.kind` being always present.

- [ ] **Step 1: Normalize on boot**

After the existing `if (!state.notes) state.notes = [];` line add:

```js
  state.schemaVersion = 2;
  // v1 ledgers predate kinds; every reader from here on can rely on n.kind.
  state.notes.forEach(function (n) { if (!n.kind) n.kind = 'comment'; });
```

- [ ] **Step 2: Badge and style for changed spans**

In `renderRail()`, the unanchored badge block reads:

```js
      if (unanchored) { var badge = document.createElement('span'); ... }
```

Replace with:

```js
      var changed = n.srcCheck === 'missing';
      if (unanchored || changed) {
        var badge = document.createElement('span'); badge.className = 'mn-badge';
        badge.textContent = changed ? 'text changed' : 'unanchored';
        head.appendChild(badge);
      }
      if (changed) card.classList.add('changed');
```

And extend the quote condition `if (unanchored && n.anchor && n.anchor.quote)` to `if ((unanchored || changed) && n.anchor && n.anchor.quote)`.

In the CSS, after `.mn-card.unanchored { border-style: dashed; }` add:

```css
.mn-card.changed { border-style: dotted; }
.mn-card.changed .mn-badge { background: var(--accent); }
```

- [ ] **Step 3: Verify (shared recipe) and commit**

```bash
git add template.html
git commit -m "feat: viewer normalizes schema v2 and surfaces text-changed state"
```

---

### Task 8: mark toolbar popover

**Files:**
- Modify: `template.html` (CSS: replace `.mn-add` block; JS: replace addBtn block, extend `createNote`, add `createMark`, extend `paintHighlights`)

**Interfaces:**
- Consumes: `n.kind` always present (Task 7).
- Produces: `createMark(anchor, kind, color)` and `createNote(anchor)`; module-level `var lastColor = 'yellow'` (Task 13 reads it); popover element `tools` with `hideTools()` (Task 13 calls it on Esc); highlight CSS vars `--hl-yellow/green/pink` per theme.

- [ ] **Step 1: CSS**

Add to both theme blocks — light:

```css
  --hl-yellow: #fde68a; --hl-green: #bbf7d0; --hl-pink: #fbcfe8;
```

dark:

```css
  --hl-yellow: #6d5a12; --hl-green: #1c5636; --hl-pink: #6b2a50;
```

Replace the `.mn-add` rule with:

```css
/* selection toolbar */
.mn-tools { position: absolute; z-index: 30; transform: translateY(-120%);
  display: flex; gap: .25rem; align-items: center; padding: .25rem .35rem;
  background: var(--panel); border: 1px solid var(--line-2); border-radius: 10px;
  box-shadow: var(--shadow-btn); }
.mn-tool { font: inherit; font-size: .82rem; line-height: 1; cursor: pointer;
  border: 1px solid transparent; border-radius: 6px; padding: .3rem .45rem;
  background: none; color: var(--ink); }
.mn-tool:hover { border-color: var(--line-2); background: var(--field); }
.mn-tool-dot { width: 16px; height: 16px; padding: 0; border-radius: 50%;
  border: 1px solid var(--line-2); }
mark.mn-hl.hl-yellow { background: var(--hl-yellow); text-decoration: none; }
mark.mn-hl.hl-green  { background: var(--hl-green);  text-decoration: none; }
mark.mn-hl.hl-pink   { background: var(--hl-pink);   text-decoration: none; }
mark.mn-hl.hl-under  { background: transparent; }
mark.mn-hl.hl-strike { background: transparent;
  text-decoration-line: line-through; }
```

- [ ] **Step 2: Replace the add-note affordance JS**

Replace the whole block from `var addBtn = document.createElement('button');` through the end of `addBtn.addEventListener('mousedown', ...)` with:

```js
  // --- selection toolbar: three highlight colors, underline, strike, comment ---
  var lastColor = 'yellow';
  var tools = document.createElement('div');
  tools.className = 'mn-tools'; tools.hidden = true;
  tools.setAttribute('role', 'toolbar'); tools.setAttribute('aria-label', 'Annotate selection');
  document.body.appendChild(tools);
  function hideTools() { tools.hidden = true; }

  function toolBtn(label, aria, cls) {
    var b = document.createElement('button');
    b.className = 'mn-tool' + (cls ? ' ' + cls : '');
    b.innerHTML = label; b.setAttribute('aria-label', aria);
    tools.appendChild(b);
    return b;
  }
  function anchorFromSelection() {
    var sel = document.getSelection();
    var flat = flatFromSelection(sel);
    var text = flatText();
    var anchor = {
      quote: flat.quote,
      prefix: text.slice(Math.max(0, flat.start - 30), flat.start),
      suffix: text.slice(flat.start + flat.quote.length, flat.start + flat.quote.length + 30)
    };
    hideTools(); sel.removeAllRanges();
    return anchor;
  }
  function wireTool(btn, fn) {
    btn.addEventListener('mousedown', function (e) {
      e.preventDefault();
      var anchor = anchorFromSelection();
      requireIdentity(function () { fn(anchor); });
    });
  }
  ['yellow', 'green', 'pink'].forEach(function (c) {
    var b = toolBtn('', 'Highlight ' + c, 'mn-tool-dot');
    b.style.background = 'var(--hl-' + c + ')';
    wireTool(b, function (anchor) { lastColor = c; createMark(anchor, 'highlight', c); });
  });
  wireTool(toolBtn('<u>U</u>', 'Underline'), function (anchor) { createMark(anchor, 'underline'); });
  wireTool(toolBtn('<s>S</s>', 'Strike through'), function (anchor) { createMark(anchor, 'strike'); });
  wireTool(toolBtn('+ note', 'Leave a note on the selected text'), createNote);

  document.addEventListener('selectionchange', function () {
    var sel = document.getSelection();
    if (!sel || sel.isCollapsed || !doc.contains(sel.anchorNode)) { hideTools(); return; }
    var rect = sel.getRangeAt(0).getBoundingClientRect();
    if (!rect.width) { hideTools(); return; }
    tools.style.left = (window.scrollX + rect.left) + 'px';
    tools.style.top = (window.scrollY + rect.top) + 'px';
    tools.hidden = false;
  });
```

- [ ] **Step 3: `createMark`, and `kind` on `createNote`**

In `createNote`, add `kind: 'comment',` right after `author: me,`. Below it add:

```js
  function createMark(anchor, kind, color) {
    var note = { id: 'n' + (++seq), author: me, kind: kind,
      created: new Date().toISOString(), anchor: anchor, thread: [], resolved: false };
    if (color) note.color = color;
    state.notes.push(note);
    paintHighlights(); renderRail(); markDirty();
  }
```

- [ ] **Step 4: Kind-aware painting**

In `paintHighlights()`, replace the two style lines

```js
      mk.style.backgroundColor = tintFor(n.author);
      mk.style.textDecorationColor = colorFor(n.author);
```

with:

```js
      if (n.kind === 'highlight') {
        mk.classList.add('hl-' + (n.color || 'yellow'));
      } else if (n.kind === 'underline' || n.kind === 'strike') {
        mk.classList.add(n.kind === 'strike' ? 'hl-strike' : 'hl-under');
        mk.style.textDecorationColor = colorFor(n.author);
      } else {
        mk.style.backgroundColor = tintFor(n.author);
        mk.style.textDecorationColor = colorFor(n.author);
      }
```

- [ ] **Step 5: Verify (shared recipe) and commit**

```bash
git add template.html
git commit -m "feat: selection toolbar with highlight colors, underline, strike"
```

---

### Task 9: rail entries for standalone marks

**Files:**
- Modify: `template.html` (`renderRail`; CSS)

**Interfaces:**
- Consumes: `createMark` notes with empty `thread` (Task 8); `messageRow`, `placeCards` (existing).
- Produces: marks with an empty thread render as compact cards; a 💬 button promotes a mark to a threaded note by pushing its first entry.

- [ ] **Step 1: CSS**

After the `.mn-quote` rule add:

```css
.mn-card.mark { padding: .45rem .6rem; }
.mn-card.mark .mn-quote { margin: 0; }
.mn-kind { width: 12px; height: 12px; border-radius: 3px; flex: none;
  border: 1px solid var(--line-2); }
```

- [ ] **Step 2: Compact rendering in `renderRail`**

Inside the `shown.forEach(function (n) {` loop, the head-building starts at `var head = document.createElement('div');`. Immediately after `card.setAttribute('aria-label', ...)` add:

```js
      var isMark = n.kind !== 'comment' && (!n.thread || !n.thread.length);
      if (isMark) card.classList.add('mark');
```

In the head, right after the `mn-id` span is appended, add:

```js
      if (n.kind !== 'comment') {
        var kd = document.createElement('span'); kd.className = 'mn-kind';
        kd.title = n.kind + (n.color ? ' ' + n.color : '');
        kd.style.background = n.kind === 'highlight'
          ? 'var(--hl-' + (n.color || 'yellow') + ')' : colorFor(n.author);
        head.appendChild(kd);
      }
```

Before `head.appendChild(resolveBtn)` add the promote button:

```js
      if (isMark) {
        var talkBtn = document.createElement('button'); talkBtn.className = 'mn-icon';
        talkBtn.textContent = '💬'; talkBtn.setAttribute('aria-label', 'Comment on this mark');
        talkBtn.addEventListener('click', function () {
          requireIdentity(function () {
            n.thread.push({ author: me, ts: new Date().toISOString(), body: '' });
            renderRail(); markDirty();
            var ta = rail.querySelector('[data-edit="' + n.id + '"]'); if (ta) ta.focus();
          });
        });
        head.appendChild(talkBtn);
      }
```

Change the conversation condition `if (!n.resolved)` to `if (!n.resolved && !isMark)`, and extend the quote display condition so marks always show their span:

```js
      if ((unanchored || changed || isMark) && n.anchor && n.anchor.quote) {
```

with the quote text truncated for marks:

```js
        var qt = n.anchor.quote;
        if (isMark && qt.length > 80) qt = qt.slice(0, 77) + '…';
        q.textContent = '“' + qt + '”';
```

(adjust the existing `q.textContent` line rather than duplicating it).

- [ ] **Step 3: Verify (shared recipe) and commit**

```bash
git add template.html
git commit -m "feat: standalone marks render as compact rail entries with promote"
```

---

### Task 10: drag-to-arm, arm bar, open-picker, real path

**Files:**
- Modify: `template.html` (CSS; save subsystem)

**Interfaces:**
- Consumes: `getStoredHandle`, `storeHandle`, `verifyPermission`, `setSaveState`, `SAVE_NAME` (existing).
- Produces: `armWithHandle(handle)` used by drop, picker, and Task 13's checklist; module-level `fileHandle` now set by arming, not only by save. `showFirstSaveExplainer` copy shows the real path.

- [ ] **Step 1: CSS**

After the `.mn-banner` rule add:

```css
/* save arming bar — the one-time gesture that lets the file write itself */
.mn-armbar { display: flex; gap: .6rem; align-items: center; justify-content: center;
  flex-wrap: wrap; padding: .45rem 1rem; font-size: .82rem; color: var(--ink-2);
  background: var(--field); border-bottom: 1px solid var(--line); }
.mn-armbar code { font-family: ui-monospace, monospace; color: var(--ink);
  background: var(--panel); border: 1px solid var(--line); border-radius: 4px;
  padding: .05em .3em; }
.mn-armbar .mn-btn { font-size: .78rem; padding: .2rem .55rem; }
.mn-armbar.mn-drag { outline: 2px dashed var(--accent); outline-offset: -3px; }
```

- [ ] **Step 2: Arming logic**

In the save subsystem, after `function verifyPermission(...)` add:

```js
  // --- arming: acquiring a writable handle to this very file ---
  var armBar = null;
  function ownPath() {
    try { return decodeURIComponent(location.pathname); } catch (e) { return location.pathname; }
  }
  function removeArmBar() { if (armBar) { armBar.remove(); armBar = null; } }
  function armNotice(msg) {
    if (armBar) { armBar.firstChild.textContent = msg; }
  }
  async function armWithHandle(handle) {
    if (!handle) return false;
    if (handle.name !== SAVE_NAME) {
      armNotice('That is a different file (' + handle.name + '). Drop ' + SAVE_NAME + '.');
      return false;
    }
    if (!(await verifyPermission(handle))) {
      armNotice('Write permission was not granted.');
      return false;
    }
    fileHandle = handle;
    await storeHandle(handle);
    removeArmBar();
    return true;
  }
  async function pickOwnFile() {
    // Open-picker, not save-picker: selecting an existing file this way skips
    // the OS "Replace?" confirm that the save-picker adds.
    var handles = await showOpenFilePicker({
      id: 'mn-view', types: [{ description: 'HTML', accept: { 'text/html': ['.html'] } }]
    });
    return armWithHandle(handles && handles[0]);
  }
  function showArmBar() {
    if (armBar || !window.showOpenFilePicker || location.protocol !== 'file:') return;
    armBar = document.createElement('div'); armBar.className = 'mn-armbar';
    var msg = document.createElement('span');
    msg.appendChild(document.createTextNode('To let this file save itself, drag it from Finder onto this window — it lives at '));
    var c = document.createElement('code'); c.textContent = ownPath();
    msg.appendChild(c); msg.appendChild(document.createTextNode(' — or '));
    armBar.appendChild(msg);
    var pick = document.createElement('button'); pick.className = 'mn-btn';
    pick.textContent = 'choose it once';
    pick.addEventListener('click', function () { pickOwnFile().catch(function () {}); });
    var dismiss = document.createElement('button'); dismiss.className = 'mn-icon';
    dismiss.textContent = '×'; dismiss.setAttribute('aria-label', 'Dismiss');
    dismiss.addEventListener('click', removeArmBar);
    armBar.appendChild(pick); armBar.appendChild(dismiss);
    // Above the sticky header, same slot the corrupt-data banner uses.
    document.body.insertBefore(armBar, header);
  }
  window.addEventListener('dragover', function (e) {
    e.preventDefault();
    if (armBar) armBar.classList.add('mn-drag');
  });
  window.addEventListener('dragleave', function () {
    if (armBar) armBar.classList.remove('mn-drag');
  });
  window.addEventListener('drop', function (e) {
    e.preventDefault();
    if (armBar) armBar.classList.remove('mn-drag');
    var item = e.dataTransfer && e.dataTransfer.items && e.dataTransfer.items[0];
    if (!item || item.kind !== 'file' || !item.getAsFileSystemHandle) return;
    item.getAsFileSystemHandle().then(armWithHandle).catch(function () {});
  });
  // Offer arming up front, not at the first save: silently reuse a stored
  // grant when the browser kept it, otherwise show the bar.
  (function () {
    if (!window.showOpenFilePicker) return;
    getStoredHandle().then(function (stored) {
      if (!stored) { showArmBar(); return; }
      Promise.resolve()
        .then(function () { return stored.queryPermission ? stored.queryPermission({ mode: 'readwrite' }) : 'prompt'; })
        .then(function (p) {
          if (p === 'granted') { fileHandle = stored; }
          else { showArmBar(); }
        })
        .catch(showArmBar);
    });
  })();
```

- [ ] **Step 3: Rewire `save()` and the explainer**

In `save()`, replace the handle-acquisition block:

```js
        if (!fileHandle) {
          var stored = await getStoredHandle();
          if (stored && await verifyPermission(stored)) fileHandle = stored;
        }
        if (!fileHandle) {
          if (!firstSaveExplained) { firstSaveExplained = true; await showFirstSaveExplainer(); }
          fileHandle = await showSaveFilePicker({
            suggestedName: SAVE_NAME, id: 'mn-view',
            types: [{ description: 'HTML', accept: { 'text/html': ['.html'] } }]
          });
          await storeHandle(fileHandle);
        }
```

with:

```js
        if (!fileHandle) {
          var stored = await getStoredHandle();
          if (stored && await verifyPermission(stored) && stored.name === SAVE_NAME) fileHandle = stored;
        }
        if (!fileHandle) {
          if (!firstSaveExplained) { firstSaveExplained = true; await showFirstSaveExplainer(); }
          if (!(await pickOwnFile())) throw { name: 'AbortError' };
        }
```

Also change the outer condition `if (window.showSaveFilePicker)` to `if (window.showOpenFilePicker)`, and in `showFirstSaveExplainer` replace the sentence nodes with path-bearing copy:

```js
      p.appendChild(document.createTextNode('Your browser will ask which file to write. Pick '));
      var codeEl = document.createElement('code'); codeEl.textContent = ownPath();
      p.appendChild(codeEl);
      p.appendChild(document.createTextNode(' — the file you are reading right now. After this once, saving is a single click.'));
```

- [ ] **Step 4: Verify (shared recipe) and commit**

```bash
git add template.html
git commit -m "feat: drag-to-arm save with open-picker fallback and real path shown"
```

---

### Task 11: save-state chip

**Files:**
- Modify: `template.html` (CSS; `setSaveState`; header build)

**Interfaces:**
- Consumes: `setSaveState` call sites (unchanged signatures: `'saved' | 'dirty' | 'saving'`).
- Produces: `stateChip` element, `aria-live="polite"`, next to the Save button.

- [ ] **Step 1: CSS**

After the `.mn-save[data-state="saving"]` rule add:

```css
.mn-state { font-size: .78rem; color: var(--ink-3); white-space: nowrap; }
.mn-state[data-state="dirty"] { color: var(--accent); }
```

- [ ] **Step 2: Chip element and wording**

In the header build section, after `saveBtn = document.createElement('button'); saveBtn.className = 'mn-save';` add:

```js
  var stateChip = document.createElement('span');
  stateChip.className = 'mn-state'; stateChip.setAttribute('aria-live', 'polite');
```

and append it right after `header.appendChild(saveBtn);`:

```js
  header.appendChild(stateChip);
```

`stateChip` must be declared before `setSaveState` runs; declare it with the other header vars (`var idWrap, themeBtn, saveBtn;` becomes `var idWrap, themeBtn, saveBtn, stateChip;`) and assign in the header build.

Replace `setSaveState` with:

```js
  function setSaveState(s) {
    saveBtn.dataset.state = s; stateChip.dataset.state = s;
    saveBtn.textContent = s === 'saving' ? 'Saving…' : 'Save';
    // The wording carries the handoff semantics: localStorage protects THIS
    // machine; only the file write travels with the document.
    var fsa = !!window.showOpenFilePicker;
    stateChip.textContent =
      s === 'saving' ? 'Saving…'
      : s === 'saved' ? 'In file'
      : fsa ? 'Safe on this Mac — not yet in the file'
      : 'Not saved';
    saveBtn.setAttribute('aria-label', s === 'dirty' ? 'Save (unsaved changes)' : (s === 'saving' ? 'Saving' : 'Saved'));
  }
```

- [ ] **Step 3: Verify (shared recipe) and commit**

```bash
git add template.html
git commit -m "feat: aria-live save-state chip with handoff wording"
```

---

### Task 12: native prompts out — undo pill and overwrite panel

**Files:**
- Modify: `template.html` (CSS; delete handler in `renderRail`; `save()`)

**Interfaces:**
- Consumes: delete handler (Task 7's `renderRail` shape), `showFirstSaveExplainer` panel pattern, `notesCorrupt` flag.
- Produces: `showUndoToast(note, index)`; `showOverwritePanel() -> Promise` (resolves to proceed, rejects `{name:'AbortError'}` on cancel).

- [ ] **Step 1: CSS**

After the `.mn-explainer .row` rule add:

```css
/* post-delete undo toast — replaces the native confirm */
.mn-undo { position: fixed; left: 50%; bottom: 1.2rem; transform: translateX(-50%);
  z-index: 50; display: flex; gap: .7rem; align-items: center;
  background: var(--panel); border: 1px solid var(--line-2); border-radius: 10px;
  box-shadow: var(--shadow); padding: .55rem .9rem; font-size: .88rem; }
```

- [ ] **Step 2: Undo toast**

Replace the delete handler body (currently the `confirm(...)` guard plus filter) with:

```js
      delBtn.addEventListener('click', function () {
        var index = state.notes.indexOf(n);
        state.notes = state.notes.filter(function (x) { return x !== n; });
        paintHighlights(); renderRail(); markDirty();
        showUndoToast(n, index);
      });
```

Add near `markDirty` (module scope, so `renderRail` can call it):

```js
  // Delete forgives instead of asking: the note is gone at once, and a short
  // undo window replaces the native confirm the no-prompt decision forbids.
  var undoToast = null, undoTimer = 0;
  function showUndoToast(note, index) {
    if (undoToast) { undoToast.remove(); clearTimeout(undoTimer); }
    var t = document.createElement('div'); t.className = 'mn-undo'; undoToast = t;
    t.setAttribute('role', 'status');
    var label = document.createElement('span');
    label.textContent = 'Note ' + note.id + ' deleted';
    var undo = document.createElement('button'); undo.className = 'mn-btn'; undo.textContent = 'Undo';
    undo.addEventListener('click', function () {
      state.notes.splice(Math.min(index, state.notes.length), 0, note);
      paintHighlights(); renderRail(); markDirty();
      t.remove(); undoToast = null; clearTimeout(undoTimer);
    });
    t.appendChild(label); t.appendChild(undo);
    document.body.appendChild(t);
    undoTimer = setTimeout(function () { t.remove(); undoToast = null; }, 6000);
  }
```

- [ ] **Step 3: Overwrite panel**

Add next to `showFirstSaveExplainer` (same panel class):

```js
  function showOverwritePanel() {
    return new Promise(function (resolve, reject) {
      var panel = document.createElement('div'); panel.className = 'mn-explainer';
      panel.setAttribute('role', 'alertdialog');
      var h = document.createElement('h3'); h.textContent = 'Overwrite unreadable notes?';
      var p = document.createElement('p'); p.style.margin = '0';
      p.textContent = 'The notes already saved in this file could not be read and are not shown here. Saving writes the current notes over them.';
      var row = document.createElement('div'); row.className = 'row';
      var ok = document.createElement('button'); ok.className = 'mn-save'; ok.textContent = 'Overwrite';
      var cancel = document.createElement('button'); cancel.className = 'mn-btn'; cancel.textContent = 'Cancel';
      ok.addEventListener('click', function () { panel.remove(); resolve(); });
      cancel.addEventListener('click', function () { panel.remove(); reject({ name: 'AbortError' }); });
      row.appendChild(ok); row.appendChild(cancel);
      panel.appendChild(h); panel.appendChild(p); panel.appendChild(row);
      document.body.appendChild(panel); cancel.focus();
    });
  }
```

In `save()`, replace the `if (notesCorrupt && !confirm(...)) return;` line with:

```js
    if (notesCorrupt) {
      try { await showOverwritePanel(); }
      catch (e) { setSaveState(window.MN.isDirty() ? 'dirty' : 'saved'); return; }
    }
```

- [ ] **Step 4: Verify (shared recipe), confirm zero native prompts remain, and commit**

Run: `grep -n "confirm(" template.html` — Expected: no matches.

```bash
git add template.html
git commit -m "feat: inline undo and overwrite panel replace native confirms"
```

---

### Task 13: keyboard path

**Files:**
- Modify: `template.html` (keydown wiring near the existing ⌘S handler)

**Interfaces:**
- Consumes: `anchorFromSelection`, `createMark`, `createNote`, `lastColor`, `hideTools` (Task 8).
- Produces: selection-scoped keys `h`, `u`, `s`, `c`; `Escape` dismisses the toolbar.

- [ ] **Step 1: Implement**

After the existing ⌘S `keydown` listener add:

```js
  // Selection-scoped keys: only with a live selection in the document and
  // focus outside any editing surface, so typing in threads is never hijacked.
  window.addEventListener('keydown', function (e) {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === 'Escape') { hideTools(); return; }
    var t = e.target;
    if (t && t.closest && t.closest('textarea, input, [contenteditable]')) return;
    var sel = document.getSelection();
    if (!sel || sel.isCollapsed || !doc.contains(sel.anchorNode)) return;
    var k = e.key.toLowerCase();
    if (k !== 'h' && k !== 'u' && k !== 's' && k !== 'c') return;
    e.preventDefault();
    var anchor = anchorFromSelection();
    requireIdentity(function () {
      if (k === 'h') createMark(anchor, 'highlight', lastColor);
      else if (k === 'u') createMark(anchor, 'underline');
      else if (k === 's') createMark(anchor, 'strike');
      else createNote(anchor);
    });
  });
```

- [ ] **Step 2: Verify (shared recipe) and commit**

```bash
git add template.html
git commit -m "feat: keyboard path for marks and notes on selection"
```

---

### Task 14: docs, skills, browser checklist

**Files:**
- Modify: `README.md`, `skills/margin-send/SKILL.md`, `skills/margin-collect/SKILL.md`, `HANDOFF.md`

**Interfaces:**
- Consumes: digest line format (Task 3), staleness header (Task 4), sidecar (Task 5), all viewer behavior.

- [ ] **Step 1: Update `skills/margin-collect/SKILL.md`**

Replace steps 2–4 with:

```markdown
2. Run: `python3 <root>/distill.py <doc>-view.html`
   - The header states whether the current `.md` still matches the reviewed
     snapshot; treat "diverged" as: verify each span before editing.
   - Each unresolved note prints as `[id · author · status] <doc>.md:LINES "quote"`
     plus thread lines; standalone marks carry their kind (`highlight-yellow`,
     `underline`, `strike`) — wordless flags on the quoted span.
   - A `<doc>.notes.json` sidecar is written next to the view file; commit it
     so review history lands in git. `--no-sidecar` suppresses.
3. Read ONLY that digest. Edit at the printed line addresses; on an
   `(unlocated)` note, re-run with `--context=3` instead of reading the whole file.
4. For each note: revise the source `<doc>.md` at its address.
```

- [ ] **Step 2: Update `skills/margin-send/SKILL.md`**

Extend step 2's carried-forward sentence:

```markdown
   - If a `<doc>-view.html` already exists, its notes are carried forward and
     each is stamped against the new source: notes whose quoted span no longer
     appears show as "text changed" in the viewer — the usual sign the span
     was revised in response.
```

Extend step 4's user message:

```markdown
4. Tell the user: select text, then pick a highlight color, underline, strike,
   or "+ note" (keys: H/U/S/C). To enable in-place saving, drag the file from
   Finder onto its own window once; after that saving is one click.
```

- [ ] **Step 3: Update `README.md`**

In the feature prose (after the threading paragraph), add:

```markdown
Selecting text raises a small toolbar: three highlight colors, underline,
strikethrough, and a note. Bare marks travel to the author as wordless
flags on their exact span; notes carry threads. The collect step prints
each item with its source line address, states whether the `.md` has moved
since the review, and writes a git-friendly `<doc>.notes.json` sidecar so
the conversation survives the view file.
```

Replace the first-save sentence in Browser support ("The first save names the exact file to choose; after that…") with:

```markdown
- **Chromium (Chrome, Edge, Helium, Brave, …):** full in-place save. Arm it
  once by dragging the file onto its own window (or picking it once — the
  bar shows the exact path); after that it is a single click.
```

- [ ] **Step 4: Browser checklist (Helium, capture screenshots per item)**

Rebuild `samples/demo-view.html`, open in Helium, verify each; where input
automation is unavailable, the user drives and the agent captures:

1. Arm bar appears on first open (no stored handle), shows the correct path.
2. Dragging the file onto the window arms saving; bar disappears; Save writes in place.
3. Dropping a *different* file shows the mismatch notice, does not arm.
4. "choose it once" opens the open-picker (no "Replace?" step) and arms.
5. Reload: stored handle silently reused (no bar) or bar reappears — either is a pass; note which.
6. Toolbar renders on selection in both themes; all five tools create their mark kinds; highlight colors legible in dark theme.
7. Compact mark cards in rail; 💬 promotes to a thread.
8. Delete shows undo toast; undo restores the note in place.
9. Corrupt-notes fixture (Task fixtures from scratchpad or regenerate): red banner, then Save raises the in-page Overwrite panel, not a native confirm.
10. Chip wording cycles: In file → Safe on this Mac — not yet in the file → Saving… → In file.
11. Keys H/U/S/C on a selection; Esc hides the toolbar; typing in a thread textarea is untouched.
12. `distill.py` on the annotated demo prints addresses + writes sidecar.

Record outcomes (including item 5's branch) in `HANDOFF.md`, replacing its contents with a short v3 status note.

- [ ] **Step 5: Full suites one last time and commit**

Run: `node --test tests/*.mjs && python3 -m pytest tests/ -q`

```bash
git add README.md skills/ HANDOFF.md
git commit -m "docs: v3 marks, save arming, source-addressed digest, sidecar"
```

---

## Self-review notes

- Spec coverage: P1→Tasks 2–3, P2→Task 4, P3→Task 5, P4→Task 6 (+viewer in 7), S1→Tasks 8–9, S2→Task 10, S3→Task 11, S4→Task 12, S5→Task 13, error handling and docs→14. Schema v2 spread across 6, 7, 8.
- The legacy v1 `color` field (an hsl string set at note creation) collides by name with v2's highlight color names; harmless because every consumer reads `color` only when `kind === "highlight"`, and v1 notes normalize to `kind: "comment"`.
- `showOpenFilePicker` gates the whole FSA path after Task 10; browsers shipping only `showSaveFilePicker` do not exist in practice (the two landed together).
- Handle persistence over `file://` may not survive relaunch in Helium — checklist item 5 records the actual branch; both branches are acceptable behavior.
