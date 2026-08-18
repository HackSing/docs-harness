/**
 * The smallest BROWSER cordis context this plugin can be mounted on: the slot
 * registry and the locale registry, plus a recording settings store standing in
 * for the live route-backed one.
 *
 * `slots.inject` is bound per context on purpose. In the real registry that
 * method installs an effect on the CALLER's fiber — which is why unloading the
 * plugin removes its slot entries — and a fake that registered globally would
 * make a leak look like a pass.
 */

import { createCordis } from './fake-cordis.js';

/**
 * @param {object} [section] - the settings section the fake store reports.
 * @returns {object} a fresh recording client context plus its ledger and store.
 */
export function createFakeClientContext(section = {}) {
  const ledger = {
    entries: [],
    injected: [],
    dictionaries: [],
    writes: [],
    warnings: [],
    loads: 0,
    storeDisposed: 0,
    disposed: 0,
  };
  const services = new Map();

  services.set('slots', {
    __bind(ctx) {
      return {
        inject: (key, callback) => {
          ledger.injected.push(key);
          return ctx.effect(callback, `slots.inject(${key})`);
        },
        register: (options, component) => {
          const entry = { ...options, component };
          ledger.entries.push(entry);
          return () => { ledger.entries.splice(ledger.entries.indexOf(entry), 1); };
        },
      };
    },
  });

  services.set('locale', {
    register(namespace, dictionaries) {
      const record = { namespace, dictionaries };
      ledger.dictionaries.push(record);
      return () => { ledger.dictionaries.splice(ledger.dictionaries.indexOf(record), 1); };
    },
  });

  let value = section;
  const listeners = new Set();
  const store = {
    getSnapshot: () => ({ status: 'ready', value, writable: true }),
    subscribe: (listener) => { listeners.add(listener); return () => listeners.delete(listener); },
    load: () => { ledger.loads += 1; return Promise.resolve(); },
    set: (field, next) => {
      ledger.writes.push([field, next]);
      value = { ...value, [field]: next };
      for (const listener of listeners) listener();
      return Promise.resolve();
    },
    dispose: () => { ledger.storeDisposed += 1; },
  };

  return { ctx: createCordis(services, ledger), ledger, store };
}
