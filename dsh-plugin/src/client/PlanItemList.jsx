/**
 * The plan checklist, rendered identically wherever it appears — inside the
 * bubble's popover and inside the `plan_progress` tool card. One component so
 * the two surfaces cannot drift into two different vocabularies for the same
 * three statuses.
 *
 * @module dsh-docs-harness/client/PlanItemList
 */

import { ITEM_STATUSES } from '../shared/constants.js';
import { css } from './styles.js';

/**
 * Leading glyph per status. Text rather than icons: the package ships no icon
 * assets, and these read correctly to a screen reader only because every row
 * also carries the translated status as its accessible name.
 */
const GLYPHS = { pending: '○', in_progress: '◐', completed: '●' };

/**
 * @param {object} props - component props.
 * @param {{ content: string, status: string }[]} props.items - the whole list, in plan order.
 * @param {(key: string) => string} props.t - namespace-bound translator.
 * @returns {import('react').ReactElement | null} the list, or null when there is nothing to show.
 */
export function PlanItemList({ items, t }) {
  if (items.length === 0) return null;
  return (
    <ul className={css.list}>
      {items.map((item, index) => (
        <li
          key={`${String(index)}:${item.content}`}
          className={css.item}
          data-status={ITEM_STATUSES.includes(item.status) ? item.status : undefined}
        >
          <span className={css.itemMark} aria-hidden="true">{GLYPHS[item.status] ?? GLYPHS.pending}</span>
          <span className={css.itemText}>
            <span className="dh-sr-only">{`${t(`status.${item.status}`)}: `}</span>
            {item.content}
          </span>
        </li>
      ))}
    </ul>
  );
}
