/**
 * What this plugin knows about one project on disk, read cheaply enough to run
 * on every prompt assembly.
 *
 * Two facts matter: whether Docs Harness is installed (and at which version),
 * and the exact governance text that project's AGENTS.md carries. Both are
 * cached against the file's mtime — a prompt assembly happens per model step,
 * and re-reading a 12 KB markdown file that many times is waste, while trusting
 * a cache that outlives an edit would inject stale rules.
 *
 * @module dsh-docs-harness/host/project-state
 */

import fs from 'node:fs';
import path from 'node:path';

import {
  CONFIG_RELATIVE,
  PROMPT_ENABLE,
  PROMPT_NONE,
  PROMPT_UPGRADE,
  RULES_CACHE_TTL_MS,
  RULES_FILE_RELATIVE,
} from '../shared/constants.js';
import { SEED_ENGINE, SEED_ROOT } from './engine.js';
import { readManagedBlock } from './managed-block.js';

/** Matches the engine's own `VERSION = "x.y.z"` declaration. */
const VERSION_PATTERN = /^VERSION\s*=\s*"([^"]+)"/m;

/** Matches the numeric x.y.z triple a release stamp starts with. */
const VERSION_TRIPLE = /^(\d+)\.(\d+)\.(\d+)/;

/**
 * Whether the installed stamp is strictly behind the seed — the only direction
 * an upgrade offer is honest in: the seed engine rewrites managed files with
 * its own content, so offering it against a newer project is a downgrade.
 * Segments compare numerically ("2.9" is older than "2.10", not newer as a
 * string compare would claim). A stamp without an x.y.z triple cannot be
 * ordered; those keep the plain mismatch rule so a damaged stamp still earns
 * the repair offer.
 * @param {string} installed - the project's version stamp.
 * @param {string} seed - the version this plugin ships.
 * @returns {boolean} whether an upgrade to the seed moves the project forward.
 */
export function versionBehind(installed, seed) {
  const own = installed.match(VERSION_TRIPLE);
  const next = seed.match(VERSION_TRIPLE);
  if (own === null || next === null) return installed !== seed;
  for (let part = 1; part <= 3; part += 1) {
    if (Number(own[part]) !== Number(next[part])) return Number(own[part]) < Number(next[part]);
  }
  return false;
}

/** Memoized seed version — the vendored file cannot change while the app runs. */
let seedVersionCache;

/**
 * The Docs Harness version this plugin ships as its installer source.
 * @returns {string | undefined} the seed version, or undefined when unreadable.
 */
export function seedVersion() {
  if (seedVersionCache !== undefined) return seedVersionCache || undefined;
  const declared = fs.readFileSync(SEED_ENGINE, 'utf8').match(VERSION_PATTERN);
  seedVersionCache = declared?.[1] ?? '';
  return seedVersionCache || undefined;
}

/** Absolute root of the vendored installer source, for `project init`. */
export { SEED_ROOT };

/**
 * @typedef {object} ProjectState
 * @property {boolean} enabled - whether the project carries an install stamp.
 * @property {string | null} projectVersion - the installed version, or null.
 * @property {string | null} seedVersion - the version this plugin would install.
 * @property {'none' | 'enable' | 'upgrade'} prompt - what the UI should offer.
 */

/**
 * Read one project's install state. Only the stamp file is touched, so this is
 * one `readFileSync` of a small JSON document in the common case and one failed
 * `stat` when Docs Harness was never installed.
 * @param {string} projectDir - absolute project root.
 * @returns {ProjectState} the detected state.
 */
export function detectProject(projectDir) {
  const seed = seedVersion() ?? null;
  const installed = readInstalledVersion(projectDir);
  if (installed === undefined) return { enabled: false, projectVersion: null, seedVersion: seed, prompt: PROMPT_ENABLE };
  const stale = seed !== null && versionBehind(installed, seed);
  return {
    enabled: true,
    projectVersion: installed,
    seedVersion: seed,
    prompt: stale ? PROMPT_UPGRADE : PROMPT_NONE,
  };
}

/**
 * The installed version stamp.
 * @param {string} projectDir - absolute project root.
 * @returns {string | undefined} the version, or undefined when not installed.
 */
function readInstalledVersion(projectDir) {
  let raw;
  try {
    raw = fs.readFileSync(path.join(projectDir, CONFIG_RELATIVE), 'utf8');
  } catch {
    // Not installed is the ordinary case for most projects, not a failure.
    return undefined;
  }
  const config = JSON.parse(raw);
  const version = config?.version;
  return typeof version === 'string' && version !== '' ? version : undefined;
}

/** mtime-and-size keyed cache of one project's extracted governance block. */
const rulesCache = new Map();

/**
 * The governance text for a project: its own AGENTS.md managed block, which is
 * the single source the engine wrote and the user's agents already read.
 *
 * Falls back to the seed copy of the same version's text when the file is gone
 * or its markers are broken — that is a damaged install, and refusing to inject
 * would silently drop governance the project is still stamped as having.
 * @param {string} projectDir - absolute project root.
 * @returns {{ text: string, source: 'project' | 'seed' } | undefined} the block, or undefined when neither is readable.
 */
export function readGovernanceRules(projectDir) {
  const file = path.join(projectDir, RULES_FILE_RELATIVE);
  const stamp = statStamp(file);
  const cached = rulesCache.get(projectDir);
  if (cached !== undefined && cached.stamp === stamp && Date.now() - cached.readAt < RULES_CACHE_TTL_MS) {
    return cached.value;
  }
  const value = loadGovernanceRules(file);
  rulesCache.set(projectDir, { stamp, readAt: Date.now(), value });
  return value;
}

/**
 * Read the block from the project, then from the seed.
 * @param {string} file - absolute AGENTS.md path.
 * @returns {{ text: string, source: 'project' | 'seed' } | undefined} the block, or undefined.
 */
function loadGovernanceRules(file) {
  const own = readBlockFrom(file);
  if (own !== undefined) return { text: own, source: 'project' };
  const seeded = readBlockFrom(path.join(SEED_ROOT, 'managed-entry.md'));
  return seeded === undefined ? undefined : { text: seeded, source: 'seed' };
}

/**
 * @param {string} file - absolute markdown path.
 * @returns {string | undefined} the managed block body, or undefined.
 */
function readBlockFrom(file) {
  let raw;
  try {
    raw = fs.readFileSync(file, 'utf8');
  } catch {
    // A damaged or absent file is the caller's fallback signal, not an error.
    return undefined;
  }
  return readManagedBlock(raw);
}

/**
 * Cheap change token for a file: mtime plus size, or a sentinel when absent.
 * @param {string} file - absolute path.
 * @returns {string} the token.
 */
function statStamp(file) {
  try {
    const info = fs.statSync(file);
    return `${info.mtimeMs}:${info.size}`;
  } catch {
    return 'absent';
  }
}

/** Drop every cached read (tests, and after a project-level write). */
export function resetProjectCaches() {
  rulesCache.clear();
  seedVersionCache = undefined;
}
