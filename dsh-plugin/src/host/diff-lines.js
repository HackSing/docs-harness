/**
 * Added/removed line counts folded out of the filesystem tools' result metadata.
 *
 * `write` and `edit` attach `{ diffs: FileDiff[] }`, one entry per applied hunk,
 * each carrying the changed lines plus three lines of context on either side
 * (`@deepseek-ai/dsh-tool-fs` DIFF_CONTEXT). Counting `newText`'s lines as
 * additions would therefore over-count every hunk by up to six.
 *
 * A hunk is one contiguous change, so its context is exactly the shared prefix
 * and suffix of the two texts. Trimming those leaves the change itself — an
 * exact count without running a diff algorithm.
 *
 * @module dsh-docs-harness/host/diff-lines
 */

/**
 * @typedef {object} DiffTotals
 * @property {number} added - lines introduced.
 * @property {number} removed - lines deleted.
 */

/** Neutral element — also the value a projection starts from. */
export const NO_DIFF = Object.freeze({ added: 0, removed: 0 });

/**
 * Count one hunk.
 * @param {{ oldText: string | null, newText: string }} diff - one applied hunk.
 * @returns {DiffTotals} that hunk's counts.
 */
export function countHunk(diff) {
  const after = splitLines(diff.newText);
  // A null `oldText` is a new file or a full overwrite: nothing to trim against.
  if (diff.oldText === null) return { added: after.length, removed: 0 };
  const before = splitLines(diff.oldText);
  const limit = Math.min(before.length, after.length);
  let prefix = 0;
  while (prefix < limit && before[prefix] === after[prefix]) prefix += 1;
  let suffix = 0;
  while (suffix < limit - prefix && before[before.length - 1 - suffix] === after[after.length - 1 - suffix]) {
    suffix += 1;
  }
  return { added: after.length - prefix - suffix, removed: before.length - prefix - suffix };
}

/**
 * Split into lines, treating a trailing newline as a terminator rather than as
 * an extra empty line.
 * @param {string} text - hunk text.
 * @returns {string[]} its lines.
 */
function splitLines(text) {
  if (text === '') return [];
  const lines = text.split('\n');
  if (lines[lines.length - 1] === '') lines.pop();
  return lines;
}

/**
 * Narrow opaque tool-result metadata to countable hunks.
 * @param {unknown} meta - the `tool/result` event's `meta` field.
 * @returns {{ oldText: string | null, newText: string }[]} the hunks, empty when the shape does not match.
 */
export function hunksFromMeta(meta) {
  if (typeof meta !== 'object' || meta === null) return [];
  const diffs = /** @type {{ diffs?: unknown }} */ (meta).diffs;
  if (!Array.isArray(diffs)) return [];
  return diffs.filter(entry =>
    typeof entry === 'object' && entry !== null
    && typeof entry.newText === 'string'
    && (entry.oldText === null || typeof entry.oldText === 'string'));
}

/**
 * Fold one tool result's hunks into a running total.
 * @param {DiffTotals} totals - the running total.
 * @param {unknown} meta - the `tool/result` event's `meta` field.
 * @returns {DiffTotals} the new total, or the same reference when nothing counted.
 */
export function addResultDiff(totals, meta) {
  const hunks = hunksFromMeta(meta);
  if (hunks.length === 0) return totals;
  let added = totals.added;
  let removed = totals.removed;
  for (const hunk of hunks) {
    const counts = countHunk(hunk);
    added += counts.added;
    removed += counts.removed;
  }
  return added === totals.added && removed === totals.removed ? totals : { added, removed };
}
