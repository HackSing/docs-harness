#!/usr/bin/env node
// Regenerate vendor/harness/managed-entry.md — the governance rules text the
// host injects when a project's own AGENTS.md cannot be read.
//
// The text lives inside vendor/harness/scripts/harness.py as Python string
// constants with two interpolation points (VERSION) and one directory-
// conditional branch (.qoder/repowiki). Hand-transcribing it would drift on
// the first upstream edit, so this script runs the vendored engine against a
// throwaway project and lifts the managed block out of the AGENTS.md it wrote.
// The result is committed, so building the package needs no Python.
import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { MANAGED_BEGIN, MANAGED_END, readManagedBlock } from '../src/host/managed-block.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = path.join(HERE, '..');
const SEED_ROOT = path.join(PROJECT_ROOT, 'vendor', 'harness');
const OUTPUT = path.join(SEED_ROOT, 'managed-entry.md');

/**
 * Run the vendored engine's `project init` against a throwaway git repository.
 * @param {string} python - interpreter command.
 * @returns {string} the temporary project directory (caller removes it).
 */
function seedThrowawayProject(python) {
  const target = fs.mkdtempSync(path.join(os.tmpdir(), 'docs-harness-seed-'));
  // `project init` refuses when git ignores an install path, so the throwaway
  // needs to be a repository with no ignore rules rather than a bare directory.
  execFileSync('git', ['init', '--quiet'], { cwd: target, stdio: 'inherit' });
  // Exit 3 means "written, but not committed yet" — expected for a throwaway.
  const run = spawnSync(
    python,
    [path.join(SEED_ROOT, 'scripts', 'harness.py'), 'project', 'init', '--json', '--target', target],
    { encoding: 'utf8' },
  );
  if (run.status !== 0 && run.status !== 3) {
    throw new Error(`project init failed (exit ${String(run.status)}): ${run.stdout ?? ''}${run.stderr ?? ''}`);
  }
  return target;
}

function main() {
  const python = process.env.DOCS_HARNESS_PYTHON ?? 'python';
  const target = seedThrowawayProject(python);
  try {
    const agents = fs.readFileSync(path.join(target, 'AGENTS.md'), 'utf8');
    const block = readManagedBlock(agents);
    if (block === undefined) throw new Error('seeded AGENTS.md carries no managed block');
    fs.writeFileSync(OUTPUT, `${MANAGED_BEGIN}\n${block}\n${MANAGED_END}\n`, 'utf8');
    console.log(`[extract-managed-block] wrote ${OUTPUT} (${block.length} chars)`);
  } finally {
    fs.rmSync(target, { recursive: true, force: true });
  }
}

main();
