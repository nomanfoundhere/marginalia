# Margin Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a zero-server, single-file Markdown annotation tool: the author bakes a `.md` into a self-contained `-view.html`, reviewers highlight spans and attach margin notes in any Chromium browser, and the author pulls the feedback back as a token-cheap digest.

**Architecture:** A placeholder-bearing `template.html` shell carries a bundled Markdown renderer (marked), pure annotation logic (`margin-core.js`), and the note UI. A `build-view.py` script inlines those plus the base64'd source Markdown into `<doc>-view.html`. The viewer renders the doc, lets reviewers create span-anchored notes, and saves them back into the same file in place via the File System Access API (verified working in Helium). Two Claude Code skills wrap the scripts: `/margin-send` (build + open) and `/margin-collect` (distill notes to a digest + act).

**Tech Stack:** Vanilla HTML/CSS/JS (no framework, no npm at runtime), `marked` (vendored single minified file), Python 3 stdlib, Node.js built-in `node:test` for JS unit tests, Claude Code skills (`SKILL.md`).

## Global Constraints

- No build step, no npm, no server in the end-user path. The only assembly is one `build-view.py` call inside `/margin-send`.
- The artifact `<doc>-view.html` is one self-contained file: doc + view + notes.
- The source `<doc>.md` is only ever an input; never edited by the reviewer, never mutated by the viewer.
- Save overwrites `<doc>-view.html` in place via the File System Access API; non-Chromium browsers fall back to a download.
- Source Markdown and notes JSON are stored base64-encoded inside `<script type="text/plain">` blocks with ids `margin-source` and `margin-notes`.
- Reconstruction invariant: save rebuilds the file by swapping only the `margin-notes` block content in the pristine page HTML captured at load; it never serializes the live mutated DOM.
- Anchoring: text-quote selector (exact quote + ~30-char prefix + ~30-char suffix). No character offsets. Ambiguous matches degrade to an unanchored note, never a wrong anchor.
- `/margin-collect` reads only the distilled digest into context, never the raw JSON or the whole doc.
- Skill commands: `/margin-send`, `/margin-collect`. Display name: Margin Notes.
- Project root for all paths below: `marginalia/` (folder name is cosmetic; do not rename mid-build).

---

### Task 1: Project skeleton and vendored renderer

**Files:**
- Create: `marginalia/.gitignore`
- Create: `marginalia/vendor/marked.min.js` (downloaded, pinned)
- Create: `marginalia/tests/test_vendor.mjs`

**Interfaces:**
- Produces: a vendored `marked` available to Node as `globalThis.marked` after eval, and inlined into the template later.

- [ ] **Step 1: Create the folder layout and gitignore**

```bash
cd marginalia
mkdir -p vendor tests skills/margin-send skills/margin-collect
printf '%s\n' '*-view.html' '*.pyc' '__pycache__/' 'marginalia-probe.txt' > .gitignore
```

- [ ] **Step 2: Vendor marked at a pinned version**

```bash
cd marginalia
curl -fsSL https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js -o vendor/marked.min.js
test -s vendor/marked.min.js && echo "vendored $(wc -c < vendor/marked.min.js) bytes"
```
Expected: prints a non-zero byte count (roughly 35000+).

- [ ] **Step 3: Write a test that marked parses Markdown**

`marginalia/tests/test_vendor.mjs`:
```js
import { test } from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';

// marked.min.js is a UMD bundle; eval it in a fake module-less scope so it
// attaches `marked` to globalThis.
const src = readFileSync(new URL('../vendor/marked.min.js', import.meta.url), 'utf8');
(0, eval)(src);

test('marked renders a heading and bold', () => {
  const html = globalThis.marked.parse('# Hi\n\nsome **bold** text');
  assert.match(html, /<h1[^>]*>Hi<\/h1>/);
  assert.match(html, /<strong>bold<\/strong>/);
});
```

- [ ] **Step 4: Run the test**

Run: `cd marginalia && node --test tests/test_vendor.mjs`
Expected: PASS, 1 test.

- [ ] **Step 5: Commit**

```bash
cd marginalia && git add .gitignore vendor/marked.min.js tests/test_vendor.mjs
git commit -m "chore: scaffold margin-notes, vendor marked@12.0.2"
```

---

### Task 2: Anchoring — locate a quoted span

**Files:**
- Create: `marginalia/margin-core.js`
- Create: `marginalia/tests/test_anchor.mjs`

**Interfaces:**
- Produces: `MarginCore.locateAnchor(text, anchor) -> number` where `anchor = {quote, prefix?, suffix?}`. Returns the start index of the chosen occurrence in `text`, or `-1` if absent or ambiguous. Exposed via `module.exports` in Node and `globalThis.MarginCore` in the browser.

- [ ] **Step 1: Write the failing tests**

`marginalia/tests/test_anchor.mjs`:
```js
import { test } from 'node:test';
import assert from 'node:assert';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { locateAnchor } = require('../margin-core.js');

test('unique quote returns its index', () => {
  assert.equal(locateAnchor('alpha beta gamma', { quote: 'beta' }), 6);
});

test('absent quote returns -1', () => {
  assert.equal(locateAnchor('alpha beta', { quote: 'zzz' }), -1);
});

test('repeated quote is disambiguated by prefix/suffix', () => {
  const text = 'the cat sat. the cat ran.';
  const second = text.indexOf('cat', 5);
  assert.equal(locateAnchor(text, { quote: 'cat', prefix: 'sat. the ', suffix: ' ran' }), second);
});

test('all-identical context is ambiguous and returns -1', () => {
  assert.equal(locateAnchor('na na na', { quote: 'na', prefix: '', suffix: '' }), -1);
});

test('partial context still picks a strict winner', () => {
  const text = 'red fox. blue fox.';
  const blue = text.indexOf('fox', 5);
  assert.equal(locateAnchor(text, { quote: 'fox', prefix: 'blue ', suffix: '.' }), blue);
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd marginalia && node --test tests/test_anchor.mjs`
Expected: FAIL — cannot find module `../margin-core.js`.

