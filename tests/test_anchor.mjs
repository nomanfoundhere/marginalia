import { test } from 'node:test';
import assert from 'node:assert';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { locateAnchor } = require('../margin-core.js');

test('unique quote returns its index', () => {
  assert.equal(locateAnchor('alpha beta gamma', { quote: 'beta' }), 6);
});

test('absent quote returns -1', () => {
  assert.equal(locateAnchor('alpha beta', { quote: 'zzz' }), -1);
});

test('repeated quote is disambiguated by prefix/suffix', () => {
  const text = 'the cat sat. the cat ran.';
  const second = text.indexOf('cat', 5);
  assert.equal(locateAnchor(text, { quote: 'cat', prefix: 'sat. the ', suffix: ' ran' }), second);
});

test('all-identical context is ambiguous and returns -1', () => {
  assert.equal(locateAnchor('na na na', { quote: 'na', prefix: '', suffix: '' }), -1);
});

test('partial context still picks a strict winner', () => {
  const text = 'red fox. blue fox.';
  const blue = text.indexOf('fox', 5);
  assert.equal(locateAnchor(text, { quote: 'fox', prefix: 'blue ', suffix: '.' }), blue);
});
