import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  EMPTY_PLAN_STATE,
  applyPlanEvent,
  planProjectionDefinition,
  planProjectionSchema,
  planProjectionView,
} from '../src/host/plan-projection.js';
import {
  TOOL_PLAN_CREATE,
  TOOL_PLAN_PROGRESS,
  TOOL_PLAN_SETTLE,
} from '../src/shared/constants.js';

/** @returns {object} a `tool/call` event. */
const call = (callId, name) => ({ type: 'tool/call', seq: 1, data: { callId, name, arguments: '{}' } });

/** @returns {object} a `tool/result` event. */
const result = (callId, extra = {}) => ({
  type: 'tool/result',
  seq: 2,
  data: { message: { source: { callId } }, ...extra },
});

/**
 * Fold a list of events from the empty state.
 * @param {object[]} events - events in log order.
 * @returns {object} the final state.
 */
function fold(events) {
  return events.reduce(applyPlanEvent, EMPTY_PLAN_STATE);
}

const ITEMS = [
  { content: 'batch 1', status: 'completed' },
  { content: 'batch 2', status: 'in_progress' },
  { content: 'batch 3', status: 'pending' },
];

describe('plan projection', () => {
  it('starts absent, so the bubble does not render', () => {
    assert.equal(planProjectionView(EMPTY_PLAN_STATE), null);
  });

  it('ignores unrelated events by identity (the registry change gate)', () => {
    for (const event of [{ type: 'turn/start', data: {} }, { type: 'assistant/message', data: {} }]) {
      assert.equal(applyPlanEvent(EMPTY_PLAN_STATE, event), EMPTY_PLAN_STATE);
    }
  });

  it('enters awaiting-approval on the plan_create CALL, before any result exists', () => {
    const state = fold([call('c1', TOOL_PLAN_CREATE)]);
    assert.equal(planProjectionView(state).status, 'awaiting-approval');
  });

  it('returns to absent when the user declines (the tool settles as an error)', () => {
    const state = fold([
      call('c1', TOOL_PLAN_CREATE),
      result('c1', { error: { name: 'Error', code: 'declined' } }),
    ]);
    assert.equal(planProjectionView(state), null);
  });

  it('runs once approved, then tracks the whole list from plan_progress results', () => {
    const state = fold([
      call('c1', TOOL_PLAN_CREATE),
      result('c1', { meta: {} }),
      call('c2', TOOL_PLAN_PROGRESS),
      result('c2', { meta: { items: ITEMS } }),
    ]);
    const view = planProjectionView(state);
    assert.equal(view.status, 'running');
    assert.equal(view.done, 1);
    assert.equal(view.total, 3);
    assert.deepEqual(view.items, ITEMS);
  });

  it('replaces the list wholesale rather than merging', () => {
    const state = fold([
      call('c1', TOOL_PLAN_CREATE),
      result('c1', { meta: {} }),
      call('c2', TOOL_PLAN_PROGRESS),
      result('c2', { meta: { items: ITEMS } }),
      call('c3', TOOL_PLAN_PROGRESS),
      result('c3', { meta: { items: [{ content: 'only', status: 'pending' }] } }),
    ]);
    assert.equal(planProjectionView(state).total, 1);
  });

  it('reaches done when every item is completed', () => {
    const state = fold([
      call('c1', TOOL_PLAN_CREATE),
      result('c1', { meta: {} }),
      call('c2', TOOL_PLAN_PROGRESS),
      result('c2', { meta: { items: [{ content: 'a', status: 'completed' }] } }),
    ]);
    assert.equal(planProjectionView(state).status, 'done');
  });

  it('reaches done on a successful settle even with work still listed', () => {
    const state = fold([
      call('c1', TOOL_PLAN_CREATE),
      result('c1', { meta: {} }),
      call('c2', TOOL_PLAN_PROGRESS),
      result('c2', { meta: { items: ITEMS } }),
      call('c3', TOOL_PLAN_SETTLE),
      result('c3', { meta: {} }),
    ]);
    assert.equal(planProjectionView(state).status, 'done');
  });

  it('ignores a malformed plan_progress payload instead of corrupting the list', () => {
    const good = fold([
      call('c1', TOOL_PLAN_CREATE),
      result('c1', { meta: {} }),
      call('c2', TOOL_PLAN_PROGRESS),
      result('c2', { meta: { items: ITEMS } }),
    ]);
    const after = fold([
      call('c1', TOOL_PLAN_CREATE),
      result('c1', { meta: {} }),
      call('c2', TOOL_PLAN_PROGRESS),
      result('c2', { meta: { items: ITEMS } }),
      call('c3', TOOL_PLAN_PROGRESS),
      result('c3', { meta: { items: [{ content: 'x', status: 'bogus' }] } }),
    ]);
    assert.deepEqual(planProjectionView(after).items, planProjectionView(good).items);
  });

  it('accumulates written lines only while a plan is active', () => {
    const before = fold([result('w0', { meta: { diffs: [{ oldText: null, newText: 'a\nb\n' }] } })]);
    assert.equal(planProjectionView(before), null);

    const during = fold([
      call('c1', TOOL_PLAN_CREATE),
      result('c1', { meta: {} }),
      result('w1', { meta: { diffs: [{ oldText: null, newText: 'a\nb\n' }] } }),
      result('w2', { meta: { diffs: [{ oldText: 'x\ny\n', newText: 'x\n' }] } }),
    ]);
    assert.deepEqual(planProjectionView(during).diff, { added: 2, removed: 1 });
  });

  it('resets the line counts when a new plan is approved', () => {
    const state = fold([
      call('c1', TOOL_PLAN_CREATE),
      result('c1', { meta: {} }),
      result('w1', { meta: { diffs: [{ oldText: null, newText: 'a\n' }] } }),
      call('c2', TOOL_PLAN_CREATE),
      result('c2', { meta: {} }),
    ]);
    assert.deepEqual(planProjectionView(state).diff, { added: 0, removed: 0 });
  });

  it('does not retain call ids after they settle', () => {
    const state = fold([call('c1', TOOL_PLAN_CREATE), result('c1', { meta: {} })]);
    assert.deepEqual(Object.keys(state.pending), []);
  });

  it('emits a payload its own schema accepts, in every reachable status', () => {
    const states = [
      fold([call('c1', TOOL_PLAN_CREATE)]),
      fold([call('c1', TOOL_PLAN_CREATE), result('c1', { meta: {} })]),
      fold([
        call('c1', TOOL_PLAN_CREATE),
        result('c1', { meta: {} }),
        call('c2', TOOL_PLAN_PROGRESS),
        result('c2', { meta: { items: ITEMS } }),
      ]),
      EMPTY_PLAN_STATE,
    ];
    for (const state of states) {
      planProjectionSchema.parse(planProjectionView(state));
    }
  });

  it('is registered as a standing unit: no turn/start clear', () => {
    const running = fold([
      call('c1', TOOL_PLAN_CREATE),
      result('c1', { meta: {} }),
      call('c2', TOOL_PLAN_PROGRESS),
      result('c2', { meta: { items: ITEMS } }),
    ]);
    const next = applyPlanEvent(running, { type: 'turn/start', seq: 9, data: {} });
    assert.equal(next, running);
    assert.equal(planProjectionView(next).total, 3);
  });

  it('exposes the registration shape the registry requires', () => {
    assert.equal(planProjectionDefinition.key, 'harnessPlan');
    assert.equal(typeof planProjectionDefinition.init, 'function');
    assert.equal(typeof planProjectionDefinition.apply, 'function');
    assert.equal(typeof planProjectionDefinition.view, 'function');
    assert.ok(Number.isInteger(planProjectionDefinition.stateVersion));
    assert.ok(planProjectionDefinition.stateVersion >= 0);
  });
});