- [ ] **Step 3: Implement `margin-core.js` with `locateAnchor`**

`marginalia/margin-core.js`:
```js
(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.MarginCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function commonPrefixLen(a, b) {
    var n = Math.min(a.length, b.length), k = 0;
    while (k < n && a.charCodeAt(k) === b.charCodeAt(k)) k++;
    return k;
  }
  function commonSuffixLen(a, b) {
    var n = Math.min(a.length, b.length), k = 0;
    while (k < n && a.charCodeAt(a.length - 1 - k) === b.charCodeAt(b.length - 1 - k)) k++;
    return k;
  }

  // Returns the start index of the best-matching occurrence of anchor.quote in
  // text, or -1 if absent or if no single occurrence is a strict winner.
  function locateAnchor(text, anchor) {
    var quote = anchor && anchor.quote;
    if (!quote) return -1;
    var hits = [], from = 0, i;
    while ((i = text.indexOf(quote, from)) !== -1) { hits.push(i); from = i + 1; }
    if (hits.length === 0) return -1;
    if (hits.length === 1) return hits[0];

    var prefix = anchor.prefix || '', suffix = anchor.suffix || '';
    var bestIdx = -1, bestScore = -1, secondScore = -1;
    for (var h = 0; h < hits.length; h++) {
      var idx = hits[h];
      var before = text.slice(Math.max(0, idx - prefix.length), idx);
      var after = text.slice(idx + quote.length, idx + quote.length + suffix.length);
      var score = commonSuffixLen(before, prefix) + commonPrefixLen(after, suffix);
      if (score > bestScore) { secondScore = bestScore; bestScore = score; bestIdx = idx; }
      else if (score > secondScore) { secondScore = score; }
    }
    return bestScore > secondScore ? bestIdx : -1; // strict winner or ambiguous
  }

  return { locateAnchor: locateAnchor };
});
```

- [ ] **Step 4: Run to verify pass**

Run: `cd marginalia && node --test tests/test_anchor.mjs`
Expected: PASS, 5 tests.

- [ ] **Step 5: Commit**

```bash
cd marginalia && git add margin-core.js tests/test_anchor.mjs
git commit -m "feat: text-quote anchoring with strict-winner disambiguation"
```

---

### Task 3: View reconstruction — swap only the notes block

**Files:**
- Modify: `marginalia/margin-core.js` (add `reconstructView`)
- Create: `marginalia/tests/test_reconstruct.mjs`

**Interfaces:**
- Produces: `MarginCore.reconstructView(pristineHtml, notesPayload) -> string`. Replaces the inner text of `<script id="margin-notes" type="text/plain">…</script>` in `pristineHtml` with `notesPayload` (a base64 string), leaving all else byte-identical. Throws if the block is missing.

- [ ] **Step 1: Write the failing tests**

`marginalia/tests/test_reconstruct.mjs`:
```js
import { test } from 'node:test';
import assert from 'node:assert';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { reconstructView } = require('../margin-core.js');

const SHELL =
  '<!doctype html><html><head></head><body>' +
  '<main id="margin-doc"></main>' +
  '<script id="margin-notes" type="text/plain">AAAA</script>' +
  '</body></html>';

test('swaps only the notes payload', () => {
  const out = reconstructView(SHELL, 'BBBB');
  assert.ok(out.includes('>BBBB<'));
  assert.ok(!out.includes('>AAAA<'));
  assert.ok(out.includes('<main id="margin-doc"></main>'));
});

test('is idempotent under repeated reconstruction', () => {
  const once = reconstructView(SHELL, 'BBBB');
  const twice = reconstructView(once, 'CCCC');
  assert.ok(twice.includes('>CCCC<'));
  assert.ok(!twice.includes('BBBB'));
  assert.equal(twice.match(/id="margin-notes"/g).length, 1);
});

test('throws when the block is absent', () => {
  assert.throws(() => reconstructView('<html></html>', 'X'));
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd marginalia && node --test tests/test_reconstruct.mjs`
Expected: FAIL — `reconstructView is not a function`.

- [ ] **Step 3: Add `reconstructView` to `margin-core.js`**

In `margin-core.js`, inside the factory, before `return { ... }`, add:
```js
  var NOTES_OPEN = '<script id="margin-notes" type="text/plain">';
  var NOTES_CLOSE = '</script>';

  function reconstructView(pristineHtml, notesPayload) {
    var start = pristineHtml.indexOf(NOTES_OPEN);
    if (start === -1) throw new Error('margin-notes block not found');
    var contentStart = start + NOTES_OPEN.length;
    var end = pristineHtml.indexOf(NOTES_CLOSE, contentStart);
    if (end === -1) throw new Error('margin-notes block not closed');
    return pristineHtml.slice(0, contentStart) + notesPayload + pristineHtml.slice(end);
  }
```
And change the return line to:
```js
  return { locateAnchor: locateAnchor, reconstructView: reconstructView };
```

- [ ] **Step 4: Run to verify pass**

