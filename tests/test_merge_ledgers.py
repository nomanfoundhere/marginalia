import importlib.util
import base64
import json
import pathlib

BASE = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("merge_ledgers", BASE / "merge-ledgers.py")
merge_ledgers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(merge_ledgers)

def _ledger(notes, sha="same-source"):
    return {"docName": "plan.md", "sourceSha256": sha, "schemaVersion": 2, "notes": notes}

def _note(note_id="n-1", quote="timeline", created="2026-07-09T10:00:00Z", **extra):
    note = {"id": note_id, "author": "Aeva", "kind": "comment", "priority": "important",
            "created": created, "anchor": {"quote": quote}, "thread": [], "resolved": False}
    note.update(extra)
    return note

def test_merge_ledgers_unions_independent_notes():
    merged = merge_ledgers.merge_ledgers([
        _ledger([_note("n-a")]),
        _ledger([_note("n-b", quote="authenticate")]),
    ])
    assert [note["id"] for note in merged["notes"]] == ["n-a", "n-b"]

def test_merge_ledgers_combines_threads_of_same_note():
    left = _note(thread=[{"id": "e-a", "author": "Aeva", "ts": "2026-07-09T10:01:00Z", "body": "Clarify"}])
    right = _note(thread=[{"id": "e-b", "author": "Bob", "ts": "2026-07-09T10:02:00Z", "body": "Agreed"}], priority="critical")
    merged = merge_ledgers.merge_ledgers([_ledger([left]), _ledger([right])])
    note = merged["notes"][0]
    assert [entry["id"] for entry in note["thread"]] == ["e-a", "e-b"]
    assert note["priority"] == "critical"

def test_merge_ledgers_keeps_legacy_id_collision_separate():
    left = _note("n1", quote="timeline", created="2026-07-09T10:00:00Z")
    right = _note("n1", quote="authenticate", created="2026-07-09T10:02:00Z")
    merged = merge_ledgers.merge_ledgers([_ledger([left]), _ledger([right])])
    assert len(merged["notes"]) == 2
    assert merged["notes"][0]["id"] == "n1"
    assert merged["notes"][1]["id"].startswith("n1-merge-")

def test_merge_ledgers_keeps_a_note_open_until_every_copy_resolves():
    left = _note(resolved=True, resolvedAt="2026-07-09T10:03:00Z")
    right = _note(resolved=False)
    merged = merge_ledgers.merge_ledgers([_ledger([left]), _ledger([right])])
    assert merged["notes"][0]["resolved"] is False

def test_merge_ledgers_rejects_different_source_snapshots():
    try:
        merge_ledgers.merge_ledgers([_ledger([]), _ledger([], sha="different-source")])
    except ValueError as error:
        assert "same document" in str(error)
    else:
        raise AssertionError("source mismatch should fail")

def test_apply_ledger_to_matching_view_replaces_only_notes(tmp_path):
    source = "# Plan\n"
    sha = merge_ledgers.hashlib.sha256(source.encode()).hexdigest()
    notes = {"schemaVersion": 2, "notes": [_note("n-a")]}
    html = ('<script id="margin-source" type="text/plain">'
            + base64.b64encode(source.encode()).decode()
            + '</script><script id="margin-notes" type="text/plain">'
            + base64.b64encode(json.dumps({"schemaVersion": 2, "notes": []}).encode()).decode()
            + '</script>')
    view = tmp_path / "plan-view.html"
    view.write_text(html)
    merge_ledgers.apply_ledger_to_view({"sourceSha256": sha, **notes}, str(view))
    payload = merge_ledgers.NOTES_RE.search(view.read_text()).group(2)
    assert json.loads(base64.b64decode(payload))["notes"][0]["id"] == "n-a"

def test_apply_ledger_to_wrong_view_rejects_before_writing(tmp_path):
    source = "# Plan\n"
    html = ('<script id="margin-source" type="text/plain">'
            + base64.b64encode(source.encode()).decode()
            + '</script><script id="margin-notes" type="text/plain"></script>')
    view = tmp_path / "plan-view.html"
    view.write_text(html)
    try:
        merge_ledgers.apply_ledger_to_view({"sourceSha256": "wrong", "notes": []}, str(view))
    except ValueError as error:
        assert "different source" in str(error)
    else:
        raise AssertionError("source mismatch should fail")
    assert view.read_text() == html
