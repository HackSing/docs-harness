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

/** Engine modules `vendor/harness/scripts/harness.py` imports at runtime. */
const ENGINE_SCRIPTS = [
  'harness.py',
  'managed_assets.py',
  'asset_checks.py',
  'plan_governance.py',
  'knowledge_assets.py',
  'acceptance_assets.py',
  'adr_assets.py',
];

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
  assertParentEngine(path.join(PARENT_ROOT, 'scripts', 'harness.py'));
  fs.rmSync(SEED_ROOT, { recursive: true, force: true });

  const scriptsOut = path.join(SEED_ROOT, 'scripts');
  fs.mkdirSync(scriptsOut, { recursive: true });
  for (const name of ENGINE_SCRIPTS) {
    fs.copyFileSync(path.join(PARENT_ROOT, 'scripts', name), path.join(scriptsOut, name));
  }
  fs.cpSync(path.join(PARENT_ROOT, 'scripts', 'githooks'), path.join(scriptsOut, 'githooks'), { recursive: true });
  fs.cpSync(path.join(PARENT_ROOT, 'plan-templates'), path.join(SEED_ROOT, 'plan-templates'), { recursive: true });

  console.log(`[seed-vendor] materialized ${SEED_ROOT} from ${PARENT_ROOT}`);
}

main();
