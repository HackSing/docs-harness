/**
 * Browser half of Docs Harness: four seats, no state of its own.
 *
 * Every live value this UI shows comes from somewhere that already owns it —
 * the plan from the `harnessPlan` projection, the project's install state from
 * the `/docs-harness` routes, the switches from the host settings namespace
 * over the `/docs-harness-settings` routes (the gateway's settings transport
 * only serves an allowlist of namespaces, so the generic scope binder can
 * never reach ours). The settings store is a thin snapshot cache over that
 * route; everything else keeps no store and no refresh loop.
 *
 * Registration is unconditional even though the host half can be switched off,
 * because the settings card is how the user switches it back on. With
 * governance off the projection is absent, the routes 404, and every other
 * surface here renders nothing — the degradation is the design, not an
 * accident.
 *
 * @module dsh-docs-harness/client
 */

import {
  DOCK_BUBBLE_ID,
  DOCK_BUBBLE_ORDER,
  DOCK_NOTICE_ID,
  DOCK_NOTICE_ORDER,
  FIELD_DISMISSED,
  LOCALE_NAMESPACE,
  SETTINGS_CARD_ID,
  SETTINGS_CARD_ORDER,
  TOOL_NAMES,
} from '../shared/constants.js';
import { EnableNoticeBar } from './EnableNoticeBar.jsx';
import { HarnessSettingsCard } from './HarnessSettingsCard.jsx';
import { PlanBubble } from './PlanBubble.jsx';
import { PlanToolCard } from './PlanToolCard.jsx';
import { en, zh } from './locales.js';
import { HarnessSettingsStore } from './settings-store.js';
import { installStyles } from './styles.js';

/** Slot names this plugin contributes to. */
const DOCK_SLOT = 'conversation.input.dock';
const TOOLVIEW_SLOT = 'tool.call.toolview';
const SETTINGS_SLOT = 'settings.plugin.item';

// Module-body side effect, matching how the upstream CSS-module pipeline
// behaves: the stylesheet lands at factory materialization, before any entry
// renders, and the loader removes plugin-owned tags on unload.
installStyles();

/** Cordis services this plugin's browser half requires. */
export const inject = ['slots', 'locale'];

/**
 * Mount the four seats.
 * @param {object} ctx - the browser plugin context.
 * @param {object} [config] - unused entry config.
 * @param {HarnessSettingsStore} [store] - injectable for tests; defaults to a live store.
 */
export function apply(ctx, config, store = new HarnessSettingsStore()) {
  ctx.effect(() => ctx.locale.register(LOCALE_NAMESPACE, { zh, en }), 'docs-harness: dictionaries');
  ctx.effect(() => {
    void store.load();
    return () => { store.dispose(); };
  }, 'docs-harness: settings store');
  const write = writer(store);
  const onDismiss = dismisser(store, write);

  ctx.slots.inject(DOCK_SLOT, function* () {
    yield ctx.slots.register({
      name: DOCK_SLOT,
      id: DOCK_BUBBLE_ID,
      order: DOCK_BUBBLE_ORDER,
      locale: LOCALE_NAMESPACE,
    }, PlanBubble);
    yield ctx.slots.register({
      name: DOCK_SLOT,
      id: DOCK_NOTICE_ID,
      order: DOCK_NOTICE_ORDER,
      locale: LOCALE_NAMESPACE,
      inject: () => ({ hooks: { harness: store }, onDismiss }),
    }, EnableNoticeBar);
  });

  ctx.slots.inject(TOOLVIEW_SLOT, function* () {
    // One registration per wire name: the slot is keyed, and an unregistered
    // key falls back to the generic JSON row rather than to a shared component.
    for (const key of TOOL_NAMES) {
      yield ctx.slots.register({ name: TOOLVIEW_SLOT, key, locale: LOCALE_NAMESPACE }, PlanToolCard);
    }
  });

  ctx.slots.inject(SETTINGS_SLOT, () => ctx.slots.register({
    name: SETTINGS_SLOT,
    id: SETTINGS_CARD_ID,
    order: SETTINGS_CARD_ORDER,
    locale: LOCALE_NAMESPACE,
    inject: () => ({ hooks: { harness: store }, write }),
  }, HarnessSettingsCard));
}

/**
 * Build the settings writer the cards call.
 * @param {{ set: (field: string, value: unknown) => Promise<void> }} store - the settings store.
 * @returns {(field: string, value: unknown) => Promise<{ ok: boolean, message?: string }>} the writer.
 */
export function writer(store) {
  return async (field, value) => {
    try {
      await store.set(field, value);
      return { ok: true };
    } catch (cause) {
      // A refused write leaves the previous snapshot in place, so the control
      // snaps back on the next render; this carries the reason back to the
      // surface that asked, instead of leaving the revert unexplained.
      return { ok: false, message: cause instanceof Error ? cause.message : String(cause) };
    }
  };
}

/**
 * Build the "do not ask again" writer.
 * @param {{ getSnapshot: () => { value?: { dismissed?: string[] } } }} store - the settings store.
 * @param {(field: string, value: unknown) => Promise<unknown>} write - the settings writer.
 * @returns {(dir: string) => void} appends one project root to the dismissal list.
 */
export function dismisser(store, write) {
  return (dir) => {
    const current = store.getSnapshot().value?.dismissed ?? [];
    if (current.includes(dir)) return;
    void write(FIELD_DISMISSED, [...current, dir]);
  };
}
