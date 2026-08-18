/**
 * The smallest HOST cordis context this plugin can be mounted on.
 *
 * It records what was registered so a test can assert the governance gate's two
 * states — which is the whole point, since "off" must mean nothing was
 * registered at all, not that something registered and stayed quiet.
 */

import { createCordis } from './fake-cordis.js';

/** @returns {object} a fresh recording context plus its ledger. */
export function createFakeContext() {
  const ledger = {
    tools: [],
    sections: [],
    projections: [],
    routes: [],
    warnings: [],
    disposed: 0,
  };
  const services = new Map();

  services.set('tools', {
    register(definition) {
      ledger.tools.push(definition.name);
      return () => { ledger.tools.splice(ledger.tools.indexOf(definition.name), 1); };
    },
  });
  services.set('systemPrompt', {
    section(section) {
      ledger.sections.push(section);
      return () => { ledger.sections.splice(ledger.sections.indexOf(section), 1); };
    },
  });
  services.set('sessionProjections', {
    register(definition) {
      ledger.projections.push(definition.key);
      return () => { ledger.projections.splice(ledger.projections.indexOf(definition.key), 1); };
    },
  });
  services.set('webServer', {
    register(route) {
      ledger.routes.push(route.path);
      return () => { ledger.routes.splice(ledger.routes.indexOf(route.path), 1); };
    },
  });
  services.set('sessions', { get: () => undefined });

  return { ctx: createCordis(services, ledger), ledger, services };
}