Run: `cd marginalia && node --test tests/test_reconstruct.mjs`
Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
cd marginalia && git add margin-core.js tests/test_reconstruct.mjs
git commit -m "feat: idempotent view reconstruction by notes-block swap"
```

---

### Task 4: `build-view.py` — assemble the artifact, carry notes forward

**Files:**
- Create: `marginalia/template.html` (minimal shell; UI added in Tasks 5–7)
- Create: `marginalia/build-view.py`
- Create: `marginalia/tests/test_build_view.py`

**Interfaces:**
- Consumes: `template.html`, `vendor/marked.min.js`, `margin-core.js`.
- Produces: CLI `python3 build-view.py <doc.md>` writes `<doc-stem>-view.html` next to the source and prints its path. Function `build(doc_md_path, base_dir) -> out_path`. Placeholders in template, replaced exactly once each: `/*MARGIN_MARKED*/`, `/*MARGIN_CORE*/`, `<!--MARGIN_DOC_NAME-->`, and the `margin-source` / `margin-notes` block bodies.

- [ ] **Step 1: Create the minimal template shell**

`marginalia/template.html`:
```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Margin Notes — <!--MARGIN_DOC_NAME--></title>
<style>/* UI styles added in Task 5 */</style>
</head>
<body>
<header id="margin-header"></header>
<main id="margin-doc"></main>
<aside id="margin-rail"></aside>

<script id="margin-source" type="text/plain"></script>
<script id="margin-notes" type="text/plain"></script>

<script>/*MARGIN_MARKED*/</script>
<script>/*MARGIN_CORE*/</script>
<script>/* viewer boot added in Task 5 */</script>
</body>
</html>
```

- [ ] **Step 2: Write the failing tests**

`marginalia/tests/test_build_view.py`:
```python
import base64, importlib.util, pathlib, re, sys

BASE = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_view", BASE / "build-view.py")
build_view = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_view)

NOTES_RE = re.compile(
    r'<script id="margin-notes" type="text/plain">(.*?)</script>', re.DOTALL)
SOURCE_RE = re.compile(
    r'<script id="margin-source" type="text/plain">(.*?)</script>', re.DOTALL)

def test_fresh_build_embeds_source_and_empty_notes(tmp_path):
    doc = tmp_path / "plan.md"
    doc.write_text("# Title\n\nbody with </script> and **bold**", encoding="utf-8")
    out = pathlib.Path(build_view.build(str(doc), str(BASE)))
    assert out.name == "plan-view.html"
    html = out.read_text(encoding="utf-8")
    # source decodes back to the exact markdown, including the tricky </script>
    src_b64 = SOURCE_RE.search(html).group(1).strip()
    assert base64.b64decode(src_b64).decode("utf-8") == doc.read_text(encoding="utf-8")
    # notes start as an empty ledger
    notes_b64 = NOTES_RE.search(html).group(1).strip()
    import json
    assert json.loads(base64.b64decode(notes_b64))["notes"] == []
    # renderer and core were inlined
    assert "/*MARGIN_MARKED*/" not in html
    assert "/*MARGIN_CORE*/" not in html

def test_rebuild_carries_existing_notes_forward(tmp_path):
    doc = tmp_path / "plan.md"
    doc.write_text("# v1", encoding="utf-8")
    out = pathlib.Path(build_view.build(str(doc), str(BASE)))
    html = out.read_text(encoding="utf-8")
    sentinel = base64.b64encode(b'{"schemaVersion":1,"notes":[{"id":"n1"}]}').decode()
    html = NOTES_RE.sub(
        '<script id="margin-notes" type="text/plain">' + sentinel + '</script>', html)
    out.write_text(html, encoding="utf-8")
    # edit the source and rebuild
    doc.write_text("# v2 edited", encoding="utf-8")
    build_view.build(str(doc), str(BASE))
    html2 = out.read_text(encoding="utf-8")
    assert NOTES_RE.search(html2).group(1).strip() == sentinel  # ledger preserved
    assert base64.b64decode(SOURCE_RE.search(html2).group(1).strip()).decode() == "# v2 edited"
```

- [ ] **Step 3: Run to verify failure**

Run: `cd marginalia && python3 -m pytest tests/test_build_view.py -q` (or `python3 -m unittest` if pytest absent — see Step 4 note)
Expected: FAIL — no module `build-view` / `build` not defined.

> Note: if `pytest` is not installed, the tests use only `tmp_path`-style fixtures from pytest. Install once with `python3 -m pip install --user pytest`, or rewrite the two functions to create temp dirs via `tempfile` and call them under `if __name__ == "__main__"`. Prefer pytest.

- [ ] **Step 4: Implement `build-view.py`**

`marginalia/build-view.py`:
```python
#!/usr/bin/env python3
"""Assemble <doc>-view.html from template.html + marked + margin-core + source."""
import base64, os, pathlib, re, sys

TEMPLATE = "template.html"
MARKED = "vendor/marked.min.js"
CORE = "margin-core.js"
EMPTY_NOTES = '{"schemaVersion":1,"notes":[]}'

NOTES_RE = re.compile(
    r'(<script id="margin-notes" type="text/plain">)(.*?)(</script>)', re.DOTALL)
SOURCE_RE = re.compile(
    r'(<script id="margin-source" type="text/plain">)(.*?)(</script>)', re.DOTALL)

def _b64(s: str) -> str:
    return base64.b64encode(s.encode("utf-8")).decode("ascii")

def _existing_notes_payload(out_path: pathlib.Path) -> str:
    if out_path.exists():
        m = NOTES_RE.search(out_path.read_text(encoding="utf-8"))
        if m and m.group(2).strip():
            return m.group(2).strip()
    return _b64(EMPTY_NOTES)

