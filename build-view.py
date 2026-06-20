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

def _inline_js(js: str) -> str:
    # A JS payload inlined into an HTML <script> block must not carry a raw
    # </script>: the tokenizer would treat it as the element's end tag and close
    # the script early. Escaping the solidus (</script -> <\/script) is a no-op
    # on the JS string value but hides the sequence from the HTML parser.
    return js.replace("</script", "<\\/script")

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
    out = out.replace("/*MARGIN_MARKED*/", _inline_js(marked))
    out = out.replace("/*MARGIN_CORE*/", _inline_js(core))
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
