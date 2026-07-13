import base64, importlib.util, json, pathlib, re, sys

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
    # the 8 real script elements: theme-init, source, notes, marked, KaTeX,
    # auto-render, core, boot
    assert html.count("</script>") == 8
    assert "/*MARGIN_KATEX*/" not in html
    assert "/*MARGIN_KATEX_AUTO_RENDER*/" not in html
    assert "/*MARGIN_KATEX_CSS*/" not in html
    assert "renderMathInElement" in html
    assert "data:font/woff2;base64," in html
    assert "url(fonts/" not in html

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
    # ledger is carried forward and stamped with srcCheck on rebuild
    data = _read_payload(out)
    assert data["schemaVersion"] == 3
    assert len(data["notes"]) == 1
    assert data["notes"][0]["id"] == "n1"
    assert "srcCheck" in data["notes"][0]
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


def _notes_payload(notes, version=1):
    return base64.b64encode(json.dumps(
        {"schemaVersion": version, "notes": notes}).encode()).decode()

def _read_payload(view_path):
    m = NOTES_RE.search(view_path.read_text())
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
    html = re.sub(r'(<script id="margin-notes" type="text/plain">)(.*?)(</script>)',
                  lambda m: m.group(1) + _notes_payload(notes) + m.group(3), html,
                  count=1, flags=re.DOTALL)
    view.write_text(html)
    build_view.build(str(doc), str(BASE))
    data = _read_payload(view)
    assert data["schemaVersion"] == 3
    by_id = {n["id"]: n for n in data["notes"]}
    assert by_id["n1"]["srcCheck"] == "found"
    assert by_id["n2"]["srcCheck"] == "missing"

def test_corrupt_payload_carried_verbatim(tmp_path):
    doc = tmp_path / "plan.md"
    doc.write_text("alpha\n")
    view = tmp_path / "plan-view.html"
    build_view.build(str(doc), str(BASE))
    html = view.read_text()
    html = re.sub(r'(<script id="margin-notes" type="text/plain">)(.*?)(</script>)',
                  lambda m: m.group(1) + "!!!corrupt!!!" + m.group(3), html,
                  count=1, flags=re.DOTALL)
    view.write_text(html)
    build_view.build(str(doc), str(BASE))
    assert "!!!corrupt!!!" in view.read_text()

def test_malformed_notes_shape_carried_verbatim(tmp_path):
    # Valid base64, valid JSON, but "notes" is not a list of dicts: the
    # per-note stamping loop must not be allowed to raise past the guard.
    doc = tmp_path / "plan.md"
    doc.write_text("alpha\n")
    view = tmp_path / "plan-view.html"
    build_view.build(str(doc), str(BASE))
    bad_payload = base64.b64encode(
        json.dumps({"schemaVersion": 1, "notes": "oops"}).encode()).decode()
    html = view.read_text()
    html = re.sub(r'(<script id="margin-notes" type="text/plain">)(.*?)(</script>)',
                  lambda m: m.group(1) + bad_payload + m.group(3), html,
                  count=1, flags=re.DOTALL)
    view.write_text(html)
    build_view.build(str(doc), str(BASE))
    assert NOTES_RE.search(view.read_text()).group(1).strip() == bad_payload
