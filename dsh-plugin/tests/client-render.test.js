/**
 * What each surface actually renders.
 *
 * Server rendering runs no effects, so these cover exactly the part that is a
 * pure function of props — which is where the decisions live: whether a surface
 * appears at all, what it says, and whether an action is reachable.
 */
import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, it } from 'node:test';

import { PROMPT_ENABLE, PROMPT_UPGRADE, TOOL_PLAN_PROGRESS } from '../src/shared/constants.js';
import { HarnessSettingsCard } from '../src/client/HarnessSettingsCard.jsx';
import { NoticeBarView } from '../src/client/EnableNoticeBar.jsx';
import { PlanBubble } from '../src/client/PlanBubble.jsx';
import { PlanToolCard } from '../src/client/PlanToolCard.jsx';

/** Identity translator: the assertions then read as the keys the UI asked for. */
const t = (key, params) => (params === undefined ? key : `${key}(${JSON.stringify(params)})`);

/**
 * @param {Function} component - the component under test.
 * @param {object} props - its props.
 * @returns {string} the static markup.
 */
const render = (component, props) => renderToStaticMarkup(createElement(component, props));

/**
 * @param {object | null | undefined} plan - the projected plan value.
 * @returns {Function} a `useProjection` stub returning it.
 */
const projecting = plan => () => plan;

/**
 * @param {string} status - the plan status.
 * @param {object[]} items - the checklist.
 * @param {object} [diff] - the folded diff counts.
 * @returns {object} a projected plan value.
 */
const planValue = (status, items, diff = { added: 0, removed: 0 }) => ({
  status,
  items,
  done: items.filter(item => item.status === 'completed').length,
  total: items.length,
  diff,
});

describe('plan bubble', () => {
  it('renders nothing when the capability is absent', () => {
    assert.equal(render(PlanBubble, { useProjection: projecting(undefined), t }), '');
  });

  it('renders nothing when no plan was ever frozen', () => {
    assert.equal(render(PlanBubble, { useProjection: projecting(null), t }), '');
  });

  it('counts progress against the whole list', () => {
    const items = [
      { content: 'a', status: 'completed' },
      { content: 'b', status: 'in_progress' },
      { content: 'c', status: 'pending' },
    ];
    const html = render(PlanBubble, { useProjection: projecting(planValue('running', items)), t });
    assert.match(html, /bubble\.progress\(\{&quot;done&quot;:1,&quot;total&quot;:3\}\)/);
  });

  it('says a plan is waiting for review before counting anything', () => {
    const html = render(PlanBubble, { useProjection: projecting(planValue('awaiting-approval', [])), t });
    assert.match(html, /bubble\.review/);
    assert.doesNotMatch(html, /bubble\.progress/);
  });

  it('shows the folded diff, and hides it when nothing was written', () => {
    const items = [{ content: 'a', status: 'pending' }];
    const withDiff = render(PlanBubble, { useProjection: projecting(planValue('running', items, { added: 12, removed: 3 })), t });
    assert.match(withDiff, /\+12/);
    assert.match(withDiff, /-3/);
    const without = render(PlanBubble, { useProjection: projecting(planValue('running', items)), t });
    assert.doesNotMatch(without, /dh-bubble-diff/);
  });

  it('is not announced as expandable when there is nothing to expand', () => {
    const html = render(PlanBubble, { useProjection: projecting(planValue('done', [])), t });
    assert.doesNotMatch(html, /aria-expanded/);
  });

  it('names the whole readout for a screen reader', () => {
    const items = [{ content: 'a', status: 'pending' }];
    const html = render(PlanBubble, { useProjection: projecting(planValue('running', items, { added: 1, removed: 1 })), t });
    assert.match(html, /aria-label="[^"]*bubble\.diff/);
  });
});

