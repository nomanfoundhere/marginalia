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
    # the 6 real script elements: theme-init, source, notes, marked, core, boot
    assert html.count("</script>") == 6

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


def test_artifact_has_no_external_resource_references(tmp_path):
    # The offline guarantee, checked by test rather than inspection: the
    # assembled artifact fetches nothing at runtime. We scope the check to the
    # template's own markup by stripping the base64 source/notes payloads, whose
    # arbitrary document text must not trip the assertions.
    doc = tmp_path / "plan.md"
    doc.write_text("# See https://example.com\n\n<link> and url(http://x) in prose", encoding="utf-8")
    html = pathlib.Path(build_view.build(str(doc), str(BASE))).read_text(encoding="utf-8")
    markup = SOURCE_RE.sub("SRC", NOTES_RE.sub("NOTES", html))
    assert not re.search(r'<link\b', markup)                       # no stylesheet/font links
    assert "@import" not in markup                                  # no css imports
    assert "@font-face" not in markup                              # platform fonts only
    assert not re.search(r'url\(\s*["\']?https?:', markup)         # no remote url() in css
    assert not re.search(r'(?:src|href)\s*=\s*["\']https?:', markup)  # no remote src/href


def test_theme_init_script_present(tmp_path):
    doc = tmp_path / "plan.md"
    doc.write_text("# Title", encoding="utf-8")
    html = pathlib.Path(build_view.build(str(doc), str(BASE))).read_text(encoding="utf-8")
    head = html[: html.index("</head>")]
    # the pre-paint theme init lives in <head> and reads storage + the OS pref
    assert "data-theme" in head
    assert "mn-theme" in head
    assert "prefers-color-scheme" in head
