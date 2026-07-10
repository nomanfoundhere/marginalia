import base64
import importlib.util
import json
import pathlib

BASE = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("record_receipts", BASE / "record-receipts.py")
record_receipts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(record_receipts)

def _view(notes, source="# Plan\n\nText\n"):
    source_b64 = base64.b64encode(source.encode()).decode()
    notes_b64 = base64.b64encode(json.dumps({"schemaVersion": 2, "notes": notes}).encode()).decode()
    return ('<title>Margin Notes — plan.md</title>'
            '<script id="margin-source" type="text/plain">' + source_b64 + '</script>'
            '<script id="margin-notes" type="text/plain">' + notes_b64 + '</script>')

def test_receipt_is_added_without_resolving_the_note(tmp_path):
    note = {"id": "n1", "resolved": False, "anchor": {}, "thread": []}
    view = tmp_path / "plan-view.html"
    view.write_text(_view([note]))
    count = record_receipts.record_receipts(str(view), [{"noteId": "n1", "outcome": "applied",
                                                         "reason": "Added the condition."}], author="Codex")
    data = record_receipts.distill.extract_notes(view.read_text())
    receipt = data["notes"][0]["receipts"][0]
    assert count == 1
    assert receipt["author"] == "Codex"
    assert receipt["outcome"] == "applied"
    assert not data["notes"][0]["resolved"]

def test_receipt_rejects_unknown_note_and_bad_outcome(tmp_path):
    view = tmp_path / "plan-view.html"
    view.write_text(_view([{"id": "n1", "anchor": {}, "thread": []}]))
    for payload in ([{"noteId": "missing", "outcome": "applied", "reason": "x"}],
                    [{"noteId": "n1", "outcome": "done", "reason": "x"}]):
        try:
            record_receipts.record_receipts(str(view), payload)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid receipt should fail")
