/**
 * Where the browser half sits, and that it leaves nothing behind.
 *
 * The seats are load-bearing in a way a screenshot cannot check: an order that
 * collides with a shipped dock entry, a toolview key that does not match the
 * wire tool name, or an entry that outlives its fiber are all invisible until
 * someone notices the wrong thing on screen.
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  DOCK_BUBBLE_ID,
  DOCK_BUBBLE_ORDER,
  DOCK_NOTICE_ID,
  DOCK_NOTICE_ORDER,
  FIELD_DISMISSED,
  LOCALE_NAMESPACE,
  SETTINGS_SECTION_ID,
  SETTINGS_SECTION_ORDER,
  TOOL_NAMES,
} from '../src/shared/constants.js';
import { apply, dismisser, inject, writer } from '../src/client/index.jsx';
import { createFakeClientContext } from './fake-client-context.js';

/** Dock seats the shipped packages already occupy (todo, goal, queue). */
const TAKEN_DOCK_ORDERS = [0, 10, 20];

/**
 * @param {object} [section] - the settings section the fake store reports.
 * @returns {object} a mounted fake context.
 */
function mount(section) {
  const harness = createFakeClientContext(section);
  apply(harness.ctx, undefined, harness.store);
  return harness;
}

/**
 * @param {object[]} entries - the ledger's entries.
 * @param {string} name - the slot name to filter by.
 * @returns {object[]} that slot's entries.
 */
const forSlot = (entries, name) => entries.filter(entry => entry.name === name);

describe('client registration', () => {
  it('declares the services it needs, and no more', () => {
    // No settingsScope: the gateway's settings transport serves an allowlist of
    // namespaces this plugin can never join, so the switches ride plugin routes.
    assert.deepEqual(inject, ['slots', 'locale']);
  });

  it('waits for each slot declaration instead of assuming it exists', () => {
    const { ledger } = mount();
    assert.deepEqual(
      ledger.injected.sort(),
      ['conversation.input.dock', 'settings.section', 'tool.call.toolview'],
    );
  });

  it('registers both dock entries below the shipped ones', () => {
    const dock = forSlot(mount().ledger.entries, 'conversation.input.dock');
    assert.deepEqual(dock.map(entry => entry.id), [DOCK_BUBBLE_ID, DOCK_NOTICE_ID]);
    for (const entry of dock) {
      assert.ok(!TAKEN_DOCK_ORDERS.includes(entry.order), `order ${String(entry.order)} collides with a shipped dock entry`);
    }
    assert.deepEqual(dock.map(entry => entry.order), [DOCK_BUBBLE_ORDER, DOCK_NOTICE_ORDER]);
  });

  it('claims exactly its own tool names as tool views', () => {
    const views = forSlot(mount().ledger.entries, 'tool.call.toolview');
    assert.deepEqual(views.map(entry => entry.key), TOOL_NAMES);
  });

  it('registers one first-level settings section with its nav identity', () => {
    const sections = forSlot(mount().ledger.entries, 'settings.section');
    assert.equal(sections.length, 1);
    assert.equal(sections[0].id, SETTINGS_SECTION_ID);
    assert.equal(sections[0].order, SETTINGS_SECTION_ORDER);
    // A list slot carries no key — that constraint belongs to the keyed
    // settings.plugin.item contract this plugin no longer registers into.
    assert.equal(sections[0].key, undefined);
  });

  it('resolves the nav label lazily so a locale switch re-projects it', () => {
    const section = forSlot(mount().ledger.entries, 'settings.section')[0];
    assert.equal(typeof section.label, 'function');
    assert.equal(section.label(), `${LOCALE_NAMESPACE}:settings.title`);
  });

  it('declares the locale namespace on every entry, so `t` is present', () => {
    for (const entry of mount().ledger.entries) {
      assert.equal(entry.locale, LOCALE_NAMESPACE, `${entry.id ?? entry.key} would render without a translator`);
    }
  });

  it('registers both dictionaries under that namespace', () => {
    const { ledger } = mount();
    assert.equal(ledger.dictionaries.length, 1);
    assert.equal(ledger.dictionaries[0].namespace, LOCALE_NAMESPACE);
    assert.deepEqual(Object.keys(ledger.dictionaries[0].dictionaries).sort(), ['en', 'zh']);
  });

  it('loads the settings store at activation and disposes it with the fiber', () => {
    const { ctx, ledger } = mount();
    assert.equal(ledger.loads, 1);
    assert.equal(ledger.storeDisposed, 0);
    ctx.__dispose();
    assert.equal(ledger.storeDisposed, 1);
  });

  it('hands the notice bar and the settings page the live store, not a copied value', () => {
    const { ledger, store } = mount();
    const notice = ledger.entries.find(entry => entry.id === DOCK_NOTICE_ID);
    const page = ledger.entries.find(entry => entry.id === SETTINGS_SECTION_ID);
    assert.equal(notice.inject().hooks.harness, store);
    assert.equal(page.inject().hooks.harness, store);
    assert.equal(typeof notice.inject().onDismiss, 'function');
    assert.equal(typeof page.inject().write, 'function');
    assert.equal(typeof page.inject().reset, 'function');
  });

  it('registers nothing that the plan bubble needs injected — it reads a projection', () => {
    const bubble = mount().ledger.entries.find(entry => entry.id === DOCK_BUBBLE_ID);
    assert.equal(bubble.inject, undefined);
  });

  it('removes every entry and dictionary when the fiber unloads', () => {
    const { ctx, ledger } = mount();
    assert.ok(ledger.entries.length > 0);
    ctx.__dispose();
    assert.deepEqual(ledger.entries, []);
    assert.deepEqual(ledger.dictionaries, []);
  });
});

describe('settings writers', () => {
  it('reports a rejected write instead of leaving the revert unexplained', async () => {
    const write = writer({ set: () => Promise.reject(new Error('read-only document')) });
    assert.deepEqual(await write('governance', false), { ok: false, message: 'read-only document' });
  });

  it('reports a successful write', async () => {
    const written = [];
    const write = writer({ set: (field, value) => { written.push([field, value]); return Promise.resolve(); } });
    assert.deepEqual(await write('governance', false), { ok: true });
    assert.deepEqual(written, [['governance', false]]);
  });

  it('appends a dismissal to the list already stored', async () => {
    const { ledger, store } = mount({ dismissed: ['D:/old'] });
    dismisser(store, writer(store))('D:/new');
    await Promise.resolve();
    assert.deepEqual(ledger.writes, [[FIELD_DISMISSED, ['D:/old', 'D:/new']]]);
  });

  it('does not rewrite a project already dismissed', () => {
    const { ledger, store } = mount({ dismissed: ['D:/old'] });
    dismisser(store, writer(store))('D:/old');
    assert.deepEqual(ledger.writes, []);
  });
});
