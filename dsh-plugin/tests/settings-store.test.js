/**
 * The route-backed settings store: snapshot discipline and write recovery.
 *
 * What matters here is the contract the slot hooks rely on — a stable snapshot
 * reference between changes, serialized operations, and a rejected write that
 * leaves the previous snapshot standing for the control to snap back to.
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  ACTION_SETTINGS_READ,
  ACTION_SETTINGS_RESET,
  ACTION_SETTINGS_WRITE,
  SETTINGS_ROUTE_PREFIX,
} from '../src/shared/constants.js';
import { HarnessSettingsStore } from '../src/client/settings-store.js';

/** A transport answering from a script of envelopes, recording every call. */
function makeTransport(script) {
  const calls = [];
  const transport = (path, body) => {
    calls.push({ path, body });
    const next = script.shift();
    return Promise.resolve(typeof next === 'function' ? next() : next);
  };
  return { transport, calls };
}

const READY = { ok: true, value: { value: { governance: true, dismissed: [] }, user: {}, writable: true } };

describe('settings store', () => {
  it('starts loading and publishes ready after a successful read', async () => {
    const { transport, calls } = makeTransport([READY]);
    const store = new HarnessSettingsStore(transport);
    assert.equal(store.getSnapshot().status, 'loading');
    await store.load();
    assert.deepEqual(calls, [{ path: `${SETTINGS_ROUTE_PREFIX}/${ACTION_SETTINGS_READ}`, body: {} }]);
    assert.deepEqual(store.getSnapshot(), { status: 'ready', value: { governance: true, dismissed: [] }, user: {}, writable: true });
  });

  it('publishes unavailable on a refused or unreachable read', async () => {
    const store = new HarnessSettingsStore(() => Promise.resolve({ ok: false, error: { code: 'unreachable', message: 'x' } }));
    await store.load();
    assert.equal(store.getSnapshot().status, 'unavailable');
    assert.equal(store.getSnapshot().writable, false);
  });

  it('keeps the snapshot reference stable between changes and notifies on each', async () => {
    // Two envelopes: the first subscriber triggers one load, the explicit call is the second.
    const { transport } = makeTransport([READY, READY]);
    const store = new HarnessSettingsStore(transport);
    let notified = 0;
    store.subscribe(() => { notified += 1; });
    const before = store.getSnapshot();
    assert.equal(store.getSnapshot(), before);
    await store.load();
    assert.notEqual(store.getSnapshot(), before);
    assert.equal(store.getSnapshot(), store.getSnapshot());
    assert.ok(notified >= 1);
  });

  it('the first subscriber of an unanswered store triggers a load; a ready store is left alone', async () => {
    const { transport, calls } = makeTransport([READY, READY]);
    const store = new HarnessSettingsStore(transport);
    store.subscribe(() => {});
    await store.tail;
    assert.equal(calls.length, 1);
    assert.equal(store.getSnapshot().status, 'ready');
    store.subscribe(() => {});
    await store.tail;
    assert.equal(calls.length, 1, 'a ready store must not re-read for every new subscriber');
  });

  it('a successful write publishes the section the host answered with', async () => {
    const fresh = { ok: true, value: { value: { governance: false, dismissed: [] }, user: { governance: false }, writable: true } };
    const { transport, calls } = makeTransport([READY, fresh]);
    const store = new HarnessSettingsStore(transport);
    await store.load();
    await store.set('governance', false);
    assert.deepEqual(calls[1], {
      path: `${SETTINGS_ROUTE_PREFIX}/${ACTION_SETTINGS_WRITE}`,
      body: { field: 'governance', value: false },
    });
    assert.equal(store.getSnapshot().value.governance, false);
    assert.deepEqual(store.getSnapshot().user, { governance: false });
  });

  it('a reset posts the reset action and publishes the section without the override', async () => {
    const overridden = { ok: true, value: { value: { governance: false, dismissed: [] }, user: { governance: false }, writable: true } };
    const fresh = { ok: true, value: { value: { governance: true, dismissed: [] }, user: {}, writable: true } };
    const { transport, calls } = makeTransport([overridden, fresh]);
    const store = new HarnessSettingsStore(transport);
    await store.load();
    await store.reset('governance');
    assert.deepEqual(calls[1], {
      path: `${SETTINGS_ROUTE_PREFIX}/${ACTION_SETTINGS_RESET}`,
      body: { field: 'governance' },
    });
    assert.equal(store.getSnapshot().value.governance, true);
    assert.deepEqual(store.getSnapshot().user, {});
  });

  it('a refused reset rejects and leaves the snapshot standing', async () => {
    const { transport } = makeTransport([
      READY,
      { ok: false, error: { code: 'invalid-field', message: 'not a writable docs-harness field' } },
    ]);
    const store = new HarnessSettingsStore(transport);
    await store.load();
    const before = store.getSnapshot();
    await assert.rejects(() => store.reset('governance'), /not a writable/);
    assert.equal(store.getSnapshot(), before);
  });

  it('a refused write rejects with the host reason and leaves the snapshot standing', async () => {
    const { transport } = makeTransport([
      READY,
      { ok: false, error: { code: 'invalid-field', message: 'not a writable docs-harness field' } },
    ]);
    const store = new HarnessSettingsStore(transport);
    await store.load();
    const before = store.getSnapshot();
    await assert.rejects(() => store.set('governance', false), /not a writable/);
    assert.equal(store.getSnapshot(), before);
  });

  it('a rejected write does not strand the queue', async () => {
    const { transport } = makeTransport([
      READY,
      { ok: false, error: { code: 'failed', message: 'boom' } },
      READY,
    ]);
    const store = new HarnessSettingsStore(transport);
    await store.load();
    await assert.rejects(() => store.set('governance', false));
    await store.load();
    assert.equal(store.getSnapshot().status, 'ready');
  });

  it('operations run strictly in call order', async () => {
    const order = [];
    const store = new HarnessSettingsStore((path) => {
      order.push(path.endsWith(ACTION_SETTINGS_WRITE) ? 'write' : 'read');
      return Promise.resolve(READY);
    });
    const first = store.load();
    const second = store.set('governance', false).catch(() => {});
    const third = store.load();
    await Promise.all([first, second, third]);
    assert.deepEqual(order, ['read', 'write', 'read']);
  });

  it('publishes nothing after dispose', async () => {
    const { transport, calls } = makeTransport([READY]);
    const store = new HarnessSettingsStore(transport);
    store.dispose();
    await store.load();
    assert.equal(calls.length, 0);
    assert.equal(store.getSnapshot().status, 'loading');
  });
});
