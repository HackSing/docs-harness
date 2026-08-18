/**
 * The shipped artifact's contract with the host's client module system.
 *
 * Nothing about this is checkable by reading the source: the wrapper, the
 * externals, and the exports are properties of the BUILD. Getting any of them
 * wrong produces a bundle that loads without complaint and then fails to
 * materialize in the browser, which is the worst place to find out.
 */
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { before, describe, it } from 'node:test';

import { PACKAGE_NAME } from '../src/shared/constants.js';

const ROOT = fileURLToPath(new URL('..', import.meta.url));
const ARTIFACT = fileURLToPath(new URL('../lib/client.js', import.meta.url));

/** Specifiers the host's frozen module table can answer. */
const TABLE_WORDS = [
  'react', 'react/jsx-runtime', 'react-dom', 'react-dom/client', '@deepseek-ai/cordis',
  '@deepseek-ai/dsh-client-ui-slots', '@deepseek-ai/dsh-client-web-react',
  '@deepseek-ai/dsh-client-ui-primitives', '@deepseek-ai/dsh-client-ui-attachment',
  '@deepseek-ai/dsh-client-schema-form',
];

let bundle = '';

before(() => {
  execFileSync(process.execPath, ['scripts/build-client.mjs'], { cwd: ROOT, stdio: 'inherit' });
  bundle = fs.readFileSync(ARTIFACT, 'utf8');
});

describe('client bundle', () => {
  it('registers a factory under the package name instead of running on load', () => {
    assert.ok(bundle.startsWith(`window.__ModuleLoader__.load({ id: ${JSON.stringify(PACKAGE_NAME)}, factory: (require) => {`));
    assert.ok(bundle.trimEnd().endsWith('return module.exports; } });')
      || bundle.includes('return module.exports; } });'));
  });

  it('declares the module/exports pair the CJS body assigns to', () => {
    assert.match(bundle, /var module = \{ exports: \{\} \}; var exports = module\.exports;/);
  });

  it('exports the two names cordis reads off a plugin module', () => {
    assert.match(bundle, /apply: \(\) => apply/);
    assert.match(bundle, /inject: \(\) => inject/);
  });

  it('requires only specifiers the host module table can answer', () => {
    const required = [...bundle.matchAll(/\brequire\("([^"]+)"\)/g)].map(match => match[1]);
    assert.ok(required.length > 0, 'the artifact requires nothing — the externals list stopped being applied');
    for (const specifier of new Set(required)) {
      assert.ok(TABLE_WORDS.includes(specifier), `"${specifier}" has no row in the frozen module table`);
    }
  });

  it('inlines its own dependencies rather than importing another plugin package', () => {
    assert.doesNotMatch(bundle, /require\("@deepseek-ai\/dsh-(?!client-(ui-slots|web-react|ui-primitives|ui-attachment|schema-form))/);
  });

  it('carries the stylesheet inside the factory, not as a separate asset', () => {
    assert.match(bundle, /data-plugin-css/);
    assert.match(bundle, /--dsw-alias-label-primary/);
  });

  it('ships a sourcemap next to it', () => {
    assert.ok(fs.existsSync(`${ARTIFACT}.map`));
    assert.match(bundle, /sourceMappingURL=client\.js\.map/);
  });
});
