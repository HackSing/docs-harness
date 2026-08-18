/**
 * Shared preconditions for every model-facing tool in this plugin.
 *
 * @module dsh-docs-harness/host/tool-support
 */

import { NOT_ENABLED_HINT } from '../shared/constants.js';
import { engineFor, runEngine } from './engine.js';
import { detectProject } from './project-state.js';

/**
 * The workspace root a tool call acts on.
 * @param {object} exec - the tool execution context.
 * @returns {string} the absolute project root.
 * @throws {Error} when the caller has no agent-owned session with a cwd.
 */
export function projectDirOf(exec) {
  const cwd = exec.agent?.session.header.cwd;
  if (typeof cwd !== 'string' || cwd === '') {
    throw new Error('Docs Harness tools require an agent session bound to a workspace directory');
  }
  return cwd;
}

/**
 * Resolve the project root and refuse when Docs Harness is not installed there.
 *
 * The refusal is deliberate and final: installing writes into the user's
 * repository, and this plugin's whole contract is that only the user starts
 * that. The message tells the model to say so rather than look for another way.
 * @param {object} exec - the tool execution context.
 * @returns {string} the absolute project root of a prepared project.
 * @throws {Error} when the project has no Docs Harness install.
 */
export function requireEnabledProject(exec) {
  const projectDir = projectDirOf(exec);
  if (!detectProject(projectDir).enabled) throw new Error(NOT_ENABLED_HINT);
  return projectDir;
}

/**
 * Run one engine subcommand on behalf of a tool call.
 * @param {object} exec - the tool execution context.
 * @param {string[]} args - subcommand and flags, without `--json`/`--target`.
 * @returns {Promise<Record<string, unknown>>} the engine's JSON payload.
 */
export async function runForTool(exec, args) {
  const projectDir = requireEnabledProject(exec);
  const settled = await runEngine({ engine: engineFor(projectDir), args, projectDir });
  return settled.payload;
}

/**
 * Append optional string flags to an argument vector.
 * @param {string[]} args - the vector being built.
 * @param {Record<string, string | undefined>} flags - flag name to value.
 * @returns {string[]} the same vector, for chaining.
 */
export function withFlags(args, flags) {
  for (const [flag, value] of Object.entries(flags)) {
    if (value !== undefined && value !== '') args.push(flag, value);
  }
  return args;
}
