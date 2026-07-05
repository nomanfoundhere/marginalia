"""Anchor location shared by distill.py and build-view.py.

locate_anchor is a port of MarginCore.locateAnchor (margin-core.js); the two
must stay in lockstep — tests/fixtures/anchor_cases.json is run against both.
"""

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
