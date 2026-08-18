/**
 * Locating the Docs Harness managed block inside a project's AGENTS.md.
 *
 * The markers are the engine's own constants (`scripts/harness.py`
 * MANAGED_BEGIN/MANAGED_END). The engine owns every write; this module only
 * reads, so a marker change upstream shows up as "no block found" and the
 * caller falls back to the seed text instead of corrupting the file.
 *
 * @module dsh-docs-harness/host/managed-block
 */

/** Opening marker of the AGENTS.md managed block. */
export const MANAGED_BEGIN = '<!-- docs-harness:managed-entry:start -->';

/** Closing marker of the AGENTS.md managed block. */
export const MANAGED_END = '<!-- docs-harness:managed-entry:end -->';

/**
 * Extract the block body between the markers.
 *
 * A file with zero, duplicated, or inverted markers yields `undefined` rather
 * than a guess: the engine treats those same shapes as a corrupt install and
 * refuses to write, so reading one is not a state this module can repair.
 * CRLF is normalized to LF first. The engine always writes LF, but a Windows
 * checkout with `core.autocrlf` hands back CRLF, and the injected rules must
 * be byte-identical to the seed text regardless of how the repo was cloned.
 * @param {string} text - full AGENTS.md contents.
 * @returns {string | undefined} the LF-normalized block body, without markers or their newlines.
 */
export function readManagedBlock(raw) {
  const text = raw.replace(/\r\n/g, '\n');
  const begin = text.indexOf(MANAGED_BEGIN);
  const end = text.indexOf(MANAGED_END);
  if (begin < 0 || end < 0 || begin > end) return undefined;
  if (text.indexOf(MANAGED_BEGIN, begin + 1) >= 0) return undefined;
  if (text.indexOf(MANAGED_END, end + 1) >= 0) return undefined;
  return text.slice(begin + MANAGED_BEGIN.length, end).replace(/^\n/, '').replace(/\n$/, '');
}
