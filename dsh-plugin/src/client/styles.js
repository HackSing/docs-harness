/**
 * One stylesheet, injected once at factory execution.
 *
 * The upstream client build compiles CSS Modules through lightningcss and emits
 * exactly this shape — a `<style data-plugin=…>` tag written on first
 * evaluation. This package builds with esbuild instead, so it writes the same
 * tag by hand rather than pulling in a second toolchain to generate it.
 *
 * Every colour is a theme token. Hard-coding one would look correct in whatever
 * theme it was written against and wrong in the other.
 *
 * @module dsh-docs-harness/client/styles
 */

import { PACKAGE_NAME } from '../shared/constants.js';

/** Class names, so markup and stylesheet cannot drift apart silently. */
export const css = {
  bar: 'dh-bar',
  barText: 'dh-bar-text',
  barActions: 'dh-bar-actions',
  button: 'dh-button',
  buttonPrimary: 'dh-button-primary',
  spinner: 'dh-spinner',
  bubbleRow: 'dh-bubble-row',
  bubbleWrap: 'dh-bubble-wrap',
  bubble: 'dh-bubble',
  bubbleCount: 'dh-bubble-count',
  bubbleDiff: 'dh-bubble-diff',
  added: 'dh-added',
  removed: 'dh-removed',
  popover: 'dh-popover',
  list: 'dh-list',
  item: 'dh-item',
  itemMark: 'dh-item-mark',
  itemText: 'dh-item-text',
  card: 'dh-card',
  cardTitle: 'dh-card-title',
  cardRow: 'dh-card-row',
  cardHint: 'dh-card-hint',
  error: 'dh-error',
};

const SHEET = `
.${css.bar} {
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 0 auto;
  width: 100%;
  padding: 7px 12px;
  border: 1px solid var(--dsw-alias-border-l1);
  border-radius: 12px;
  background: var(--dsw-specific-tip, var(--dsw-alias-bg-layer-1));
  font-size: 13px;
  color: var(--dsw-alias-label-secondary);
}
.${css.barText} { flex: 1 1 auto; min-width: 0; }
.${css.barActions} { flex: none; display: flex; gap: 6px; }
.${css.button} {
  font: inherit;
  cursor: pointer;
  padding: 3px 10px;
  border-radius: 8px;
  border: 1px solid var(--dsw-alias-border-l2);
  background: transparent;
  color: var(--dsw-alias-label-secondary);
}
.${css.button}:hover:not(:disabled) { background: var(--dsw-alias-interactive-bg-hover); }
.${css.button}:disabled { cursor: default; opacity: 0.55; }
.${css.buttonPrimary} {
  border-color: transparent;
  background: var(--dsw-alias-brand-primary);
  color: var(--dsw-alias-bg-base);
}
.${css.spinner} {
  flex: none;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 1.5px solid var(--dsw-alias-border-l2);
  border-top-color: var(--dsw-alias-label-secondary);
  animation: dh-spin 0.8s linear infinite;
}
@keyframes dh-spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .${css.spinner} { animation: none; } }

.${css.bubbleRow} { display: flex; justify-content: center; width: 100%; }
.${css.bubbleWrap} { position: relative; display: inline-flex; }
.${css.bubble} {
  font: inherit;
  font-size: 12px;
  cursor: default;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 12px;
  border-radius: 999px;
  border: 1px solid var(--dsw-alias-border-l1);
  background: var(--dsw-specific-tip, var(--dsw-alias-bg-layer-1));
  color: var(--dsw-alias-label-secondary);
  box-shadow: 0 1px 4px rgb(0 0 0 / 12%);
}
.${css.bubbleCount} { font-variant-numeric: tabular-nums; color: var(--dsw-alias-label-primary); }
.${css.bubbleDiff} { font-variant-numeric: tabular-nums; }
.${css.added} { color: var(--dsw-alias-state-success-primary); }
.${css.removed} { color: var(--dsw-alias-state-error-primary); }
.${css.popover} {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 50%;
  transform: translateX(-50%);
  z-index: 40;
  min-width: 240px;
  max-width: min(420px, 80vw);
  max-height: 260px;
  overflow-y: auto;
  padding: 8px 10px;
  border: 1px solid var(--dsw-alias-border-l1);
  border-radius: 10px;
  background: var(--dsw-specific-tip, var(--dsw-alias-bg-layer-2));
  box-shadow: 0 4px 16px rgb(0 0 0 / 22%);
  text-align: left;
}
/* The 6px visual gap below the popover is intentionally NOT bridged in CSS:
   a pseudo-element stretched over it is clipped by this element's own
   overflow-y. PlanBubble closes on a short hover-intent delay instead. */
.${css.list} { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.${css.item} { display: flex; align-items: baseline; gap: 8px; font-size: 12px; }
.${css.itemMark} { flex: none; width: 1.2em; color: var(--dsw-alias-label-tertiary); }
.${css.item}[data-status="completed"] .${css.itemText} { color: var(--dsw-alias-label-tertiary); text-decoration: line-through; }
.${css.item}[data-status="in_progress"] .${css.itemText} { color: var(--dsw-alias-label-primary); }
.${css.item}[data-status="in_progress"] .${css.itemMark} { color: var(--dsw-alias-state-business-primary); }
.${css.itemText} { color: var(--dsw-alias-label-secondary); overflow-wrap: anywhere; }

.${css.card} {
  border: 1px solid var(--dsw-alias-border-l1);
  border-radius: 12px;
  padding: 12px 14px;
  background: var(--dsw-alias-bg-layer-1);
  color: var(--dsw-alias-label-secondary);
  font-size: 13px;
}
.${css.cardTitle} { font-weight: 600; color: var(--dsw-alias-label-primary); margin-bottom: 8px; }
.${css.cardRow} { display: flex; align-items: center; gap: 10px; padding: 6px 0; }
.${css.cardRow} label { flex: 1 1 auto; }
.${css.cardHint} { color: var(--dsw-alias-label-tertiary); font-size: 12px; }
.${css.error} { color: var(--dsw-alias-state-error-primary); }

.dh-sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  padding: 0;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
  border: 0;
}

/* Narrow composer: the pill keeps the counts and drops the ± readout. */
@media (max-width: 560px) {
  .${css.bubbleDiff} { display: none; }
}
`;

/** Idempotent: the loader may re-evaluate the factory after a hot reload. */
export function installStyles() {
  if (typeof document === 'undefined') return;
  const marker = `${PACKAGE_NAME}/styles`;
  if (document.querySelector(`style[data-plugin-css="${marker}"]`) !== null) return;
  const tag = document.createElement('style');
  tag.dataset.plugin = PACKAGE_NAME;
  tag.dataset.pluginCss = marker;
  tag.textContent = SHEET;
  document.head.appendChild(tag);
}
