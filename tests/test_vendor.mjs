import { test } from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';

// marked.min.js is a UMD bundle; eval it in a fake module-less scope so it
// attaches `marked` to globalThis.
const src = readFileSync(new URL('../vendor/marked.min.js', import.meta.url), 'utf8');
(0, eval)(src);

test('marked renders a heading and bold', () => {
  const html = globalThis.marked.parse('# Hi\n\nsome **bold** text');
  assert.match(html, /<h1[^>]*>Hi<\/h1>/);
  assert.match(html, /<strong>bold<\/strong>/);
});

const require = createRequire(import.meta.url);
const katex = require('../vendor/katex/katex.min.js');

test('vendored KaTeX renders accessible inline math', () => {
  const html = katex.renderToString('x(t) = \\frac{a}{b}', { output: 'htmlAndMathml' });
  assert.match(html, /class="katex"/);
  assert.match(html, /class="katex-mathml"/);
});
