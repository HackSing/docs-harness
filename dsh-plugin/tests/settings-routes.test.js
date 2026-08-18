/**
 * The settings route family: the master switch's control plane.
 *
 * These routes exist because the upstream gateway serves settings only for an
 * allowlist of namespaces — so what is under test is the plugin's OWN wire
 * contract: loopback-only, field-guarded writes, and honest not-ready answers.
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  ACTION_SETTINGS_READ,
  ACTION_SETTINGS_WRITE,
  FIELD_DISMISSED,
  FIELD_GOVERNANCE,
  SETTINGS_NAMESPACE,
  SETTINGS_ROUTE_PREFIX,
} from '../src/shared/constants.js';
import { registerSettingsRoutes } from '../src/host/settings-routes.js';

/**
 * @param {object} [options] - settings service behaviour overrides.
 * @returns {object} a fake host context plus its recording ledger.
 */
function makeCtx({ section = { governance: true, dismissed: [] }, unregistered = false, writable = true, failWrite } = {}) {
  const ledger = { registered: [], updates: [], warnings: [], disposed: 0 };
  let value = section;
  const ctx = {
    logger: { warn: message => ledger.warnings.push(String(message)) },
    webServer: {
      register(options) {
        ledger.registered.push(options);
        return () => { ledger.disposed += 1; };
      },
    },
    settings: {
      get: ns => (ns === SETTINGS_NAMESPACE && !unregistered ? value : undefined),
      writable,
      update: async (ns, patch) => {
        if (failWrite !== undefined) throw new Error(failWrite);
        ledger.updates.push([ns, patch]);
        value = value === undefined ? undefined : { ...value, ...patch };
      },
    },
  };
  return { ctx, ledger };
}

/**
 * @param {object} spec - request shape.
 * @returns {object} a fake IncomingMessage feeding `spec.body` then end.
 */
function request({ method = 'POST', action = ACTION_SETTINGS_READ, address = '127.0.0.1', body = '{}' }) {
  const handlers = {};
  const req = {
    method,
    url: `${SETTINGS_ROUTE_PREFIX}/${action}`,
    socket: { remoteAddress: address },
    on(event, callback) { handlers[event] = callback; return req; },
  };
  queueMicrotask(() => {
    if (body !== undefined) handlers.data?.(body);
    handlers.end?.();
  });
  return req;
}

/**
 * @returns {object} a fake ServerResponse recording status and parsed body.
 */
function response() {
  const record = { status: undefined, body: undefined, settled: undefined };
  let resolve;
  record.settled = new Promise((r) => { resolve = r; });
  return {
    record,
    writeHead(status) { record.status = status; },
    end(chunk) {
      record.body = chunk === undefined ? undefined : JSON.parse(String(chunk));
      resolve();
    },
  };
}

/**
 * Mount the routes and answer one request.
 * @param {object} ctx - the fake host context.
 * @param {object} spec - request shape for {@link request}.
 * @returns {Promise<{ status?: number, body?: object }>} what the route wrote.
 */
async function roundTrip(ctx, spec) {
  registerSettingsRoutes(ctx);
  const handler = ctx.webServer === undefined ? undefined : lastRegistered(ctx);
  const res = response();
  await handler(request(spec), res);
  await res.record.settled;
  return res.record;
}

/** @param {object} ctx - the fake context. @returns {Function} the last registered handler. */
function lastRegistered(ctx) {
  // registerSettingsRoutes pushed exactly one registration in these tests.
  return ctx.__lastHandler;
}

