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

SRC = """# Title

We **authenticate** via `twikit` and pull the [full timeline](https://x.com).

Then we parse each tweet. The cat sat. The cat ran.
"""

def test_normalize_strips_syntax_and_maps_back():
    norm, omap = margin_anchor.normalize_markdown(SRC)
    assert "**" not in norm and "`" not in norm and "](" not in norm
    i = norm.find("authenticate")
    assert i != -1
    assert SRC[omap[i]:omap[i] + len("authenticate")] == "authenticate"

def test_locate_in_source_exact():
    span = margin_anchor.locate_in_source(SRC, {"quote": "parse each tweet"})
    assert span is not None
    assert SRC[span[0]:span[1]] == "parse each tweet"

def test_locate_in_source_through_formatting():
    # Rendered text has no ** or backticks or link syntax.
    span = margin_anchor.locate_in_source(
        SRC, {"quote": "authenticate via twikit and pull the full timeline"})
    assert span is not None
    assert SRC[span[0]:span[1]].startswith("authenticate")
    assert SRC[span[0]:span[1]].endswith("timeline")

def test_locate_in_source_ambiguous_uses_affixes():
    span = margin_anchor.locate_in_source(
        SRC, {"quote": "The cat", "prefix": "sat. ", "suffix": " ran"})
    assert span is not None
    assert SRC.index("The cat ran") == span[0]

def test_locate_in_source_missing():
    assert margin_anchor.locate_in_source(SRC, {"quote": "not present"}) is None

def test_line_range():
    start = SRC.index("authenticate")
    assert margin_anchor.line_range(SRC, start, start + 5) == "3"
