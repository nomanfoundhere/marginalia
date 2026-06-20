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