describe('plan tool card', () => {
  it('renders the checklist a settled call published as metadata', () => {
    const block = { kind: 'tool-result', meta: { items: [{ content: 'ship it', status: 'completed' }] } };
    const html = render(PlanToolCard, { toolName: TOOL_PLAN_PROGRESS, block, t });
    assert.match(html, /ship it/);
    assert.match(html, /card\.plan_progress/);
  });

  it('falls back to the arguments while the call is still running', () => {
    const block = { callId: '1', name: TOOL_PLAN_PROGRESS, argsRaw: JSON.stringify({ items: [{ content: 'in flight', status: 'in_progress' }] }) };
    assert.match(render(PlanToolCard, { toolName: TOOL_PLAN_PROGRESS, block, t }), /in flight/);
  });

  it('shows the bare title rather than crashing on a half-streamed argument blob', () => {
    const block = { callId: '1', name: TOOL_PLAN_PROGRESS, argsRaw: '{"items":[{"content":"hal' };
    const html = render(PlanToolCard, { toolName: TOOL_PLAN_PROGRESS, block, t });
    assert.match(html, /card\.plan_progress/);
    assert.doesNotMatch(html, /dh-card-hint/);
  });

  it('ignores a malformed item list instead of rendering half of it', () => {
    const block = { kind: 'tool-result', meta: { items: [{ content: 'ok', status: 'completed' }, { status: 'nope' }] } };
    const html = render(PlanToolCard, { toolName: TOOL_PLAN_PROGRESS, block, t });
    assert.match(html, /card\.plan_progress/);
    assert.doesNotMatch(html, /dh-card-hint/);
    assert.doesNotMatch(html, /ok/);
  });
});

describe('notice bar view', () => {
  it('shows nothing at all when there is nothing to offer', () => {
    assert.equal(render(NoticeBarView, { notice: { prompt: undefined }, working: false, t }), '');
  });

  it('offers the enable action', () => {
    const html = render(NoticeBarView, { notice: { prompt: PROMPT_ENABLE, dir: 'D:/w' }, working: false, t });
    assert.match(html, /notice\.enable\.action/);
    assert.match(html, /notice\.dismiss/);
  });

  it('names both versions when offering an upgrade', () => {
    const notice = { prompt: PROMPT_UPGRADE, dir: 'D:/w', versions: { from: '2.7.0', to: '2.8.0' } };
    assert.match(render(NoticeBarView, { notice, working: false, t }), /2\.7\.0/);
  });

  it('disables its actions and marks itself busy while writing', () => {
    const html = render(NoticeBarView, { notice: { prompt: PROMPT_ENABLE, dir: 'D:/w' }, working: true, t });
    assert.match(html, /aria-busy="true"/);
    assert.equal(html.match(/disabled/g)?.length, 2);
    assert.match(html, /notice\.working/);
  });

  it('reports a failure without offering an action that just failed', () => {
    const html = render(NoticeBarView, { notice: { error: 'boom' }, working: false, t });
    assert.match(html, /notice\.failed/);
    assert.doesNotMatch(html, /<button/);
  });
});

describe('settings card', () => {
  /**
   * @param {object} snapshot - the settings-scope snapshot to serve.
   * @param {string} [current] - the current session id.
   * @returns {string} the rendered card.
   */
  const card = (snapshot, current) => render(HarnessSettingsCard, {
    useHarness: selector => selector(snapshot),
    useSessions: selector => selector({ current }),
    write: () => Promise.resolve({ ok: true }),
    t,
  });

  const ready = { status: 'ready', writable: true, value: { governance: true, autoEnable: false, autoUpgrade: false } };

  it('renders one switch per setting', () => {
    const html = card(ready, 'session-1');
    assert.equal(html.match(/type="checkbox"/g).length, 3);
    assert.match(html, /id="docs-harness-governance"[^>]*checked/);
  });

  it('defaults the master switch to on before the host answers', () => {
    const html = card({ status: 'ready', writable: true, value: undefined }, 'session-1');
    assert.match(html, /id="docs-harness-governance"[^>]*checked/);
  });

  it('locks the switches and says why when the namespace is unavailable', () => {
    const html = card({ status: 'unavailable', writable: false, value: undefined }, 'session-1');
    assert.match(html, /settings\.unavailable/);
    // The three switches lock; removal does not, because it goes through the
    // routes rather than through the settings document.
    assert.equal(html.match(/disabled/g).length, 3);
    assert.doesNotMatch(html, /<button[^>]*disabled/);
  });

  it('cannot remove anything without a session to name the project', () => {
    const html = card(ready, undefined);
    assert.match(html, /settings\.noSession/);
  });
});
