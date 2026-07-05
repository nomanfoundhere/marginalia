import importlib.util, json, pathlib

BASE = pathlib.Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("margin_anchor", BASE / "margin_anchor.py")
margin_anchor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(margin_anchor)

CASES = json.loads((BASE / "tests" / "fixtures" / "anchor_cases.json").read_text())

def test_locate_anchor_matches_fixtures():
    for c in CASES:
        got = margin_anchor.locate_anchor(c["text"], c["anchor"])
        assert got == c["expected"], "%s: got %d want %d" % (c["name"], got, c["expected"])
