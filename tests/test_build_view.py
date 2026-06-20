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
    # margin-core.js carries a literal </script> (NOTES_CLOSE); inlining must
    # neutralize it so the HTML parser does not close the script block early.
    assert "<\\/script>" in html
    assert html.count("</script>") == 5  # exactly the 5 real script elements

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
