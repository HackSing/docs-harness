/**
 * The three project-level operations: install, upgrade, remove.
 *
 * These write into the user's repository, so they are deliberately NOT model
 * tools — nothing an agent can reach for. They exist only behind the HTTP
 * routes the UI calls when the user clicks, which is what makes "the user
 * decides, always" a property of the wiring rather than of a prompt.
 *
 * @module dsh-docs-harness/host/project-ops
 */

import { ACTION_INIT, ACTION_UNINSTALL, ACTION_UPGRADE } from '../shared/constants.js';
import { engineFor, runEngine } from './engine.js';
import { SEED_ENGINE } from './engine.js';
import { detectProject, resetProjectCaches } from './project-state.js';

/** Operations the routes expose, and the engine invocation each maps to. */
const OPERATIONS = {
  // Install runs from the SEED: the project has no engine of its own yet, and
  // the seed is precisely the version this plugin is prepared to support.
  [ACTION_INIT]: { engine: () => SEED_ENGINE, args: () => ['project', 'init'] },
  // Upgrade also runs from the seed — it is the newer side of the migration.
  [ACTION_UPGRADE]: { engine: () => SEED_ENGINE, args: () => ['project', 'upgrade', '--apply'] },
  // Removal is the project's own engine: it knows the fingerprints it wrote,
  // and only deletes files the user has not modified.
  [ACTION_UNINSTALL]: { engine: projectDir => engineFor(projectDir), args: () => ['project', 'uninstall', '--apply'] },
};

/** The operation names the routes accept. */
export const OPERATION_NAMES = Object.keys(OPERATIONS);

/**
 * Run one project operation and report the resulting state.
 * @param {string} operation - one of {@link OPERATION_NAMES}.
 * @param {string} projectDir - absolute project root.
 * @returns {Promise<{ state: object, changed: unknown }>} the post-operation state.
 * @throws {Error} when the operation is unknown or the engine refuses.
 */
export async function runProjectOperation(operation, projectDir) {
  const spec = OPERATIONS[operation];
  if (spec === undefined) throw new Error(`unknown project operation "${operation}"`);
  const settled = await runEngine({ engine: spec.engine(projectDir), args: spec.args(), projectDir });
  // The install stamp and AGENTS.md just changed underneath every cache.
  resetProjectCaches();
  return {
    state: detectProject(projectDir),
    changed: settled.payload['changed'] ?? settled.payload['removed'] ?? [],
  };
}