def build(doc_md_path: str, base_dir: str) -> str:
    base = pathlib.Path(base_dir)
    template = (base / TEMPLATE).read_text(encoding="utf-8")
    marked = (base / MARKED).read_text(encoding="utf-8")
    core = (base / CORE).read_text(encoding="utf-8")

    doc = pathlib.Path(doc_md_path)
    source_md = doc.read_text(encoding="utf-8")
    out_path = doc.with_name(doc.stem + "-view.html")
    notes_payload = _existing_notes_payload(out_path)

    out = template
    out = out.replace("/*MARGIN_MARKED*/", marked)
    out = out.replace("/*MARGIN_CORE*/", core)
    out = out.replace("<!--MARGIN_DOC_NAME-->", doc.name)
    out = SOURCE_RE.sub(lambda m: m.group(1) + _b64(source_md) + m.group(3), out, count=1)
    out = NOTES_RE.sub(lambda m: m.group(1) + notes_payload + m.group(3), out, count=1)

    out_path.write_text(out, encoding="utf-8")
    return str(out_path)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: build-view.py <doc.md>", file=sys.stderr); sys.exit(2)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    print(build(sys.argv[1], base_dir))
```

- [ ] **Step 5: Run to verify pass**

Run: `cd marginalia && python3 -m pytest tests/test_build_view.py -q`
Expected: PASS, 2 tests.

- [ ] **Step 6: Commit**

```bash
cd marginalia && git add template.html build-view.py tests/test_build_view.py
git commit -m "feat: build-view assembles single-file artifact, carries notes forward"
```

---

### Task 5: Viewer — render, identity, and span→note creation

This task and Tasks 6–7 build the inline viewer script in `template.html`. They are verified manually in Helium because the behaviour is DOM/selection-driven; adding a headless browser harness would violate the no-npm constraint. Each step lists exact click-throughs and expected results.

**Files:**
- Modify: `marginalia/template.html` (fill the `<style>` and the boot `<script>`)
- Create: `marginalia/samples/demo.md` (fixture for manual checks)

**Interfaces:**
- Consumes: `globalThis.marked`, `globalThis.MarginCore`.
- Produces: a running viewer that decodes `margin-source`, renders it into `#margin-doc`, maintains an in-memory `state.notes` array matching the spec data model, and creates a note from a text selection with a stored `{quote, prefix, suffix}` anchor.

- [ ] **Step 1: Create a demo Markdown fixture**

`marginalia/samples/demo.md`:
```markdown
# Phase 2: Scrape the timeline

We authenticate via twikit and pull the full timeline, then dump to tweets.json.

Then we parse each tweet for word-frequency. The cat sat. The cat ran.
```

- [ ] **Step 2: Fill the viewer boot script and styles**

Replace the `<style>…</style>` and the final `<script>/* viewer boot added in Task 5 */</script>` in `template.html` with the following.

`<style>`:
```css
:root { --rail: 340px; }
* { box-sizing: border-box; }
body { margin: 0; font: 16px/1.6 -apple-system, system-ui, sans-serif; color: #1a1a1a; }
#margin-header { position: sticky; top: 0; z-index: 5; display: flex; gap: 1rem;
  align-items: center; padding: .6rem 1rem; background: #111; color: #eee; }
#margin-header .grow { flex: 1; }
#margin-header button, #margin-header select { font: inherit; padding: .3rem .7rem; }
.layout { display: grid; grid-template-columns: minmax(0,1fr) var(--rail); }
#margin-doc { padding: 2rem clamp(1rem, 4vw, 4rem); max-width: 70ch; }
#margin-rail { padding: 1rem; border-left: 1px solid #ddd; }
mark.mn-hl { background: #fff1a8; border-radius: 2px; cursor: pointer; }
.mn-card { border: 1px solid #ddd; border-left: 4px solid #6ea0ff; border-radius: 6px;
  padding: .6rem .7rem; margin-bottom: .8rem; background: #fafafa; }
.mn-card .who { font-weight: 600; font-size: .85rem; }
.mn-add { position: absolute; transform: translateY(-120%); z-index: 10;
  font: inherit; padding: .25rem .6rem; cursor: pointer; }
[hidden] { display: none !important; }
```

