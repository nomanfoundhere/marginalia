#!/usr/bin/env node
'use strict';

const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const commands = {
  build: { script: 'build-view.py', description: 'Bake <doc.md> into <doc>-view.html.' },
  collect: { script: 'distill.py', description: 'Print a digest from <doc>-view.html.' },
  merge: { script: 'merge-ledgers.py', description: 'Merge reviewer sidecars safely.' },
  receipt: { script: 'record-receipts.py', description: 'Record agent revision outcomes.' }
};

function usage() {
  process.stdout.write([
    'Marginalia: portable Markdown review for people and AI agents.',
    '',
    'Usage:',
    '  marginalia build <doc.md>',
    '  marginalia collect [distill options] <doc>-view.html',
    '  marginalia packet [distill options] <doc>-view.html',
    '  marginalia merge <ledger...> --out <merged.notes.json> [--view <doc>-view.html]',
    '  marginalia receipt <doc>-view.html <receipts.json> [--author NAME] [--source <doc>.md]',
    '  marginalia skills [--all|--claude|--codex]',
    '  marginalia demo',
    '',
    'Python 3.10+ is required for the bundled review engine.'
  ].join('\n') + '\n');
}

function resolvePython() {
  const candidates = process.platform === 'win32'
    ? [['py', ['-3']], ['python', []]]
    : [['python3', []], ['python', []]];
  for (const [command, prefix] of candidates) {
    const probe = spawnSync(command, prefix.concat('--version'), { stdio: 'ignore' });
    if (!probe.error && probe.status === 0) return { command, prefix };
  }
  process.stderr.write('Marginalia needs Python 3.10 or newer. Install Python, then run this command again.\n');
  process.exit(1);
}

function run(command, args) {
  const python = resolvePython();
  const result = spawnSync(python.command, python.prefix.concat(path.join(root, command), args), { stdio: 'inherit' });
  if (result.error) {
    process.stderr.write('Marginalia could not start Python: ' + result.error.message + '\n');
    process.exit(1);
  }
  process.exitCode = result.status === null ? 1 : result.status;
}

function runSkills(args) {
  if (process.platform === 'win32') {
    process.stderr.write('marginalia skills requires a POSIX shell. Install the skills from the package directory instead.\n');
    process.exit(1);
  }
  const result = spawnSync('bash', [path.join(root, 'scripts', 'install-agent-skills.sh')].concat(args), { stdio: 'inherit' });
  process.exitCode = result.status === null ? 1 : result.status;
}

const argv = process.argv.slice(2);
const command = argv.shift();

if (!command || command === '--help' || command === '-h' || command === 'help') {
  usage();
} else if (command === 'packet') {
  run('distill.py', ['--packet'].concat(argv));
} else if (command === 'skills') {
  runSkills(argv);
} else if (command === 'demo') {
  run('build-view.py', [path.join(root, 'samples', 'release-demo.md')]);
} else if (commands[command]) {
  run(commands[command].script, argv);
} else {
  process.stderr.write('Unknown Marginalia command: ' + command + '\n\n');
  usage();
  process.exitCode = 2;
}
