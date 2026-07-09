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

def test_digest_omits_draft_thread_entries():
    notes = [{"id": "n1", "author": "Aeva", "resolved": False,
              "anchor": {"quote": "full timeline"},
              "thread": [{"author": "Aeva", "body": "half written", "draft": True},
                         {"author": "Aeva", "body": "posted"}]}]
    out = distill.digest(distill.extract_notes(_html(notes)))
    assert "posted" in out
    assert "half written" not in out

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
    assert "## Important" in out
    assert "open · important" in out

def test_digest_groups_semantic_mark_feedback():
    notes = [
        {"id": "n1", "author": "Aeva", "resolved": False, "kind": "highlight",
         "color": "pink", "anchor": {"quote": "twikit"}, "thread": []},
        {"id": "n2", "author": "Aeva", "resolved": False, "kind": "comment",
         "anchor": {"quote": "full timeline"}, "thread": [{"author": "Aeva", "body": "expand"}]},
        {"id": "n3", "author": "Aeva", "resolved": False, "kind": "highlight",
         "color": "green", "anchor": {"quote": "pull"}, "thread": []},
    ]
    html = _html_full(notes)
    out = distill.digest(distill.extract_notes(html),
                         source=distill.extract_source(html),
                         doc_name=distill.extract_doc_name(html))
    assert out.index("## Critical") < out.index("## Important") < out.index("## Refinements")
    assert "open · critical" in out
    assert "open · refinement" in out

def test_digest_groups_deletions_separately():
    notes = [
        {"id": "n1", "author": "Aeva", "resolved": False, "kind": "strike",
         "anchor": {"quote": "twikit"}, "thread": []},
        {"id": "n2", "author": "Aeva", "resolved": False, "kind": "comment",
         "priority": "critical", "anchor": {"quote": "full timeline"}, "thread": []},
    ]
    out = distill.digest(distill.extract_notes(_html_full(notes)), source=SRC_MD, doc_name="plan.md")
    assert out.index("## Critical") < out.index("## Deletions")
    assert "open · delete" in out

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
    item = [line for line in out.splitlines() if line.startswith("[n1")][0]
    assert "full timeline" in out and ":" not in item.split("]")[1].split('"')[0]

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

def test_find_current_source_reads_sibling(tmp_path):
    (tmp_path / "plan.md").write_text(SRC_MD)
    view = tmp_path / "plan-view.html"
    view.write_text(_html_full([]))
    assert distill.find_current_source(str(view), view.read_text()) == str(tmp_path / "plan.md")

def test_find_current_source_skips_fallback_name(tmp_path):
    (tmp_path / "source").write_text("decoy")
    view = tmp_path / "plan-view.html"
    view.write_text(_html_full([]).replace('<title>Margin Notes — plan.md</title>', ''))
    assert distill.find_current_source(str(view), view.read_text()) is None

def test_find_current_source_override_wins(tmp_path):
    other = tmp_path / "elsewhere.md"
    other.write_text(SRC_MD)
    view = tmp_path / "plan-view.html"
    view.write_text(_html_full([]))
    assert distill.find_current_source(str(view), view.read_text(), str(other)) == str(other)

def test_find_current_source_rejects_empty_override(tmp_path):
    view = tmp_path / "plan-view.html"
    view.write_text(_html_full([]))
    assert distill.find_current_source(str(view), view.read_text(), "") is None

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

def test_revision_packet_carries_operation_priority_and_anchor():
    notes = [
        {"id": "n1", "author": "Aeva", "resolved": False, "kind": "comment",
         "priority": "critical", "anchor": {"quote": "full timeline", "prefix": "the ", "suffix": "."},
         "thread": [{"author": "Aeva", "body": "Be specific"}]},
        {"id": "n2", "author": "Aeva", "resolved": False, "kind": "strike",
         "anchor": {"quote": "twikit"}, "thread": []},
    ]
    packet = distill.revision_packet({"schemaVersion": 2, "notes": notes}, source=SRC_MD,
                                     current_source=SRC_MD, doc_name="plan.md")
    assert packet["document"]["currentSourceStatus"] == "matches-reviewed"
    assert packet["operations"][0]["operation"] == "note"
    assert packet["operations"][0]["priority"] == "critical"
    assert packet["operations"][0]["currentLocation"]["lineRange"] == "3"
    assert packet["operations"][1]["operation"] == "delete"
    assert packet["operations"][1]["priority"] is None

def test_revision_packet_marks_changed_current_span_unlocated():
    notes = [{"id": "n1", "author": "Aeva", "resolved": False, "kind": "comment",
              "priority": "important", "anchor": {"quote": "full timeline"}, "thread": []}]
    packet = distill.revision_packet({"notes": notes}, source=SRC_MD,
                                     current_source=SRC_MD.replace("full timeline", "entire history"))
    assert packet["document"]["currentSourceStatus"] == "diverged"
    assert packet["operations"][0]["spanStatus"] == "unlocated"