`<script>` (viewer boot):
```html
<script>
(function () {
  'use strict';
  var doc = document.getElementById('margin-doc');
  var rail = document.getElementById('margin-rail');

  function b64decode(b64) {
    return new TextDecoder().decode(Uint8Array.from(atob(b64), function (c) { return c.charCodeAt(0); }));
  }
  function readPayload(id, fallback) {
    var el = document.getElementById(id);
    var raw = el ? el.textContent.trim() : '';
    return raw ? JSON.parse.bind(null) && raw : fallback; // raw base64
  }

  // --- state ---
  var sourceMd = b64decode(document.getElementById('margin-source').textContent.trim());
  var notesRaw = document.getElementById('margin-notes').textContent.trim();
  var state = notesRaw ? JSON.parse(b64decode(notesRaw)) : { schemaVersion: 1, notes: [] };
  if (!state.notes) state.notes = [];
  var seq = state.notes.reduce(function (m, n) {
    var k = parseInt(String(n.id).replace(/\D/g, ''), 10); return isNaN(k) ? m : Math.max(m, k);
  }, 0);

  // identity
  var me = localStorage.getItem('mn-reviewer') || '';
  function ensureIdentity() {
    if (!me) { me = (prompt('Your name for this review?') || 'Reviewer').trim(); localStorage.setItem('mn-reviewer', me); }
    return me;
  }

  // --- render markdown ---
  document.body.classList.add('layout-ready');
  document.body.insertAdjacentHTML('afterbegin', ''); // no-op anchor for clarity
  var wrap = document.createElement('div'); wrap.className = 'layout';
  doc.parentNode.insertBefore(wrap, doc);
  wrap.appendChild(doc); wrap.appendChild(rail);
  doc.innerHTML = globalThis.marked.parse(sourceMd);

  // --- flat-text index <-> DOM range over #margin-doc ---
  function textNodes() {
    var w = document.createTreeWalker(doc, NodeFilter.SHOW_TEXT, null);
    var arr = [], n; while ((n = w.nextNode())) arr.push(n); return arr;
  }
  function flatText() { return textNodes().map(function (t) { return t.nodeValue; }).join(''); }
  function rangeFromFlat(start, length) {
    var nodes = textNodes(), acc = 0, range = document.createRange(), set = false;
    for (var i = 0; i < nodes.length; i++) {
      var len = nodes[i].nodeValue.length;
      if (!set && start < acc + len) { range.setStart(nodes[i], start - acc); set = true; }
      if (set && start + length <= acc + len) { range.setEnd(nodes[i], start + length - acc); return range; }
      acc += len;
    }
    return null;
  }
  function flatFromSelection(sel) {
    var nodes = textNodes(), acc = 0, startFlat = -1;
    var r = sel.getRangeAt(0);
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i] === r.startContainer) startFlat = acc + r.startOffset;
      acc += nodes[i].nodeValue.length;
    }
    return { start: startFlat, quote: sel.toString() };
  }

  // --- add-note affordance on selection ---
  var addBtn = document.createElement('button');
  addBtn.className = 'mn-add'; addBtn.textContent = '+ note'; addBtn.hidden = true;
  document.body.appendChild(addBtn);
  var pending = null;

  document.addEventListener('selectionchange', function () {
    var sel = document.getSelection();
    if (!sel || sel.isCollapsed || !doc.contains(sel.anchorNode)) { addBtn.hidden = true; return; }
    var rect = sel.getRangeAt(0).getBoundingClientRect();
    if (!rect.width) { addBtn.hidden = true; return; }
    addBtn.style.left = (window.scrollX + rect.left) + 'px';
    addBtn.style.top = (window.scrollY + rect.top) + 'px';
    addBtn.hidden = false;
  });

  addBtn.addEventListener('mousedown', function (e) {
    e.preventDefault();
    var sel = document.getSelection();
    var flat = flatFromSelection(sel);
    var text = flatText();
    var anchor = {
      quote: flat.quote,
      prefix: text.slice(Math.max(0, flat.start - 30), flat.start),
      suffix: text.slice(flat.start + flat.quote.length, flat.start + flat.quote.length + 30)
    };
    addNote(anchor);
    addBtn.hidden = true; sel.removeAllRanges();
  });

  function addNote(anchor) {
    ensureIdentity();
    var id = 'n' + (++seq);
    var note = { id: id, author: me, color: '#6ea0ff', created: new Date().toISOString(),
      anchor: anchor, thread: [{ author: me, ts: new Date().toISOString(), body: '' }], resolved: false };
    state.notes.push(note);
    paintHighlights(); renderRail(); markDirty();
    var ta = rail.querySelector('[data-edit="' + id + '"]'); if (ta) ta.focus();
  }

  // --- repaint highlights from anchors (Task 6 adds card interaction) ---
  function paintHighlights() {
    doc.querySelectorAll('mark.mn-hl').forEach(function (m) {
      var parent = m.parentNode; while (m.firstChild) parent.insertBefore(m.firstChild, m); parent.removeChild(m);
    });
    doc.normalize();
    var text = flatText();
    state.notes.forEach(function (n) {
      if (n.resolved) return;
      var idx = globalThis.MarginCore.locateAnchor(text, n.anchor);
      n._located = idx;
      if (idx < 0) return;
      var range = rangeFromFlat(idx, n.anchor.quote.length);
      if (!range) return;
      var mk = document.createElement('mark'); mk.className = 'mn-hl'; mk.dataset.note = n.id;
      try { range.surroundContents(mk); } catch (e) { /* spans element boundary: skip paint, note still listed */ }
    });
  }

  // --- minimal rail (expanded in Task 6) ---
  function renderRail() {
    rail.innerHTML = '';
    state.notes.forEach(function (n) {
      var card = document.createElement('div'); card.className = 'mn-card'; card.dataset.note = n.id;
      var first = n.thread[0] || { body: '' };
      card.innerHTML = '<div class="who"></div>';
      card.querySelector('.who').textContent = n.author + (n._located < 0 ? ' · unanchored' : '');
      var ta = document.createElement('textarea'); ta.dataset.edit = n.id; ta.value = first.body; ta.rows = 3; ta.style.width = '100%';
      ta.addEventListener('input', function () { first.body = ta.value; markDirty(); });
      card.appendChild(ta);
      rail.appendChild(card);
    });
  }

  // --- dirty flag (save wired in Task 7) ---
  var dirty = false;
  function markDirty() { dirty = true; document.dispatchEvent(new CustomEvent('mn-dirty')); }

  // expose for Tasks 6–7
  window.MN = { state: state, paintHighlights: paintHighlights, renderRail: renderRail,
    isDirty: function () { return dirty; }, setClean: function () { dirty = false; }, me: function () { return me; } };

  paintHighlights(); renderRail();
})();
</script>
```

> Note: the `readPayload` helper above is unused scaffolding — delete it before commit; the real decode is inline. (Listed so the reviewer is not surprised by its removal.)

- [ ] **Step 3: Build the demo view**

Run: `cd marginalia && python3 build-view.py samples/demo.md && open -a Helium samples/demo-view.html`
Expected: prints `samples/demo-view.html`; Helium opens a rendered document with an `# Phase 2` heading.

- [ ] **Step 4: Manual verification — create a note**

In Helium:
1. The doc renders full-width with a notes rail on the right.
2. Select the words "full timeline". A `+ note` button appears just above the selection.
3. Click it. On first use, a prompt asks your name; enter `Aeva`.
4. "full timeline" highlights yellow; a card appears in the rail with author `Aeva` and a focused empty textarea. Type `too crude`.
Expected: highlight persists, card shows `Aeva`, textarea holds `too crude`. (Saving comes in Task 7; do not reload yet.)

