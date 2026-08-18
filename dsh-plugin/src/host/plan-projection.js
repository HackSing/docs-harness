/**
 * The standing plan projection: what the composer bubble and the plan card read.
 *
 * DESIGN CONSTRAINT — why this folds built-in events instead of its own.
 * A projection is driven only by committed session events, and the natural
 * move would be to append a `docs-harness/plan` event. Out-of-repo event types
 * are not survivable: session persistence refuses to interpret a log carrying a
 * type outside `KNOWN_SESSION_EVENT_TYPES` unless the envelope is marked
 * `ignorable`, and `Session.append` offers no way to set that marker. A session
 * that once carried such an event would fail to load after a restart — the
 * user's conversation, lost. So every fact here is folded out of this plugin's
 * OWN `tool/call` / `tool/result` events, which are built-in and durable.
 *
 * State moves on results, not calls: a rejected plan or a malformed
 * `plan_progress` throws before producing one, and the projection must not have
 * already moved. `tool/call` therefore only records which tool owns a call id.
 *
 * Standing, not per-turn: unlike the built-in todo list, a frozen plan outlives
 * the turn that created it, so there is deliberately no `turn/start` arm.
 *
 * @module dsh-docs-harness/host/plan-projection
 */

import { z as zod } from 'zod';

import {
  ITEM_STATUSES,
  PLAN_PROJECTION_KEY,
  PLAN_PROJECTION_STATE_VERSION,
  TOOL_PLAN_CREATE,
  TOOL_PLAN_PROGRESS,
  TOOL_PLAN_SETTLE,
} from '../shared/constants.js';
import { narrowItemsOf } from '../shared/plan-items.js';
import { NO_DIFF, addResultDiff } from './diff-lines.js';

/** The wire payload's schema; the registry validates every pushed frame against it. */
export const planProjectionSchema = zod.union([
  zod.null(),
  zod.object({
    status: zod.union([zod.literal('awaiting-approval'), zod.literal('running'), zod.literal('done')]),
    items: zod.array(zod.object({
      content: zod.string(),
      status: zod.union(ITEM_STATUSES.map(value => zod.literal(value))),
    })),
    done: zod.number(),
    total: zod.number(),
    diff: zod.object({ added: zod.number(), removed: zod.number() }),
  }),
]);

/** The empty fold — no plan has been frozen in this session. */
export const EMPTY_PLAN_STATE = Object.freeze({
  status: null,
  items: Object.freeze([]),
  diff: NO_DIFF,
  pending: Object.freeze({}),
});

/**
 * Fold one committed event into the plan state.
 *
 * Returns the SAME reference for every event this unit does not own — that
 * identity check is the registry's change gate, and allocating a fresh object
 * would push a frame to the browser on every unrelated event in the session.
 * @param {object} state - the fold covering all prior events.
 * @param {object} event - the next committed session event.
 * @returns {object} the next state, or `state` unchanged.
 */
export function applyPlanEvent(state, event) {
  if (event.type === 'tool/call') return rememberCall(state, event);
  if (event.type === 'tool/result') return applyResult(state, event);
  return state;
}

/**
 * Record which tool owns a call id, for the result that arrives later.
 * Only the ids this unit can act on are kept, so the map cannot grow with
 * unrelated tool traffic.
 * @param {object} state - current fold.
 * @param {object} event - a `tool/call` event.
 * @returns {object} the next state.
 */
function rememberCall(state, event) {
  const { callId, name } = event.data;
  const owned = name === TOOL_PLAN_CREATE || name === TOOL_PLAN_PROGRESS || name === TOOL_PLAN_SETTLE;
  if (!owned && state.status === null) return state;
  const pending = { ...state.pending, [callId]: name };
  // A plan under review is the one state a call alone establishes: the tool
  // parks inside `execute` awaiting the user, so its result is still minutes away.
  const status = name === TOOL_PLAN_CREATE ? 'awaiting-approval' : state.status;
  return { ...state, pending, status };
}

/**
 * Apply a settled tool call.
 * @param {object} state - current fold.
 * @param {object} event - a `tool/result` event.
 * @returns {object} the next state.
 */
function applyResult(state, event) {
  const callId = event.data.message?.source?.callId;
  const name = callId === undefined ? undefined : ownPending(state, callId);
  const pending = name === undefined ? state.pending : withoutCall(state.pending, callId);
  const failed = event.data.error !== undefined;
  if (name === TOOL_PLAN_CREATE) {
    // A declined review settles as a tool error; the plan never became active.
    return failed
      ? { ...EMPTY_PLAN_STATE, pending }
      : { ...state, pending, status: 'running', diff: NO_DIFF };
  }
  if (name === TOOL_PLAN_SETTLE && !failed) return { ...state, pending, status: 'done' };
  if (name === TOOL_PLAN_PROGRESS && !failed) {
    const items = narrowItemsOf(event.data.meta);
    return items === undefined ? { ...state, pending } : { ...state, pending, items, status: statusFor(items) };
  }
  // Any other settled tool may still have written files; count them while a
  // plan is active, so the bubble's ± tracks the work the plan is doing.
  const diff = state.status === null ? state.diff : addResultDiff(state.diff, event.data.meta);
  if (diff === state.diff && pending === state.pending) return state;
  return { ...state, pending, diff };
}

/**
 * @param {object} state - current fold.
 * @param {string} callId - the settling call.
 * @returns {string | undefined} the owning tool name, when this unit recorded it.
 */
function ownPending(state, callId) {
  return Object.hasOwn(state.pending, callId) ? state.pending[callId] : undefined;
}

/**
 * @param {Record<string, string>} pending - the call map.
 * @param {string} callId - the id to drop.
 * @returns {Record<string, string>} a copy without that id.
 */
function withoutCall(pending, callId) {
  const next = { ...pending };
  delete next[callId];
  return next;
}

/**
 * @param {{ status: string }[]} items - the whole list.
 * @returns {'running' | 'done'} whether anything is left to do.
 */
function statusFor(items) {
  return items.length > 0 && items.every(item => item.status === 'completed') ? 'done' : 'running';
}

/**
 * Project the fold onto the wire.
 * @param {object} state - the current fold.
 * @returns {object | null} the client-visible value.
 */
export function planProjectionView(state) {
  if (state.status === null) return null;
  return {
    status: state.status,
    items: state.items.map(item => ({ content: item.content, status: item.status })),
    done: state.items.filter(item => item.status === 'completed').length,
    total: state.items.length,
    diff: { added: state.diff.added, removed: state.diff.removed },
  };
}

/** The registration passed to `ctx.sessionProjections.register`. */
export const planProjectionDefinition = {
  key: PLAN_PROJECTION_KEY,
  schema: planProjectionSchema,
  init: () => EMPTY_PLAN_STATE,
  apply: applyPlanEvent,
  view: planProjectionView,
  stateVersion: PLAN_PROJECTION_STATE_VERSION,
};
