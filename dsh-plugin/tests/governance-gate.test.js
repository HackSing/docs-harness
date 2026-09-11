import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { Config, apply } from '../src/host/index.js';
import { PLAN_PROJECTION_KEY, ROUTE_PREFIX, SETTINGS_NAMESPACE, TOOL_NAMES } from '../src/shared/constants.js';
import { createFakeContext } from './fake-context.js';

/**
 * Mount the plugin with a resolved config.
 * @param {object} overrides - config fields to override.
 * @returns {{ ctx: object, ledger: object }} the mounted context and its ledger.
 */
function mount(overrides = {}) {
  const { ctx, ledger } = createFakeContext();
  apply(ctx, new Config({ ...overrides }));
  return { ctx, ledger };
}

describe('governance gate', () => {
  it('defaults to on, so the capability works without the user finding a setting', () => {
    assert.equal(new Config({}).governance, true);
  });

  it('defaults both automatic actions to off, so a first-seen project is only ever offered', () => {
    const config = new Config({});
    assert.equal(config.autoEnable, false);
    assert.equal(config.autoUpgrade, false);
    assert.deepEqual(config.dismissed, []);
  });

  it('registers the whole surface when on', () => {
    const { ledger } = mount({ governance: true });
    assert.deepEqual(ledger.tools, TOOL_NAMES);
    assert.equal(ledger.sections.length, 1);
    assert.deepEqual(ledger.projections, [PLAN_PROJECTION_KEY]);
    assert.deepEqual(ledger.routes, [ROUTE_PREFIX]);
  });

  it('registers NOTHING when off — indistinguishable from not being installed', () => {
    const { ledger } = mount({ governance: false });
    assert.deepEqual(ledger.tools, []);
    assert.deepEqual(ledger.sections, []);
    assert.deepEqual(ledger.projections, []);
    assert.deepEqual(ledger.routes, []);
  });

  it('tears the whole surface down when the plugin unloads', () => {
    const { ctx, ledger } = mount({ governance: true });
    ctx.__dispose();
    assert.equal(ledger.disposed, 1);
    assert.deepEqual(ledger.tools, []);
    assert.deepEqual(ledger.sections, []);
    assert.deepEqual(ledger.projections, []);
    assert.deepEqual(ledger.routes, []);
  });

  it('registers the prompt section as a dynamic provider, not fixed text', () => {
    const { ledger } = mount({ governance: true });
    assert.equal(typeof ledger.sections[0].text, 'function');
    assert.equal(typeof ledger.sections[0].order, 'number');
  });

  // The host contract that broke on dsh 0.1.5-rc.1: the section used to be
  // installed by a free function this package imported, and the import turned
  // into a hard boot failure the moment upstream dropped the export. Mounting
  // against a settings service pins the call we actually make, so the next
  // upstream rename fails here instead of at a user's first launch.
  it('installs its settings section through the settings service', () => {
    const { ctx, services } = createFakeContext();
    const calls = [];
    services.set('settings', {
      installSection(owner, ns, schema, entry, hooks) {
        calls.push({ owner, ns, schema, entry, hooks });
      },
    });
    apply(ctx, new Config({}));
    assert.equal(calls.length, 1);
    assert.equal(calls[0].ns, SETTINGS_NAMESPACE);
    assert.equal(calls[0].schema, Config);
    assert.equal(calls[0].entry.governance, true);
    assert.equal(typeof calls[0].hooks.setSource, 'function');
    assert.equal(typeof calls[0].hooks.onChange, 'function');
  });

  it('lets a settings edit close the gate through setSource + onChange', () => {
    const { ctx, ledger, services } = createFakeContext();
    let hooks;
    services.set('settings', {
      installSection(owner, ns, schema, entry, installed) { hooks = installed; },
    });
    apply(ctx, new Config({}));
    assert.deepEqual(ledger.tools, TOOL_NAMES);
    hooks.setSource(() => ({ governance: false }));
    hooks.onChange();
    assert.deepEqual(ledger.tools, []);
  });

  it('mounts without a settings service (the composition entry is authoritative)', () => {
    const { ctx, ledger } = createFakeContext();
    assert.equal(ctx.get('settings'), undefined);
    apply(ctx, new Config({}));
    assert.deepEqual(ledger.tools, TOOL_NAMES);
  });
});
