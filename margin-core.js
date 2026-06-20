(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  root.MarginCore = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function commonPrefixLen(a, b) {
    var n = Math.min(a.length, b.length), k = 0;
    while (k < n && a.charCodeAt(k) === b.charCodeAt(k)) k++;
    return k;
  }
  function commonSuffixLen(a, b) {
    var n = Math.min(a.length, b.length), k = 0;
    while (k < n && a.charCodeAt(a.length - 1 - k) === b.charCodeAt(b.length - 1 - k)) k++;
    return k;
  }

  // Returns the start index of the best-matching occurrence of anchor.quote in
  // text, or -1 if absent or if no single occurrence is a strict winner.
  function locateAnchor(text, anchor) {
    var quote = anchor && anchor.quote;
    if (!quote) return -1;
    var hits = [], from = 0, i;
    while ((i = text.indexOf(quote, from)) !== -1) { hits.push(i); from = i + 1; }
    if (hits.length === 0) return -1;
    if (hits.length === 1) return hits[0];

    var prefix = anchor.prefix || '', suffix = anchor.suffix || '';
    var bestIdx = -1, bestScore = -1, secondScore = -1;
    for (var h = 0; h < hits.length; h++) {
      var idx = hits[h];
      var before = text.slice(Math.max(0, idx - prefix.length), idx);
      var after = text.slice(idx + quote.length, idx + quote.length + suffix.length);
      var score = commonSuffixLen(before, prefix) + commonPrefixLen(after, suffix);
      if (score > bestScore) { secondScore = bestScore; bestScore = score; bestIdx = idx; }
      else if (score > secondScore) { secondScore = score; }
    }
    return bestScore > secondScore ? bestIdx : -1; // strict winner or ambiguous
  }

  return { locateAnchor: locateAnchor };
});
