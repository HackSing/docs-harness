/**
 * The browser end of the `/docs-harness` and `/docs-harness-settings` routes.
 *
 * One transport, one envelope shape. Transport failures are converted into the
 * same `{ ok: false, error }` the host sends, so a caller has exactly one
 * failure shape to render — nothing is thrown past this boundary and nothing is
 * dropped either.
 *
 * @module dsh-docs-harness/client/api
 */

import { ROUTE_PREFIX } from '../shared/constants.js';

/**
 * A response the routes are not registered for at all. The host removes the
 * project route family when the governance switch is off, so this specific code
 * means "capability absent", which the UI renders as nothing rather than as an
 * error the user cannot act on.
 */
export const CODE_ABSENT = 'route-absent';

/**
 * @typedef {object} HarnessEnvelope
 * @property {boolean} ok - whether the operation succeeded.
 * @property {object} [value] - present when ok.
 * @property {{ code: string, message: string }} [error] - present when not ok.
 */

/**
 * POST one JSON body to one plugin route and normalize every failure into the
 * envelope shape.
 * @param {string} path - the absolute route path.
 * @param {object} body - the JSON payload.
 * @param {AbortSignal} [signal] - cancels the request when the caller unmounts.
 * @returns {Promise<HarnessEnvelope>} the host's envelope, or a transport failure in the same shape.
 */
export async function postJson(path, body, signal) {
  let response;
  try {
    response = await fetch(path, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
      ...(signal === undefined ? {} : { signal }),
    });
  } catch (cause) {
    return { ok: false, error: { code: 'unreachable', message: String(cause) } };
  }
  if (response.status === 404 || response.status === 403 || response.status === 405) {
    return { ok: false, error: { code: CODE_ABSENT, message: `HTTP ${String(response.status)}` } };
  }
  try {
    return await response.json();
  } catch (cause) {
    return { ok: false, error: { code: 'malformed-response', message: String(cause) } };
  }
}

/**
 * Call one project route action for a session's workspace.
 * @param {string} action - `status`, `init`, `upgrade`, or `uninstall`.
 * @param {string | undefined} sessionId - the session whose workspace to act on.
 * @param {AbortSignal} [signal] - cancels the request when the caller unmounts.
 * @returns {Promise<HarnessEnvelope>} the host's envelope, or a transport failure in the same shape.
 */
export async function callHarness(action, sessionId, signal) {
  if (sessionId === undefined) {
    return { ok: false, error: { code: 'no-session', message: 'no current session' } };
  }
  return postJson(`${ROUTE_PREFIX}/${action}`, { sessionId }, signal);
}
