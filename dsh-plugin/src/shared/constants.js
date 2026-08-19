/**
 * Single source for every business default, wire name, and key this plugin
 * owns. Nothing else in the package may spell one of these literals: a default
 * changed here changes everywhere, and a rename is one edit.
 *
 * This module is bundled into the browser artifact as well, so it must stay
 * free of `node:` imports and of anything that touches the filesystem.
 *
 * @module dsh-docs-harness/host/constants
 */

/** npm package name, also the cordis roster row name and the client bundle id. */
export const PACKAGE_NAME = '@aiwaretop/dsh-docs-harness';

/** Settings namespace owned by this plugin (the registry enforces `[a-z][a-z0-9-]*`). */
export const SETTINGS_NAMESPACE = 'docs-harness';

/** Governance master switch default — on, so the capability ships usable. */
export const DEFAULT_GOVERNANCE_ENABLED = true;

/** Auto-enable default — off, so a first-seen project only ever gets a prompt. */
export const DEFAULT_AUTO_ENABLE = false;

/** Auto-upgrade default — off, same reason. */
export const DEFAULT_AUTO_UPGRADE = false;

/** Projection key carrying the standing plan. */
export const PLAN_PROJECTION_KEY = 'harnessPlan';

/** Persisted-cache invalidation version of the plan projection's state shape. */
export const PLAN_PROJECTION_STATE_VERSION = 1;

/** Prompt section name; must be unique across every loaded plugin. */
export const RULES_SECTION_NAME = 'docs-harness:governance';

/**
 * Prompt order. Tool guidance occupies 100–199 by convention; governance rules
 * are read after the persona and before per-tool guidance.
 */
export const RULES_SECTION_ORDER = 90;

/** Model-facing tool names. */
export const TOOL_PLAN_SELECT = 'harness_plan_select';
export const TOOL_PLAN_CREATE = 'harness_plan_create';
export const TOOL_PLAN_SETTLE = 'harness_plan_settle';
export const TOOL_PLAN_PROGRESS = 'plan_progress';

/** Every tool this plugin registers, in registration order. */
export const TOOL_NAMES = [TOOL_PLAN_SELECT, TOOL_PLAN_CREATE, TOOL_PLAN_SETTLE, TOOL_PLAN_PROGRESS];

/** HTTP route prefix for the project-level operations the UI triggers. */
export const ROUTE_PREFIX = '/docs-harness';

/**
 * HTTP route prefix for this plugin's own settings surface. A SIBLING of
 * {@link ROUTE_PREFIX}, not a child: the project routes live on the gated
 * governance fiber while these must survive the master switch being off (they
 * are how it is turned back on), and two prefix registrations must never
 * overlap. They exist at all because the upstream gateway serves settings only
 * for an allowlist of namespaces it compiles in — a third-party namespace is
 * filtered from `settings.describe` and refused on write, so the generic
 * settings transport can never carry this plugin's switches.
 */
export const SETTINGS_ROUTE_PREFIX = '/docs-harness-settings';

/** Settings route actions. */
export const ACTION_SETTINGS_READ = 'read';
export const ACTION_SETTINGS_WRITE = 'write';

/** Read-only route action: report whether this project is prepared, and how. */
export const ACTION_STATUS = 'status';

/** Write route actions; each maps to one engine invocation host-side. */
export const ACTION_INIT = 'init';
export const ACTION_UPGRADE = 'upgrade';
export const ACTION_UNINSTALL = 'uninstall';

/**
 * Notice-bar prompt states `detectProject` reports. `none` means the bar has
 * nothing to say, which is the state a healthy prepared project sits in.
 */
export const PROMPT_NONE = 'none';
export const PROMPT_ENABLE = 'enable';
export const PROMPT_UPGRADE = 'upgrade';

/** Locale namespace this plugin's client half registers its dictionaries under. */
export const LOCALE_NAMESPACE = 'docs-harness';

/** Slot entry ids and dock positions (0/10/20 are taken by todo/goal/queue). */
export const DOCK_BUBBLE_ID = 'docs-harness-plan';
export const DOCK_BUBBLE_ORDER = 30;
export const DOCK_NOTICE_ID = 'docs-harness-notice';
export const DOCK_NOTICE_ORDER = 40;
export const SETTINGS_CARD_ORDER = 30;

/** Settings fields the client writes; the host schema is their single definition. */
export const FIELD_GOVERNANCE = 'governance';
export const FIELD_AUTO_ENABLE = 'autoEnable';
export const FIELD_AUTO_UPGRADE = 'autoUpgrade';
export const FIELD_DISMISSED = 'dismissed';

/**
 * Wire-boundary shape of each writable settings field, keyed by field name.
 * The settings write route validates against this table before touching the
 * settings service; the host schema stays the single source of defaults.
 * @type {Record<string, (value: unknown) => boolean>}
 */
export const SETTINGS_FIELD_GUARDS = {
  [FIELD_GOVERNANCE]: value => typeof value === 'boolean',
  [FIELD_AUTO_ENABLE]: value => typeof value === 'boolean',
  [FIELD_AUTO_UPGRADE]: value => typeof value === 'boolean',
  [FIELD_DISMISSED]: value => Array.isArray(value) && value.every(item => typeof item === 'string'),
};

/** Project-relative path of the engine's install stamp. */
export const CONFIG_RELATIVE = '.docs-harness/config.json';

/** Project-relative path of the file whose managed block carries the rules. */
export const RULES_FILE_RELATIVE = 'AGENTS.md';

/** Project-relative path of the engine copy a tool call prefers over the seed. */
export const PROJECT_ENGINE_RELATIVE = 'scripts/harness.py';

/** Item statuses `plan_progress` accepts, mirroring the built-in todo vocabulary. */
export const ITEM_STATUSES = ['pending', 'in_progress', 'completed'];

/** How long a cached AGENTS.md read stays trusted without re-stat'ing (ms). */
export const RULES_CACHE_TTL_MS = 2_000;

/** Wall-clock budget for one engine subprocess (ms). */
export const ENGINE_TIMEOUT_MS = 120_000;

/**
 * Engine exit codes that still carry a usable JSON payload. 0 is plain
 * success; 3 means the write landed but the files are not committed yet
 * (`delivery_status: pending_commit`), which is normal right after an install.
 */
export const ENGINE_SOFT_EXIT_CODES = [0, 3];

/** Interpreter candidates tried in order when spawning the engine. */
export const PYTHON_CANDIDATES = ['python3', 'python'];

/** Shown whenever no interpreter answered — the user must fix this themselves. */
export const PYTHON_MISSING_HINT =
  'Docs Harness needs Python 3 on PATH (tried: '
  + `${PYTHON_CANDIDATES.join(', ')}). Install Python 3.10+ from https://www.python.org/downloads/ `
  + 'and restart the app.';

/** Returned to the model when it reaches for a plan tool in an unprepared project. */
export const NOT_ENABLED_HINT =
  'Docs Harness is not enabled for this project, so no plan can be frozen here. '
  + 'Do NOT enable it yourself: enabling writes files into the user\'s repository and only '
  + 'the user may start it, from the "Enable Docs Harness" bar above the composer or from '
  + 'Settings → Plugins → Docs Harness. Tell the user that, then continue the task without '
  + 'the plan tools.';
