/**
 * Pre-publish self-check.
 *
 * `npm pack` will happily produce a tarball that installs cleanly and then does
 * nothing: a missing `lib/client.js` leaves the UI half absent, a missing
 * `cordis.patch.yml` leaves the plugin unmounted, and a truncated
 * `vendor/harness` leaves the install action failing on the user's machine. All
 * three are silent at install time, so they are checked here, in `prepack`,
 * where the failure still belongs to whoever is publishing.
 *
 * @module dsh-docs-harness/scripts/verify-package
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { PACKAGE_NAME } from '../src/shared/constants.js';

const ROOT = fileURLToPath(new URL('..', import.meta.url));

/** Files without which the installed package is inert. */
const REQUIRED_FILES = [
  'cordis.patch.yml',
  'lib/client.js',
  'src/host/index.js',
  'src/host/invariant.js',
  'vendor/harness/managed-entry.md',
  'vendor/harness/scripts/harness.py',
  'vendor/harness/scripts/managed_assets.py',
  'vendor/harness/scripts/asset_checks.py',
  'vendor/harness/scripts/plan_governance.py',
  'vendor/harness/scripts/knowledge_assets.py',
  'vendor/harness/scripts/acceptance_assets.py',
  'vendor/harness/scripts/adr_assets.py',
  'vendor/harness/scripts/script_hygiene.py',
  'vendor/harness/scripts/githooks/pre-commit',
  'vendor/harness/scripts/githooks/setup.sh',
  'vendor/harness/plan-templates/levels/brief.json',
  'vendor/harness/plan-templates/levels/full.json',
];

/** Every plan profile the engine can be asked for. */
const PLAN_PROFILES = ['general', 'frontend-ui', 'backend-service', 'bugfix', 'architecture', 'migration-release'];

const failures = [];

/**
 * @param {boolean} condition - what must hold.
 * @param {string} message - what to report when it does not.
 */
function check(condition, message) {
  if (!condition) failures.push(message);
}

for (const relative of REQUIRED_FILES) {
  check(fs.existsSync(path.join(ROOT, relative)), `missing ${relative}`);
}
for (const profile of PLAN_PROFILES) {
  const relative = `vendor/harness/plan-templates/profiles/${profile}.json`;
  check(fs.existsSync(path.join(ROOT, relative)), `missing ${relative}`);
}

const manifest = JSON.parse(fs.readFileSync(path.join(ROOT, 'package.json'), 'utf8'));
check(manifest.name === PACKAGE_NAME, `package name ${manifest.name} does not match the constant ${PACKAGE_NAME}`);
check(manifest.dsh?.client?.platform === 'web', 'dsh.client.platform must be "web"');
check(typeof manifest.dsh?.bundle?.patch === 'string', 'dsh.bundle.patch must name the cordis patch');
check(manifest.exports?.['./client'] === './lib/client.js', 'exports["./client"] must point at the built bundle');

// The `files` allowlist decides what actually ships; a path outside it is
// present in the working tree and absent from the tarball.
for (const relative of REQUIRED_FILES) {
  const top = relative.split('/')[0];
  check(manifest.files.includes(top), `${relative} is not covered by package.json "files"`);
}

const bundle = fs.existsSync(path.join(ROOT, 'lib', 'client.js'))
  ? fs.readFileSync(path.join(ROOT, 'lib', 'client.js'), 'utf8')
  : '';
check(
  bundle.startsWith(`window.__ModuleLoader__.load({ id: ${JSON.stringify(PACKAGE_NAME)}`),
  'lib/client.js is not the loader-factory artifact — run the build',
);

if (failures.length > 0) {
  for (const failure of failures) process.stderr.write(`verify-package: ${failure}\n`);
  process.exit(1);
}
process.stdout.write(`verify-package: ${PACKAGE_NAME} is publishable\n`);
