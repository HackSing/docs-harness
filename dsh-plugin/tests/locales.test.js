/**
 * The dictionaries and the keys the components actually ask for.
 *
 * A missing key does not throw — the locale service returns the key itself —
 * so nothing at runtime would report `settings.autoUpgrade.hint` never being
 * written. That silence is what these assertions replace.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, it } from 'node:test';

import { ITEM_STATUSES, PROMPT_ENABLE, PROMPT_UPGRADE, TOOL_NAMES } from '../src/shared/constants.js';
import { en, zh } from '../src/client/locales.js';

const CLIENT_DIR = fileURLToPath(new URL('../src/client', import.meta.url));

/** Every `t('literal')` spelled in the browser sources. */
function literalKeys() {
  const keys = new Set();
  for (const entry of fs.readdirSync(CLIENT_DIR)) {
    const source = fs.readFileSync(path.join(CLIENT_DIR, entry), 'utf8');
    for (const match of source.matchAll(/\bt\('([^']+)'/g)) keys.add(match[1]);
  }
  return [...keys];
}

describe('dictionaries', () => {
  it('carries the same key set in both locales', () => {
    assert.deepEqual(Object.keys(en).sort(), Object.keys(zh).sort());
  });

  it('has no blank translation', () => {
    for (const [key, value] of [...Object.entries(zh), ...Object.entries(en)]) {
      assert.ok(value.trim() !== '', `${key} is blank`);
    }
  });

  it('defines every key the components spell literally', () => {
    const literals = literalKeys();
    assert.ok(literals.length > 0, 'the scan found no keys at all — the pattern stopped matching');
    for (const key of literals) assert.ok(key in zh, `missing dictionary key: ${key}`);
  });

  it('defines every key the components build from a value', () => {
    const built = [
      ...TOOL_NAMES.map(name => `card.${name}`),
      ...ITEM_STATUSES.map(status => `status.${status}`),
      `notice.${PROMPT_ENABLE}.action`,
      `notice.${PROMPT_UPGRADE}.action`,
      'settings.governance', 'settings.governance.hint',
      'settings.autoEnable', 'settings.autoEnable.hint',
      'settings.autoUpgrade', 'settings.autoUpgrade.hint',
    ];
    for (const key of built) assert.ok(key in zh, `missing dictionary key: ${key}`);
  });

  it('keeps the interpolation placeholders identical across locales', () => {
    const placeholders = text => [...text.matchAll(/\{(\w+)\}/g)].map(match => match[1]).sort();
    for (const key of Object.keys(zh)) {
      assert.deepEqual(placeholders(en[key]), placeholders(zh[key]), `${key} interpolates differently`);
    }
  });
});
