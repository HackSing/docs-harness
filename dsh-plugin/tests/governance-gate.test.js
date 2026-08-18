import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { Config, apply } from '../src/host/index.js';
import { PLAN_PROJECTION_KEY, ROUTE_PREFIX, TOOL_NAMES } from '../src/shared/constants.js';
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

  it('mounts without a settings service (the composition entry is authoritative)', () => {
    const { ctx, ledger } = createFakeContext();
    assert.equal(ctx.get('settings'), undefined);
    apply(ctx, new Config({}));
    assert.deepEqual(ledger.tools, TOOL_NAMES);
  });
});
