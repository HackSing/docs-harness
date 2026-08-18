/**
 * dsh-docs-harness — host half.
 *
 * Docs Harness is a plan / knowledge / acceptance discipline implemented by a
 * Python engine that lives in the user's own repository. This plugin makes that
 * discipline reachable from the app: it injects the project's governance rules
 * into the agent's prompt, exposes the plan lifecycle as tools, projects
 * progress for the UI, and lets the user install or remove the engine.
 *
 * TWO GATES decide whether any of that happens.
 *   1. The governance setting (default on). Off means off: no tools, no prompt
 *      section, no projection, no project routes — the whole child fiber is
 *      disposed, so a session behaves exactly as it would without this package
 *      installed. Only the settings control plane (settings-routes.js) stays,
 *      because it is how the switch is turned back on.
 *   2. The project's own install state. A project with no Docs Harness install
 *      gets no rules injected and no working plan tools, only an offer to
 *      install — which only the user can accept.
 *
 * @module dsh-docs-harness
 */

import { installSettingsSection, settingsNamespace } from '@deepseek-ai/dsh-settings';
import z from '@deepseek-ai/schemastery';

import {
  DEFAULT_AUTO_ENABLE,
  DEFAULT_AUTO_UPGRADE,
  DEFAULT_GOVERNANCE_ENABLED,
  PACKAGE_NAME,
  RULES_SECTION_NAME,
  RULES_SECTION_ORDER,
  SETTINGS_NAMESPACE,
} from '../shared/constants.js';
import { planProjectionDefinition } from './plan-projection.js';
import { detectProject, readGovernanceRules } from './project-state.js';
import { registerRoutes } from './routes.js';
import { buildRulesSection } from './rules-section.js';
import { registerSettingsRoutes } from './settings-routes.js';
import { harnessTools } from './tools.js';

/** Plugin name in the cordis roster. */
export const name = PACKAGE_NAME;

/**
 * Hard requirements. Everything else this plugin touches — projections, the web
 * server, the questions channel — is optional and reached through a child
 * inject, so a headless or trimmed assembly still loads.
 */
export const inject = ['tools', 'systemPrompt'];

/** User-facing settings for this plugin. */
export const Config = z.object({
  governance: z.boolean().default(DEFAULT_GOVERNANCE_ENABLED)
    .description('Inject Docs Harness governance rules and expose the plan tools.'),
  autoEnable: z.boolean().default(DEFAULT_AUTO_ENABLE)
    .description('Install Docs Harness into a new project automatically instead of asking.'),
  autoUpgrade: z.boolean().default(DEFAULT_AUTO_UPGRADE)
    .description('Upgrade a project whose Docs Harness version is behind, automatically.'),
  dismissed: z.array(z.string()).default([])
    .description('Projects where the install offer was declined; they are not offered again.'),
});

/**
 * The gated half: everything that exists only while governance is on.
 *
 * A child plugin rather than a bag of disposers, because that is what makes the
 * teardown total — nested injects, the projection cell, the route, and the
 * prompt section all belong to this fiber and unwind with it.
 */
const governanceFiber = {
  name: `${PACKAGE_NAME}:governance`,
  /**
   * @param {object} ctx - the child context.
   */
  apply(ctx) {
    for (const tool of harnessTools(ctx)) ctx.effect(() => ctx.tools.register(tool), `${PACKAGE_NAME}: ${tool.name}`);

    // Evaluated at every prompt assembly, per agent: enabling a project
    // mid-session makes the very next step carry the rules, and no session
    // ever caches another session's project.
    ctx.effect(() => ctx.systemPrompt.section({
      name: RULES_SECTION_NAME,
      order: RULES_SECTION_ORDER,
      text: context => governanceText(context),
    }), `${PACKAGE_NAME}: governance rules`);

    ctx.inject(['sessionProjections'], (projectionCtx) => {
      projectionCtx.effect(
        () => projectionCtx.sessionProjections.register(planProjectionDefinition),
        `${PACKAGE_NAME}: plan projection`,
      );
    });

    ctx.inject(['webServer', 'sessions'], (routeCtx) => {
      routeCtx.effect(() => registerRoutes(routeCtx), `${PACKAGE_NAME}: project routes`);
    });
  },
};

/**
 * The rules for one prompt assembly.
 *
 * Empty for a diagnostics assembly with no agent, and empty for a project with
 * no Docs Harness install — rules describing a lifecycle whose tooling refuses
 * to run would be instructions the agent cannot follow.
 * @param {{ agent?: { session: { header: { cwd?: string } } } }} context - the assembly context.
 * @returns {string} the section text, possibly empty.
 */
export function governanceText(context) {
  const cwd = context.agent?.session.header.cwd;
  if (typeof cwd !== 'string' || cwd === '') return '';
  if (!detectProject(cwd).enabled) return '';
  return buildRulesSection(readGovernanceRules(cwd));
}

/**
 * Mount the plugin.
 * @param {object} ctx - the host plugin context.
 * @param {object} config - the composition entry config.
 */
export function apply(ctx, config) {
  let source = () => config;
  let fiber;

  const reconcile = () => {
    const wanted = source().governance !== false;
    if (wanted && fiber === undefined) {
      fiber = ctx.plugin(governanceFiber);
      return;
    }
    if (!wanted && fiber !== undefined) {
      const closing = fiber;
      fiber = undefined;
      // Teardown is asynchronous; a failure here would otherwise vanish into an
      // unhandled rejection and leave the operator with a silently half-off gate.
      void closing.dispose().catch((cause) => {
        ctx.logger?.warn(`${PACKAGE_NAME}: disposing the governance fiber failed: ${String(cause)}`);
      });
    }
  };

  // Open the gate from the composition entry first: a deployment with no
  // settings service mounted never calls onChange, and must still work.
  reconcile();
  installSettingsSection(ctx, settingsNamespace(SETTINGS_NAMESPACE), Config, config, {
    setSource: (current) => { source = current; },
    onChange: reconcile,
  });
  // The browser's settings surface. On the PLUGIN fiber, not the governance
  // fiber: this is the master switch's control plane, and the gateway's own
  // settings transport cannot carry it (allowlist — see settings-routes.js).
  ctx.inject(['webServer', 'settings'], (settingsCtx) => {
    settingsCtx.effect(() => registerSettingsRoutes(settingsCtx), `${PACKAGE_NAME}: settings routes`);
  });
  ctx.effect(() => () => {
    const closing = fiber;
    fiber = undefined;
    return closing === undefined ? undefined : closing.dispose();
  }, `${PACKAGE_NAME}: governance gate`);
}
