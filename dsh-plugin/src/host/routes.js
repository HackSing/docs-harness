/**
 * The UI's channel to the project-level operations.
 *
 * WHY HTTP RATHER THAN A PROJECTION. The notice bar has to know a filesystem
 * fact — is Docs Harness installed here — before any event exists to fold, and
 * a projection can only ever be a fold over committed session events. The
 * alternative would be appending an event of our own, which is not survivable
 * (see plan-projection.js). An HTTP route answers a question that has no event
 * behind it, and the same route family carries the click that acts on it.
 *
 * SECURITY. Two gates, both server-side. The request must arrive on loopback,
 * and the directory operated on is resolved from the caller's `sessionId`
 * through the session store — never taken from the request body. A browser
 * that asks about an arbitrary path gets nothing, because it cannot name one.
 *
 * @module dsh-docs-harness/host/routes
 */

import { ACTION_STATUS, ROUTE_PREFIX } from '../shared/constants.js';
import { OPERATION_NAMES, runProjectOperation } from './project-ops.js';
import { detectProject } from './project-state.js';

/** Largest request body accepted (bytes); every legitimate body is one small object. */
const MAX_BODY_BYTES = 4096;

/**
 * Register the `/docs-harness/*` routes.
 * @param {object} ctx - host context carrying `webServer` and `sessions`.
 * @returns {() => void} the disposer removing the routes.
 */
export function registerRoutes(ctx) {
  const dispose = ctx.webServer.register({
    kind: 'prefix',
    path: ROUTE_PREFIX,
    handler: (req, res) => handle(ctx, req, res),
  });
  return dispose;
}

/**
 * Answer one request.
 * @param {object} ctx - host context.
 * @param {import('node:http').IncomingMessage} req - the request.
 * @param {import('node:http').ServerResponse} res - the response.
 * @returns {Promise<void>} settled after the response is written.
 */
async function handle(ctx, req, res) {
  if (!isLoopback(req)) return sendStatus(res, 403);
  if (req.method !== 'POST') return sendStatus(res, 405);
  const action = new URL(req.url ?? '/', 'http://local').pathname.slice(ROUTE_PREFIX.length + 1);
  if (action !== ACTION_STATUS && !OPERATION_NAMES.includes(action)) return sendStatus(res, 404);
  const body = await readBody(req).catch(() => undefined);
  const projectDir = body === undefined ? undefined : workspaceOf(ctx, body.sessionId);
  if (projectDir === undefined) {
    return sendJson(res, { ok: false, error: { code: 'unknown-session', message: 'no live session with a workspace' } });
  }
  try {
    const value = action === ACTION_STATUS
      ? { state: detectProject(projectDir), changed: [] }
      : await runProjectOperation(action, projectDir);
    // The resolved root travels back so the UI can remember a dismissal against
    // the project rather than against the session that happened to be open.
    sendJson(res, { ok: true, value: { ...value, dir: projectDir } });
  } catch (cause) {
    ctx.logger?.warn(`docs-harness: ${action} failed for ${projectDir}: ${String(cause)}`);
    sendJson(res, {
      ok: false,
      error: { code: cause?.code ?? 'failed', message: cause instanceof Error ? cause.message : String(cause) },
    });
  }
}

/**
 * Resolve a session id to its workspace root through the session store.
 * @param {object} ctx - host context.
 * @param {unknown} sessionId - the client-supplied id.
 * @returns {string | undefined} the absolute root, or undefined when the id names no live session.
 */
export function workspaceOf(ctx, sessionId) {
  if (typeof sessionId !== 'string' || sessionId === '') return undefined;
  const cwd = ctx.sessions?.get(sessionId)?.header.cwd;
  return typeof cwd === 'string' && cwd !== '' ? cwd : undefined;
}

/**
 * Whether the request came from the local machine.
 * @param {import('node:http').IncomingMessage} req - the request.
 * @returns {boolean} whether the peer address is loopback.
 */
export function isLoopback(req) {
  const address = req.socket?.remoteAddress ?? '';
  return address === '127.0.0.1' || address === '::1' || address === '::ffff:127.0.0.1';
}

/**
 * Read and parse a bounded JSON body. Shared with the settings routes — the
 * two route families live on different fibers but speak the same HTTP dialect.
 * @param {import('node:http').IncomingMessage} req - the request.
 * @returns {Promise<Record<string, unknown>>} the parsed object.
 */
export function readBody(req) {
  return new Promise((resolve, reject) => {
    let raw = '';
    req.on('data', (chunk) => {
      raw += String(chunk);
      if (raw.length > MAX_BODY_BYTES) reject(new Error('request body too large'));
    });
    req.on('error', reject);
    req.on('end', () => {
      try {
        const value = JSON.parse(raw || '{}');
        if (typeof value !== 'object' || value === null || Array.isArray(value)) reject(new Error('body must be an object'));
        else resolve(value);
      } catch (cause) {
        reject(cause);
      }
    });
  });
}

/**
 * @param {import('node:http').ServerResponse} res - the response.
 * @param {number} status - HTTP status.
 */
export function sendStatus(res, status) {
  res.writeHead(status);
  res.end();
}

/**
 * @param {import('node:http').ServerResponse} res - the response.
 * @param {object} envelope - the `{ ok, value | error }` payload.
 */
export function sendJson(res, envelope) {
  const body = JSON.stringify(envelope);
  res.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
  res.end(body);
}