describe('settings routes', () => {
  it('registers one prefix handler on its own sibling prefix, and the disposer removes it', () => {
    const { ctx, ledger } = makeCtx();
    const dispose = registerSettingsRoutes(ctx);
    assert.equal(ledger.registered.length, 1);
    assert.equal(ledger.registered[0].kind, 'prefix');
    assert.equal(ledger.registered[0].path, SETTINGS_ROUTE_PREFIX);
    dispose();
    assert.equal(ledger.disposed, 1);
  });

  it('refuses non-loopback peers before reading anything', async () => {
    const { ctx, ledger } = makeCtx();
    hook(ctx);
    const record = await roundTrip(ctx, { address: '203.0.113.7' });
    assert.equal(record.status, 403);
    assert.deepEqual(ledger.updates, []);
  });

  it('answers only POST and only its two actions', async () => {
    const { ctx } = makeCtx();
    hook(ctx);
    assert.equal((await roundTrip(ctx, { method: 'GET' })).status, 405);
    assert.equal((await roundTrip(ctx, { action: 'reset' })).status, 404);
  });

  it('read reports the resolved section and writability', async () => {
    const { ctx } = makeCtx({ section: { governance: false, dismissed: ['D:/x'] } });
    hook(ctx);
    const record = await roundTrip(ctx, { action: ACTION_SETTINGS_READ });
    assert.deepEqual(record.body, {
      ok: true,
      value: { value: { governance: false, dismissed: ['D:/x'] }, writable: true },
    });
  });

  it('read reports not-ready while the namespace is unregistered, instead of inventing defaults', async () => {
    const { ctx } = makeCtx({ unregistered: true });
    hook(ctx);
    const record = await roundTrip(ctx, { action: ACTION_SETTINGS_READ });
    assert.equal(record.body.ok, false);
    assert.equal(record.body.error.code, 'not-ready');
  });

  it('write updates exactly the guarded field and answers with the fresh section', async () => {
    const { ctx, ledger } = makeCtx();
    hook(ctx);
    const record = await roundTrip(ctx, {
      action: ACTION_SETTINGS_WRITE,
      body: JSON.stringify({ field: FIELD_GOVERNANCE, value: false }),
    });
    assert.deepEqual(ledger.updates, [[SETTINGS_NAMESPACE, { governance: false }]]);
    assert.equal(record.body.ok, true);
    assert.equal(record.body.value.value.governance, false);
  });

  it('write accepts a string list for the dismissal field', async () => {
    const { ctx, ledger } = makeCtx();
    hook(ctx);
    const record = await roundTrip(ctx, {
      action: ACTION_SETTINGS_WRITE,
      body: JSON.stringify({ field: FIELD_DISMISSED, value: ['D:/a', 'D:/b'] }),
    });
    assert.equal(record.body.ok, true);
    assert.deepEqual(ledger.updates, [[SETTINGS_NAMESPACE, { dismissed: ['D:/a', 'D:/b'] }]]);
  });

  it('write refuses unknown fields and wrong shapes without touching the service', async () => {
    const { ctx, ledger } = makeCtx();
    hook(ctx);
    for (const body of [
      { field: 'governance', value: 'yes' },
      { field: 'dismissed', value: [1, 2] },
      { field: 'python', value: true },
      { value: true },
    ]) {
      const record = await roundTrip(ctx, { action: ACTION_SETTINGS_WRITE, body: JSON.stringify(body) });
      assert.equal(record.body.ok, false, JSON.stringify(body));
      assert.equal(record.body.error.code, 'invalid-field');
    }
    assert.deepEqual(ledger.updates, []);
  });

  it('carries a refused provider write back as the error message', async () => {
    const { ctx } = makeCtx({ failWrite: 'settings provider is read-only' });
    hook(ctx);
    const record = await roundTrip(ctx, {
      action: ACTION_SETTINGS_WRITE,
      body: JSON.stringify({ field: FIELD_GOVERNANCE, value: false }),
    });
    assert.equal(record.body.ok, false);
    assert.match(record.body.error.message, /read-only/);
  });

  it('answers malformed JSON as bad-request instead of crashing the route', async () => {
    const { ctx } = makeCtx();
    hook(ctx);
    const record = await roundTrip(ctx, { action: ACTION_SETTINGS_READ, body: 'not json' });
    assert.equal(record.body.ok, false);
    assert.equal(record.body.error.code, 'bad-request');
  });
});

/**
 * Capture the handler the register call installs, for direct driving.
 * @param {object} ctx - the fake context to instrument.
 */
function hook(ctx) {
  const original = ctx.webServer.register.bind(ctx.webServer);
  ctx.webServer.register = (options) => {
    ctx.__lastHandler = options.handler;
    return original(options);
  };
}
