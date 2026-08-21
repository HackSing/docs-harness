/**
 * The settings surface for this plugin's own switches.
 *
 * WHY A ROUTE RATHER THAN THE SETTINGS TRANSPORT. The upstream gateway serves
 * `settings.describe` / `settings.update` only for an allowlist of namespaces
 * compiled into the gateway package; a third-party namespace is filtered from
 * reads and refused on writes ("a future registration does not become remotely
 * readable or writable by default"). The host-side registration still works —
 * values resolve, the reconcile watch fires — so the plugin keeps
 * `installSettingsSection` for the gate and carries the BROWSER's reads and
 * writes over its own loopback route instead, exactly the way the project
 * operations already travel.
 *
 * WHY OUTSIDE THE GOVERNANCE FIBER. These routes are the master switch's
 * control plane. If they unwound with the gate, switching governance off would
 * also remove the only way to switch it back on.
 *
 * SECURITY. Same stance as routes.js: loopback-only, bounded JSON bodies, and
 * writes validated against {@link SETTINGS_FIELD_GUARDS} before the settings
 * service sees them. No request names a namespace — this route family serves
 * exactly one, this plugin's own.
 *
 * @module dsh-docs-harness/host/settings-routes
 */

import {
  ACTION_SETTINGS_READ,
  ACTION_SETTINGS_RESET,
  ACTION_SETTINGS_WRITE,
  SETTINGS_FIELD_GUARDS,
  SETTINGS_NAMESPACE,
  SETTINGS_ROUTE_PREFIX,
} from '../shared/constants.js';
import { isLoopback, readBody, sendJson, sendStatus } from './routes.js';

/**
 * Register the `/docs-harness-settings/*` routes.
 * @param {object} ctx - host context carrying `webServer` and `settings`.
 * @returns {() => void} the disposer removing the routes.
 */
export function registerSettingsRoutes(ctx) {
  return ctx.webServer.register({
    kind: 'prefix',
    path: SETTINGS_ROUTE_PREFIX,
    handler: (req, res) => handle(ctx, req, res),
  });
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
  const action = new URL(req.url ?? '/', 'http://local').pathname.slice(SETTINGS_ROUTE_PREFIX.length + 1);
  if (action !== ACTION_SETTINGS_READ && action !== ACTION_SETTINGS_WRITE && action !== ACTION_SETTINGS_RESET) {
    return sendStatus(res, 404);
  }
  let body;
  try {
    body = await readBody(req);
  } catch (cause) {
    return sendJson(res, { ok: false, error: { code: 'bad-request', message: String(cause) } });
  }
  try {
    if (action === ACTION_SETTINGS_WRITE) {
      const guard = typeof body.field === 'string' ? SETTINGS_FIELD_GUARDS[body.field] : undefined;
      if (guard === undefined || !guard(body.value)) {
        return sendJson(res, {
          ok: false,
          error: { code: 'invalid-field', message: `not a writable docs-harness field/value: ${JSON.stringify(body.field)}` },
        });
      }
      await ctx.settings.update(SETTINGS_NAMESPACE, { [body.field]: body.value });
    }
    if (action === ACTION_SETTINGS_RESET) {
      // Unset from the user layer: the resolved value then re-inherits the
      // composition base and schema defaults — this is the "恢复默认" path.
      if (typeof body.field !== 'string' || SETTINGS_FIELD_GUARDS[body.field] === undefined) {
        return sendJson(res, {
          ok: false,
          error: { code: 'invalid-field', message: `not a writable docs-harness field: ${JSON.stringify(body.field)}` },
        });
      }
      await ctx.settings.mutate(SETTINGS_NAMESPACE, [{ op: 'unset', path: [body.field] }]);
    }
    sendJson(res, { ok: true, value: describeSection(ctx) });
  } catch (cause) {
    ctx.logger?.warn(`docs-harness: settings ${action} failed: ${String(cause)}`);
    sendJson(res, {
      ok: false,
      error: { code: cause?.code ?? 'failed', message: cause instanceof Error ? cause.message : String(cause) },
    });
  }
}

/**
 * The section as the browser needs it: the resolved value, the raw user layer
 * (a field's presence there is the "user-overridden" mark the settings page
 * renders), and whether the provider accepts writes. A namespace not yet
 * registered (the register inject races this route only for the first
 * milliseconds of boot) reports as such instead of inventing a value.
 * @param {object} ctx - host context carrying `settings`.
 * @returns {{ value: object, user: object, writable: boolean }} the browser-facing view.
 */
function describeSection(ctx) {
  // Wire posture: redactSecrets, per the settings service contract. This
  // schema declares no secrets, so the resolved value arrives intact.
  const descriptor = ctx.settings.describe({ redactSecrets: true })
    .find(entry => entry.ns === SETTINGS_NAMESPACE);
  if (descriptor === undefined) {
    const error = new Error('docs-harness settings namespace is not registered yet');
    error.code = 'not-ready';
    throw error;
  }
  return { value: descriptor.value, user: descriptor.user ?? {}, writable: ctx.settings.writable === true };
}