- [ ] **Step 5: Commit**

```bash
cd marginalia && git add template.html samples/demo.md
git commit -m "feat: viewer renders markdown and creates span-anchored notes"
```

---

### Task 6: Viewer — threads, resolve, hide-resolved, highlight↔card linking

**Files:**
- Modify: `marginalia/template.html` (extend rail rendering + header controls)

**Interfaces:**
- Consumes: `window.MN` from Task 5.
- Produces: per-note reply threads, a resolve toggle, a hide-resolved header toggle, and bidirectional scroll between a highlight and its card.

- [ ] **Step 1: Replace `renderRail` with the threaded version**

In the boot script, replace the entire `renderRail` function with:
```js
  var hideResolved = false;
  function renderRail() {
    rail.innerHTML = '';
    state.notes.forEach(function (n) {
      if (n.resolved && hideResolved) return;
      var card = document.createElement('div'); card.className = 'mn-card'; card.dataset.note = n.id;
      card.style.borderLeftColor = n.color || '#6ea0ff';
      if (n.resolved) card.style.opacity = '.55';

      var head = document.createElement('div'); head.className = 'who';
      head.textContent = n.author + (n._located < 0 ? ' · unanchored' : '') + (n.resolved ? ' · resolved' : '');
      card.appendChild(head);

      n.thread.forEach(function (entry, i) {
        if (i === 0) {
          var ta = document.createElement('textarea'); ta.dataset.edit = n.id; ta.value = entry.body; ta.rows = 3; ta.style.width = '100%';
          ta.addEventListener('input', function () { entry.body = ta.value; markDirty(); });
          card.appendChild(ta);
        } else {
          var p = document.createElement('p'); p.style.margin = '.4rem 0';
          p.innerHTML = '<strong></strong>: '; p.querySelector('strong').textContent = entry.author;
          p.appendChild(document.createTextNode(entry.body)); card.appendChild(p);
        }
      });

      var bar = document.createElement('div');
      var reply = document.createElement('button'); reply.textContent = 'reply';
      reply.addEventListener('click', function () {
        ensureIdentity();
        n.thread.push({ author: me, ts: new Date().toISOString(), body: '' });
        renderRail(); markDirty();
      });
      var resolve = document.createElement('button'); resolve.textContent = n.resolved ? 'unresolve' : '✓ resolve';
      resolve.addEventListener('click', function () { n.resolved = !n.resolved; paintHighlights(); renderRail(); markDirty(); });
      var del = document.createElement('button'); del.textContent = 'delete';
      del.addEventListener('click', function () {
        state.notes = state.notes.filter(function (x) { return x !== n; });
        window.MN.state = state; paintHighlights(); renderRail(); markDirty();
      });
      bar.appendChild(reply); bar.appendChild(resolve); bar.appendChild(del);
      card.appendChild(bar);

      card.addEventListener('click', function (e) {
        if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'BUTTON') return;
        var hl = doc.querySelector('mark.mn-hl[data-note="' + n.id + '"]');
        if (hl) hl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
      rail.appendChild(card);
    });
  }
  window.MN.setHideResolved = function (v) { hideResolved = v; renderRail(); };
```

- [ ] **Step 2: Add header controls (hide-resolved) and highlight→card scroll**

After `paintHighlights(); renderRail();` near the end of the boot script, add:
```js
  var header = document.getElementById('margin-header');
  header.innerHTML = '<span class="grow"></span>';
  header.querySelector('.grow').textContent = document.title.replace('Margin Notes — ', '');
  var hr = document.createElement('label'); hr.style.color = '#eee';
  var cb = document.createElement('input'); cb.type = 'checkbox';
  cb.addEventListener('change', function () { window.MN.setHideResolved(cb.checked); });
  hr.appendChild(cb); hr.appendChild(document.createTextNode(' hide resolved'));
  header.appendChild(hr);

  doc.addEventListener('click', function (e) {
    var mk = e.target.closest && e.target.closest('mark.mn-hl');
    if (!mk) return;
    var card = rail.querySelector('.mn-card[data-note="' + mk.dataset.note + '"]');
    if (card) card.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });
```

- [ ] **Step 3: Rebuild and verify manually**

Run: `cd marginalia && python3 build-view.py samples/demo.md && open -a Helium samples/demo-view.html`
In Helium:
1. Create a note on "word-frequency", type `bigrams?`.
2. Click `reply`, type a second line as the same or a new name — it appears as a non-editable line under the first.
3. Click a yellow highlight in the doc — its card scrolls into view.
4. Click a card (not its buttons) — the highlight scrolls into view.
5. Click `✓ resolve` — the highlight disappears and the card greys.
6. Tick `hide resolved` in the header — the resolved card hides; untick — it returns.
Expected: all six behave as described.

- [ ] **Step 4: Commit**

```bash
cd marginalia && git add template.html
git commit -m "feat: threads, resolve, hide-resolved, highlight-card linking"
```

---

### Task 7: Viewer — save (FS Access + fallback), autosave, unsaved guard, ⌘S

**Files:**
- Modify: `marginalia/template.html` (add save subsystem + capture pristine HTML)

**Interfaces:**
- Consumes: `window.MN`, `MarginCore.reconstructView`.
- Produces: a Save button that writes the notes back into the file in place via the File System Access API (download fallback), localStorage autosave keyed to the doc, a beforeunload guard, and a ⌘S accelerator with `preventDefault`.

- [ ] **Step 1: Capture pristine HTML at the very top of the boot script**

