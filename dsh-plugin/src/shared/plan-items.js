/**
 * The one narrowing for a plan checklist.
 *
 * The same list crosses three boundaries — the tool's own validation, the
 * projection folding a result's metadata, and the browser reading either a
 * settled result or an in-flight argument blob. Each boundary is untrusted for
 * its own reason (a model wrote it; a persisted log may predate a schema
 * change; a streamed argument string may be a half-parsed prefix), and all
 * three ask exactly the same question, so they ask it here.
 *
 * @module dsh-docs-harness/shared/plan-items
 */

import { ITEM_STATUSES } from './constants.js';

/**
 * Narrow an unknown value to a plan checklist.
 * @param {unknown} value - a candidate item array.
 * @returns {{ content: string, status: string }[] | undefined} the copied list, or undefined when the shape does not match.
 */
export function narrowItems(value) {
  if (!Array.isArray(value)) return undefined;
  const valid = value.every(item =>
    typeof item === 'object' && item !== null
    && typeof item.content === 'string' && ITEM_STATUSES.includes(item.status));
  return valid ? value.map(item => ({ content: item.content, status: item.status })) : undefined;
}

/**
 * Narrow the `items` field of a metadata or argument object.
 * @param {unknown} carrier - the object expected to hold an `items` field.
 * @returns {{ content: string, status: string }[] | undefined} the list, or undefined.
 */
export function narrowItemsOf(carrier) {
  if (typeof carrier !== 'object' || carrier === null) return undefined;
  return narrowItems(/** @type {{ items?: unknown }} */ (carrier).items);
}
