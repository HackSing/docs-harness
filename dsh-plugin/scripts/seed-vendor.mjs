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
 * Engine modules `vendor/harness/scripts/harness.py` imports at runtime: every
 * `*.py` next to it. Read from the parent rather than listed here — a
 * hand-kept list silently rots the moment the engine grows a module (2.11.0's
 * `structure_check.py` was missed exactly that way, and every seed after it
 * died on ModuleNotFoundError), and the engine's own scripts directory is the
 * only place that knows what the engine is made of. Engine modules are not
 * Python-only: 2.15.0's `structure_ts_functions.cjs` is a managed module too,
 * and a `.py`-only filter fails `validate_project_source` on the seed.
 * @param {string} scriptsDir - the parent engine's scripts directory.
 * @returns {string[]} the module filenames to copy.
 */
function engineScripts(scriptsDir) {
  return fs.readdirSync(scriptsDir).filter(name => name.endsWith('.py') || name.endsWith('.cjs'));
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
  assertParentEngine(path.join(parentScripts, 'harness.py'));
  fs.rmSync(SEED_ROOT, { recursive: true, force: true });

  const scriptsOut = path.join(SEED_ROOT, 'scripts');
  fs.mkdirSync(scriptsOut, { recursive: true });
  for (const name of engineScripts(parentScripts)) {
    fs.copyFileSync(path.join(parentScripts, name), path.join(scriptsOut, name));
  }
  fs.cpSync(path.join(parentScripts, 'githooks'), path.join(scriptsOut, 'githooks'), { recursive: true });
  fs.cpSync(path.join(PARENT_ROOT, 'plan-templates'), path.join(SEED_ROOT, 'plan-templates'), { recursive: true });

  console.log(`[seed-vendor] materialized ${SEED_ROOT} from ${PARENT_ROOT}`);
}

main();
