/**
 * The Python engine boundary. Every Docs Harness operation crosses exactly
 * here: one subprocess, `--json` on the wire, the parsed payload back.
 *
 * Two engine copies exist. The project's own `scripts/harness.py` is the truth
 * for a prepared project — it is the version that wrote that project's assets.
 * The vendored seed is only an installer source, used for `project init` and
 * for a project whose copy is missing.
 *
 * Errors are never swallowed: a missing interpreter, a non-zero exit, and
 * unparsable output each throw with the engine's own diagnostic attached.
 *
 * @module dsh-docs-harness/host/engine
 */

import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  ENGINE_SOFT_EXIT_CODES,
  ENGINE_TIMEOUT_MS,
  PROJECT_ENGINE_RELATIVE,
  PYTHON_CANDIDATES,
  PYTHON_MISSING_HINT,
} from '../shared/constants.js';

/** Absolute path of the vendored seed root (`<seed>/scripts/harness.py` + `<seed>/plan-templates/`). */
export const SEED_ROOT = path.join(fileURLToPath(new URL('../../vendor/harness', import.meta.url)));

/** The seed's engine entry. */
export const SEED_ENGINE = path.join(SEED_ROOT, 'scripts', 'harness.py');

/** Raised when the engine could not be run or did not answer with JSON. */
export class EngineError extends Error {
  /**
   * @param {string} message - operator-facing diagnostic.
   * @param {{ code?: string, exitCode?: number | null, payload?: unknown }} [detail] - engine attribution.
   */
  constructor(message, detail = {}) {
    super(message);
    this.name = 'EngineError';
    this.code = detail.code ?? 'engine_failed';
    this.exitCode = detail.exitCode ?? null;
    this.payload = detail.payload;
  }
}

/** Memoized interpreter probe; `null` records "probed, none available". */
let resolvedPython;

/**
 * Locate a usable Python 3. The result is cached for the process because PATH
 * does not change under a running app, and probing on every tool call would
 * add a subprocess to each one.
 * @returns {Promise<string>} the interpreter command.
 * @throws {EngineError} when no candidate answers.
 */
export async function resolvePython() {
  if (resolvedPython === null) throw new EngineError(PYTHON_MISSING_HINT, { code: 'python_missing' });
  if (resolvedPython !== undefined) return resolvedPython;
  for (const candidate of PYTHON_CANDIDATES) {
    const probe = await runProcess(candidate, ['--version'], undefined, 10_000).catch(() => undefined);
    if (probe !== undefined && probe.code === 0) {
      resolvedPython = candidate;
      return candidate;
    }
  }
  resolvedPython = null;
  throw new EngineError(PYTHON_MISSING_HINT, { code: 'python_missing' });
}

/**
 * Spawn one process and collect its output.
 * @param {string} command - executable.
 * @param {string[]} args - argument vector.
 * @param {string | undefined} cwd - working directory.
 * @param {number} timeoutMs - wall-clock budget.
 * @returns {Promise<{ code: number | null, stdout: string, stderr: string }>} the settled process.
 */
function runProcess(command, args, cwd, timeoutMs) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd, windowsHide: true });
    let stdout = '';
    let stderr = '';
    const timer = setTimeout(() => { child.kill(); }, timeoutMs);
    child.stdout.on('data', (chunk) => { stdout += String(chunk); });
    child.stderr.on('data', (chunk) => { stderr += String(chunk); });
    child.on('error', (error) => { clearTimeout(timer); reject(error); });
    child.on('close', (code) => { clearTimeout(timer); resolve({ code, stdout, stderr }); });
  });
}

/**
 * Pick the engine that owns a project: its own installed copy when present,
 * the vendored seed otherwise.
 * @param {string} projectDir - absolute project root.
 * @returns {string} absolute path of the engine entry to run.
 */
export function engineFor(projectDir) {
  const own = path.join(projectDir, PROJECT_ENGINE_RELATIVE);
  return fs.existsSync(own) ? own : SEED_ENGINE;
}

/**
 * Run one engine subcommand and return its parsed JSON payload.
 * @param {object} request - the invocation.
 * @param {string} request.engine - absolute path of the engine entry.
 * @param {string[]} request.args - subcommand and flags, without `--json`.
 * @param {string} request.projectDir - absolute project root (the process cwd).
 * @returns {Promise<{ payload: Record<string, unknown>, exitCode: number | null }>} the engine's answer.
 * @throws {EngineError} on a missing interpreter, a hard exit, or unparsable output.
 */
export async function runEngine({ engine, args, projectDir }) {
  const python = await resolvePython();
  const argv = [engine, ...args, '--json', '--target', projectDir];
  const settled = await runProcess(python, argv, projectDir, ENGINE_TIMEOUT_MS)
    .catch((cause) => {
      throw new EngineError(`could not run ${python}: ${String(cause)}`, { code: 'python_missing' });
    });
  const payload = parsePayload(settled.stdout);
  if (payload === undefined) {
    throw new EngineError(
      `Docs Harness engine produced no JSON (exit ${String(settled.code)}): ${
        (settled.stderr || settled.stdout).trim().slice(0, 400)}`,
      { exitCode: settled.code },
    );
  }
  if (!ENGINE_SOFT_EXIT_CODES.includes(settled.code ?? -1) || payload['status'] === 'error') {
    throw new EngineError(
      `Docs Harness ${args.join(' ')} failed (${String(payload['code'] ?? settled.code)}): ${
        String(payload['message'] ?? 'see payload')}`,
      { code: String(payload['code'] ?? 'engine_failed'), exitCode: settled.code, payload },
    );
  }
  return { payload, exitCode: settled.code };
}

/**
 * Parse the engine's stdout. The engine prints exactly one JSON document, but
 * an interpreter warning can precede it, so the first `{` wins.
 * @param {string} stdout - captured standard output.
 * @returns {Record<string, unknown> | undefined} the payload, or undefined when absent.
 */
function parsePayload(stdout) {
  const start = stdout.indexOf('{');
  if (start < 0) return undefined;
  try {
    const value = JSON.parse(stdout.slice(start));
    return typeof value === 'object' && value !== null && !Array.isArray(value) ? value : undefined;
  } catch {
    return undefined;
  }
}

/** Reset the memoized interpreter probe (tests only). */
export function resetPythonProbe() {
  resolvedPython = undefined;
}
