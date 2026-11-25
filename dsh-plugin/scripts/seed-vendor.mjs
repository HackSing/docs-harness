#!/usr/bin/env node
/**
 * Materialize `vendor/harness/` from the parent docs-harness repo's canonical
 * engine, right before the engine is exercised (tests) or the package is
 * built (prepack). `vendor/harness/` is never hand-maintained or committed —
 * this script is its only writer, so the plugin's installer source can never
 * drift from `../scripts/*.py`.
 *
 * @module dsh-docs-harness/scripts/seed-vendor
 */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PLUGIN_ROOT = path.join(HERE, '..');
const PARENT_ROOT = path.join(PLUGIN_ROOT, '..');
const SEED_ROOT = path.join(PLUGIN_ROOT, 'vendor', 'harness');

/**
 * Parse `MANAGED_MODULE_RELATIVE_FILES` from `../scripts/harness.py` so the
 * vendored seed always stays in lockstep with the engine's own module manifest
 * (including non-Python assets like `structure_ts_functions.cjs` and
 * `agent_prompt.md`), rather than guessing by filename extension.
 * @param {string} harnessPath - absolute path to the parent `scripts/harness.py`.
 * @returns {string[]} filenames under `scripts/` to copy (always including `harness.py`).
 */
function engineScripts(harnessPath) {
  const source = fs.readFileSync(harnessPath, 'utf8');
  const match = source.match(/MANAGED_MODULE_RELATIVE_FILES\s*=\s*\(([\s\S]*?)\)/);
  if (!match) {
    throw new Error(`[seed-vendor] MANAGED_MODULE_RELATIVE_FILES not found in ${harnessPath}`);
  }
  const modules = [...match[1].matchAll(/["']([^"']+)["']/g)].map(entry => entry[1]);
  if (modules.length === 0) {
    throw new Error(`[seed-vendor] MANAGED_MODULE_RELATIVE_FILES is empty in ${harnessPath}`);
  }
  return ['harness.py', ...new Set(modules)];
}

/**
 * @param {string} marker - a file whose absence means the parent is missing.
 */
function assertParentEngine(marker) {
  if (!fs.existsSync(marker)) {
    throw new Error(
      `[seed-vendor] parent engine not found at ${marker} — this package must be built from `
      + 'inside the docs-harness monorepo (docs-harness/dsh-plugin), not as a standalone checkout.',
    );
  }
}

function main() {
  const parentScripts = path.join(PARENT_ROOT, 'scripts');
  const harnessPath = path.join(parentScripts, 'harness.py');
  assertParentEngine(harnessPath);
  fs.rmSync(SEED_ROOT, { recursive: true, force: true });

  const scriptsOut = path.join(SEED_ROOT, 'scripts');
  fs.mkdirSync(scriptsOut, { recursive: true });
  for (const name of engineScripts(harnessPath)) {
    fs.copyFileSync(path.join(parentScripts, name), path.join(scriptsOut, name));
  }
  fs.cpSync(path.join(parentScripts, 'githooks'), path.join(scriptsOut, 'githooks'), { recursive: true });
  fs.cpSync(path.join(PARENT_ROOT, 'plan-templates'), path.join(SEED_ROOT, 'plan-templates'), { recursive: true });

  console.log(`[seed-vendor] materialized ${SEED_ROOT} from ${PARENT_ROOT}`);
}

main();
