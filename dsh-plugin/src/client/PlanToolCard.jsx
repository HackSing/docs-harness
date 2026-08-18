/**
 * The tool view for this plugin's own calls.
 *
 * Registered per tool name on `tool.call.toolview`; an unclaimed name would
 * fall back to the generic JSON row, which for `plan_progress` would print the
 * whole checklist as raw arguments. The card reads the checklist from the
 * settled result's metadata when it exists and from the call arguments while
 * the call is still running, so a long step still shows what it is working
 * through.
 *
 * @module dsh-docs-harness/client/PlanToolCard
 */

import { narrowItemsOf } from '../shared/plan-items.js';
import { PlanItemList } from './PlanItemList.jsx';
import { css } from './styles.js';

/**
 * @param {object} props - composed slot props.
 * @param {string} props.toolName - the wire tool name this card was dispatched for.
 * @param {object} props.block - the running call or the settled result node.
 * @param {(key: string, params?: Record<string, unknown>) => string} props.t - translator.
 * @returns {import('react').ReactElement} the card.
 */
export function PlanToolCard({ toolName, block, t }) {
  const items = itemsOf(block);
  return (
    <div className={css.card} data-docs-harness-tool={toolName}>
      <div className={css.cardTitle}>{t(`card.${toolName}`)}</div>
      {items.length === 0 ? null : <PlanItemList items={items} t={t} />}
    </div>
  );
}

/**
 * The checklist this call carries, from whichever side of the call has it.
 * @param {object} block - the running call or settled result node.
 * @returns {{ content: string, status: string }[]} the items, empty when the call carries none.
 */
export function itemsOf(block) {
  const settled = narrowItemsOf(block.meta);
  if (settled !== undefined) return settled;
  const argsRaw = block.argsRaw ?? block.call?.argsRaw;
  if (typeof argsRaw !== 'string') return [];
  let parsed;
  try {
    parsed = JSON.parse(argsRaw);
  } catch {
    // Arguments stream in token by token: an incomplete JSON prefix is the
    // ordinary running state, not a fault, and the card simply has nothing to
    // show yet.
    return [];
  }
  return narrowItemsOf(parsed) ?? [];
}
