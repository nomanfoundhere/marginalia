import { test } from 'node:test';
import assert from 'node:assert';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { reconstructView } = require('../margin-core.js');

const SHELL =
  '<!doctype html><html><head></head><body>' +
  '<main id="margin-doc"></main>' +
  '<script id="margin-notes" type="text/plain">AAAA</script>' +
  '</body></html>';

test('swaps only the notes payload', () => {
  const out = reconstructView(SHELL, 'BBBB');
  assert.ok(out.includes('>BBBB<'));
  assert.ok(!out.includes('>AAAA<'));
  assert.ok(out.includes('<main id="margin-doc"></main>'));
});

test('is idempotent under repeated reconstruction', () => {
  const once = reconstructView(SHELL, 'BBBB');
  const twice = reconstructView(once, 'CCCC');
  assert.ok(twice.includes('>CCCC<'));
  assert.ok(!twice.includes('BBBB'));
  assert.equal(twice.match(/id="margin-notes"/g).length, 1);
});

test('throws when the block is absent', () => {
  assert.throws(() => reconstructView('<html></html>', 'X'));
});
