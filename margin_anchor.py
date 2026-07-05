"""Anchor location shared by distill.py and build-view.py.

locate_anchor is a port of MarginCore.locateAnchor (margin-core.js); the two
must stay in lockstep — tests/fixtures/anchor_cases.json is run against both.
"""

import re

# Inline markdown that the renderer strips: the rendered quote will not contain
# these characters, so the normalized source must not either. Each entry is
# (pattern, replacement-group): the group's text is kept, the rest dropped.
_MD_TOKENS = re.compile(
    r"(!?\[(?P<label>[^\]]*)\]\([^)]*\))"   # [text](url) / ![alt](url) -> text
    r"|(?P<fence>^```[^\n]*$)"              # fence line (dropped whole)
    r"|(?P<head>^#{1,6}[ \t]+)"             # heading marker
    r"|(?P<bold>\*\*|__)"                   # bold delimiters
    r"|(?P<em>[*_])"                        # emphasis delimiters
    r"|(?P<code>`+)",                       # backticks
    re.MULTILINE)

def normalize_markdown(source: str):
    out, omap, pos = [], [], 0
    for m in _MD_TOKENS.finditer(source):
        for k in range(pos, m.start()):
            out.append(source[k]); omap.append(k)
        if m.group("label") is not None:
            label_at = m.start() + m.group(0).index("[" ) + 1
            for j, ch in enumerate(m.group("label")):
                out.append(ch); omap.append(label_at + j)
        pos = m.end()
    for k in range(pos, len(source)):
        out.append(source[k]); omap.append(k)
    return "".join(out), omap

def locate_in_source(source: str, anchor: dict):
    quote = (anchor or {}).get("quote")
    if not quote:
        return None
    idx = locate_anchor(source, anchor)
    if idx >= 0:
        return (idx, idx + len(quote))
    norm, omap = normalize_markdown(source)
    idx = locate_anchor(norm, anchor)
    if idx < 0 or not omap:
        return None
    last = idx + len(quote) - 1
    return (omap[idx], omap[last] + 1)

def line_range(source: str, start: int, end: int) -> str:
    first = source.count("\n", 0, start) + 1
    last = source.count("\n", 0, max(start, end - 1)) + 1
    return str(first) if first == last else "%d-%d" % (first, last)

def _common_prefix_len(a: str, b: str) -> int:
    n = min(len(a), len(b)); k = 0
    while k < n and a[k] == b[k]: k += 1
    return k

def _common_suffix_len(a: str, b: str) -> int:
    n = min(len(a), len(b)); k = 0
    while k < n and a[len(a) - 1 - k] == b[len(b) - 1 - k]: k += 1
    return k

def locate_anchor(text: str, anchor: dict) -> int:
    quote = (anchor or {}).get("quote")
    if not quote:
        return -1
    hits, start = [], 0
    while True:
        i = text.find(quote, start)
        if i == -1: break
        hits.append(i); start = i + 1
    if not hits:
        return -1
    if len(hits) == 1:
        return hits[0]
    prefix = anchor.get("prefix", "") or ""
    suffix = anchor.get("suffix", "") or ""
    best_idx, best, second = -1, -1, -1
    for idx in hits:
        before = text[max(0, idx - len(prefix)):idx]
        after = text[idx + len(quote):idx + len(quote) + len(suffix)]
        score = _common_suffix_len(before, prefix) + _common_prefix_len(after, suffix)
        if score > best:
            second = best; best = score; best_idx = idx
        elif score > second:
            second = score
    return best_idx if best > second else -1