As the **first statements** inside the boot IIFE (before any DOM mutation), add:
```js
  var PRISTINE = '<!doctype html>\n' + document.documentElement.outerHTML;
  var DOC_NAME = document.title.replace('Margin Notes — ', '') || 'doc';
  var LS_KEY = 'mn-notes:' + DOC_NAME;
```

- [ ] **Step 2: Hydrate from localStorage if newer, and add the save subsystem**

Immediately after `state` is initialised from the `margin-notes` block, add:
```js
  try {
    var cached = localStorage.getItem(LS_KEY);
    if (cached) { var c = JSON.parse(cached); if (c && c.notes) state = c; }
  } catch (e) {}
```

Then near the end of the boot script (after the header is built), add:
```js
  function b64encode(str) {
    return btoa(String.fromCharCode.apply(null, new TextEncoder().encode(str)));
  }
  function serialize() { return b64encode(JSON.stringify(state)); }

  function autosave() { try { localStorage.setItem(LS_KEY, JSON.stringify(state)); } catch (e) {} }
  document.addEventListener('mn-dirty', autosave);

  var fileHandle = null;
  var saveBtn = document.createElement('button'); saveBtn.textContent = 'Save';
  header.insertBefore(saveBtn, header.querySelector('label'));
  function refreshSaveLabel() { saveBtn.textContent = window.MN.isDirty() ? '● Save' : 'Saved'; }
  document.addEventListener('mn-dirty', refreshSaveLabel);

  async function save() {
    var output = MarginCore.reconstructView(PRISTINE, serialize());
    if (window.showSaveFilePicker) {
      try {
        if (!fileHandle) fileHandle = await showSaveFilePicker({ suggestedName: DOC_NAME.replace(/\.md$/, '') + '-view.html' });
        var w = await fileHandle.createWritable(); await w.write(output); await w.close();
        window.MN.setClean(); refreshSaveLabel(); return;
      } catch (e) { if (e && e.name === 'AbortError') return; /* else fall through to download */ }
    }
    var blob = new Blob([output], { type: 'text/html' });
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = DOC_NAME.replace(/\.md$/, '') + '-view.html'; a.click();
    URL.revokeObjectURL(a.href); window.MN.setClean(); refreshSaveLabel();
  }
  saveBtn.addEventListener('click', save);

  window.addEventListener('keydown', function (e) {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') { e.preventDefault(); save(); }
  });
  window.addEventListener('beforeunload', function (e) {
    if (window.MN.isDirty()) { e.preventDefault(); e.returnValue = ''; }
  });
  refreshSaveLabel();
```

> Note: `state` may be reassigned by the localStorage hydrate and by note deletion. Ensure `serialize()` and the rail always read the current `state`; the delete handler in Task 6 already updates `window.MN.state`. Verify no stale closure over the old `state` remains after hydrate (the hydrate runs before `renderRail()`/`paintHighlights()` are first called, so the initial render uses the hydrated state).

- [ ] **Step 3: Rebuild and verify the full save cycle manually**

Run: `cd marginalia && rm -f samples/demo-view.html && python3 build-view.py samples/demo.md && open -a Helium samples/demo-view.html`
In Helium:
1. Create a note on "twikit", type `auth got 402'd`. The Save button shows `● Save`.
2. Click `Save`. The first time, a picker appears (the verified FS-Access grant) — save over `demo-view.html` in `samples/`. Button flips to `Saved`.
3. Reload the page. The note is still there (loaded from the embedded block), highlight repainted.
4. Edit the note text, do not save, try to close the tab — the browser warns about unsaved changes.
5. Create another note, press ⌘S — it saves silently (no Save-Page-As dialog), button shows `Saved`.
6. Close and reopen `samples/demo-view.html` fresh — all notes present.
Expected: all six behave as described; in particular reload-persistence (3) and ⌘S-not-browser-save (5).

- [ ] **Step 4: Second-reviewer handoff check**

1. Copy `samples/demo-view.html` to `samples/demo-handoff.html`, open it in Helium.
2. It shows the prior notes. Clear the stored name via devtools (`localStorage.removeItem('mn-reviewer')`) and reload, or open in a private window; add a note as a different reviewer `B`.
3. Save, reopen — both reviewers' notes are present, color/author distinguishable.
Expected: the single file accumulates notes across reviewers.

- [ ] **Step 5: Commit**

```bash
cd marginalia && git add template.html
git commit -m "feat: in-place save via FS Access, autosave, unsaved guard, cmd-S"
```

---

### Task 8: `distill.py` — token-cheap digest for `/margin-collect`

**Files:**
- Create: `marginalia/distill.py`
- Create: `marginalia/tests/test_distill.py`

**Interfaces:**
- Produces: CLI `python3 distill.py [--all] <doc-view.html>` prints a compact text digest of unresolved notes (or all with `--all`). Functions `extract_notes(html_text) -> dict` and `digest(data, include_resolved=False) -> str`.

- [ ] **Step 1: Write the failing tests**

`marginalia/tests/test_distill.py`:
```python
import base64, importlib.util, json, pathlib

BASE = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("distill", BASE / "distill.py")
distill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(distill)

def _html(notes):
    payload = base64.b64encode(json.dumps({"schemaVersion": 1, "notes": notes}).encode()).decode()
    return '<script id="margin-notes" type="text/plain">' + payload + '</script>'

DATA = [
    {"id": "n1", "author": "Aeva", "resolved": False,
     "anchor": {"quote": "full timeline"},
     "thread": [{"author": "Aeva", "body": "too crude"}, {"author": "Claude", "body": "fixed"}]},
    {"id": "n2", "author": "Aeva", "resolved": True,
     "anchor": {"quote": "twikit"}, "thread": [{"author": "Aeva", "body": "done"}]},
]

def test_extract_decodes_notes():
    data = distill.extract_notes(_html(DATA))
    assert len(data["notes"]) == 2

def test_digest_hides_resolved_by_default():
    out = distill.digest(distill.extract_notes(_html(DATA)))
    assert "full timeline" in out
    assert "twikit" not in out        # resolved hidden
    assert "too crude" in out and "fixed" in out

def test_digest_all_includes_resolved():
    out = distill.digest(distill.extract_notes(_html(DATA)), include_resolved=True)
    assert "twikit" in out

def test_digest_omits_machine_fields():
    out = distill.digest(distill.extract_notes(_html(DATA)))
    assert "schemaVersion" not in out and "anchor" not in out
```

