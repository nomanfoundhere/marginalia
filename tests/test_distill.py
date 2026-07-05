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
