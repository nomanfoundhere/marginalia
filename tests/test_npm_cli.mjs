import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const cli = path.join(root, 'bin', 'marginalia.js');

test('npm CLI exposes help and bakes Markdown with the bundled Python engine', () => {
  const help = spawnSync(process.execPath, [cli, '--help'], { encoding: 'utf8' });
  assert.equal(help.status, 0);
  assert.match(help.stdout, /marginalia build <doc\.md>/);

  const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'marginalia-npm-cli-'));
  try {
    const source = path.join(temp, 'plan.md');
    fs.writeFileSync(source, '# Plan\n\nReview this sentence.\n');
    execFileSync(process.execPath, [cli, 'build', source], { cwd: root, stdio: 'pipe' });
    assert.ok(fs.existsSync(path.join(temp, 'plan-view.html')));
  } finally {
    fs.rmSync(temp, { recursive: true, force: true });
  }
});