- [ ] **Step 2: Run to verify failure**

Run: `cd marginalia && python3 -m pytest tests/test_distill.py -q`
Expected: FAIL — no module `distill`.

- [ ] **Step 3: Implement `distill.py`**

`marginalia/distill.py`:
```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `cd marginalia && python3 -m pytest tests/test_distill.py -q`
Expected: PASS, 4 tests.

- [ ] **Step 5: Commit**

```bash
cd marginalia && git add distill.py tests/test_distill.py
git commit -m "feat: distill notes to token-cheap digest, unresolved by default"
```

---

### Task 9: Skills — `/margin-send` and `/margin-collect`

**Files:**
- Create: `marginalia/skills/margin-send/SKILL.md`
- Create: `marginalia/skills/margin-collect/SKILL.md`
- Create: `marginalia/README.md`

**Interfaces:**
- Consumes: `build-view.py`, `distill.py`.
- Produces: two invocable skills wrapping the scripts; a README documenting install (symlink `skills/*` into `~/.claude/skills/`) and the round-trip.

- [ ] **Step 1: Write the `margin-send` skill**

`marginalia/skills/margin-send/SKILL.md`:
```markdown
---
name: margin-send
description: Bake a Markdown file into a self-contained annotation view and open it in Helium for span-level review. Use when the author wants a reviewer to leave precise margin notes on a plan or writeup.
---

# margin-send

Turn `<doc>.md` into `<doc>-view.html` and open it for review.

1. Resolve the project root (the `marginalia/` checkout) and the target `.md` path from the user.
2. Run: `python3 <root>/build-view.py <path-to-doc.md>`
   - This writes `<doc>-view.html` next to the source and prints its path.
   - If a `<doc>-view.html` already exists, its notes are carried forward; the doc content is refreshed from the current `.md`.
3. Open it: `open -a Helium <printed-path>`
4. Tell the user: select text, click "+ note", type, and click Save when a round is done; the file can be passed to other reviewers and accumulates their notes.

Do not edit `<doc>.md` here. This skill only produces and opens the view.
```

- [ ] **Step 2: Write the `margin-collect` skill**

`marginalia/skills/margin-collect/SKILL.md`:
```markdown
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
```

- [ ] **Step 3: Write the README**

`marginalia/README.md`:
```markdown
# Margin Notes

Zero-server, single-file Markdown annotation. Bake a `.md` into a self-contained
`-view.html`, highlight spans and leave margin notes in any Chromium browser
(verified in Helium), save in place, and pull the feedback back as a digest.

## Install the skills
Symlink the two skills into your Claude Code skills directory:

    ln -s "$PWD/skills/margin-send"    ~/.claude/skills/margin-send
    ln -s "$PWD/skills/margin-collect" ~/.claude/skills/margin-collect

## Round-trip
1. `/margin-send plan.md` — builds `plan-view.html`, opens it in Helium.
2. Reviewer selects text → "+ note" → types → Save. Passes the one file on; it
   accumulates each reviewer's notes.
3. `/margin-collect plan-view.html` — distills unresolved notes; the author
   revises `plan.md` and regenerates.

## Tests
    node --test tests/          # JS: anchoring, reconstruction, vendor
    python3 -m pytest tests/    # Python: build-view, distill
```

- [ ] **Step 4: Run the full suite and an end-to-end smoke**

```bash
cd marginalia
node --test tests/
python3 -m pytest tests/ -q
python3 build-view.py samples/demo.md
python3 distill.py samples/demo-view.html   # after annotating+saving once in Helium
```
Expected: JS tests pass; Python tests pass; `distill.py` prints the digest of whatever notes were saved.

- [ ] **Step 5: Commit**

```bash
cd marginalia && git add skills README.md
git commit -m "feat: margin-send and margin-collect skills + README"
```

---

## Self-Review

Spec coverage:
- App-independence, in-place save, single-file ledger → Tasks 4, 7 (FS Access verified in the spec spike).
- Clean round-trip / anchoring with graceful degradation → Task 2 (`locateAnchor` returns -1 on ambiguity; Task 5 lists such notes as `unanchored`).
- Reconstruction invariant (no live-DOM serialization) → Task 7 captures `PRISTINE` before mutation; Task 3 tests idempotency.
- Token-efficiency distill → Task 8; enforced in the `/margin-collect` skill copy → Task 9.
- Save model: physical button + ⌘S intercept + localStorage autosave + beforeunload → Task 7.
- Features (threads, resolve, hide-resolved, identity colour, click-link) → Tasks 5–6. Cut features (search, tags, filter-by-author, export-md, manual colours) intentionally absent.
- base64 payload safety → Tasks 4, 7, 8.

Open risk carried into execution (flag at review): `range.surroundContents` throws when a selection spans element boundaries (e.g. across a `<strong>`); Task 5 catches and skips the paint, leaving the note listed but unpainted. If too many real selections cross boundaries, replace with a range-splitting highlighter in a follow-up — do not paper over by widening the catch.
