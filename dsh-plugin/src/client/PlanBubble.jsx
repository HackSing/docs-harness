/**
 * The standing plan bubble: a small centered pill above the composer that says
 * what the frozen plan is doing right now, and expands to the item list on
 * hover or keyboard focus. A click pins the popover open (hover leave and blur
 * no longer close it) until Esc or a second click releases it.
 *
 * It reads `useProjection('harnessPlan')` and owns no state beyond "is the
 * popover open". A plugin surface that cached the plan itself would be a second
 * copy of a value the framework already pushes; absence (`undefined`) and "no
 * plan" (`null`) both render nothing, which is also what happens when the
 * governance switch is off and the host registers no projection at all.
 *
 * @module dsh-docs-harness/client/PlanBubble
 */

import { useCallback, useEffect, useId, useRef, useState } from 'react';

import { PLAN_PROJECTION_KEY } from '../shared/constants.js';
import { PlanItemList } from './PlanItemList.jsx';
import { css } from './styles.js';

/**
 * Milliseconds the popover tolerates the pointer being outside the wrap.
 * A hover bridge cannot cover the 6px visual gap below the popover — the
 * popover's own `overflow-y: auto` clips any pseudo-element stretched over it —
 * and diagonal pointer paths leave through the sides anyway. A short close
 * delay (classic hover intent) survives every real pointer path, while a
 * genuine departure still closes the popover promptly.
 */
const CLOSE_DELAY_MS = 180;

/**
 * The pill's headline for one projected plan.
 * @param {{ status: string, done: number, total: number }} plan - the projected value.
 * @param {(key: string, params?: Record<string, unknown>) => string} t - translator.
 * @returns {string} the headline text.
 */
function headline(plan, t) {
  if (plan.status === 'awaiting-approval') return t('bubble.review');
  if (plan.status === 'done') return t('bubble.done');
  if (plan.total === 0) return t('bubble.active');
  return t('bubble.progress', { done: plan.done, total: plan.total });
}

/**
 * @param {object} props - composed slot props.
 * @param {(key: string) => unknown} props.useProjection - framework projection reader.
 * @param {(key: string, params?: Record<string, unknown>) => string} props.t - translator.
 * @returns {import('react').ReactElement | null} the pill, or null when no plan stands.
 */
export function PlanBubble({ useProjection, t }) {
  const plan = /** @type {any} */ (useProjection(PLAN_PROJECTION_KEY));
  const [open, setOpen] = useState(false);
  // Pinned = the popover survives hover leave and blur until Esc or a second
  // click; a hover-only popover drops long checklists the moment the pointer
  // drifts, which is exactly when the user is reading them.
  const [pinned, setPinned] = useState(false);
  const listId = useId();
  const closeTimer = useRef(/** @type {ReturnType<typeof setTimeout> | undefined} */ (undefined));
  const cancelClose = useCallback(() => { clearTimeout(closeTimer.current); }, []);
  const show = useCallback(() => { cancelClose(); setOpen(true); }, [cancelClose]);
  const close = useCallback(() => { cancelClose(); setPinned(false); setOpen(false); }, [cancelClose]);
  const scheduleClose = useCallback(() => {
    cancelClose();
    if (pinned) return;
    closeTimer.current = setTimeout(() => { setOpen(false); }, CLOSE_DELAY_MS);
  }, [cancelClose, pinned]);
  const toggle = useCallback(() => {
    cancelClose();
    if (pinned) {
      setPinned(false);
      setOpen(false);
    } else {
      setPinned(true);
      setOpen(true);
    }
  }, [cancelClose, pinned]);
  const onKeyDown = useCallback((event) => {
    if (event.key === 'Escape') close();
  }, [close]);
  useEffect(() => cancelClose, [cancelClose]);

  if (plan === undefined || plan === null) return null;

  const text = headline(plan, t);
  const diff = plan.diff.added > 0 || plan.diff.removed > 0 ? plan.diff : undefined;
  const diffText = diff === undefined ? '' : t('bubble.diff', diff);
  const expandable = plan.items.length > 0;
  const expanded = expandable && open;

  return (
    <div className={css.bubbleRow} data-docs-harness-plan={plan.status}>
      <div
        className={css.bubbleWrap}
        onMouseEnter={expandable ? show : undefined}
        onMouseLeave={expandable ? scheduleClose : undefined}
      >
        <button
          type="button"
          className={css.bubble}
          aria-label={diffText === '' ? text : `${text} · ${diffText}`}
          aria-expanded={expandable ? expanded : undefined}
          aria-pressed={expandable ? pinned : undefined}
          aria-controls={expanded ? listId : undefined}
          onFocus={expandable ? show : undefined}
          onBlur={expandable && !pinned ? close : undefined}
          onClick={expandable ? toggle : undefined}
          onKeyDown={onKeyDown}
          title={expandable ? t('bubble.expand') : undefined}
        >
          <span className={css.bubbleCount}>{text}</span>
          {diff === undefined ? null : (
            <span className={css.bubbleDiff} aria-hidden="true">
              <span className={css.added}>{`+${String(diff.added)}`}</span>
              {' '}
              <span className={css.removed}>{`-${String(diff.removed)}`}</span>
            </span>
          )}
        </button>
        {expanded ? (
          <div className={css.popover} id={listId} role="note">
            <PlanItemList items={plan.items} t={t} />
          </div>
        ) : null}
      </div>
    </div>
  );
}
