import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { afterEach, describe, it } from 'node:test';

import { ITEM_STATUSES, TOOL_NAMES, TOOL_PLAN_PROGRESS } from '../src/shared/constants.js';
import { resetProjectCaches } from '../src/host/project-state.js';
import { harnessTools } from '../src/host/tools.js';
import { isLoopback, workspaceOf } from '../src/host/routes.js';

const created = [];

/**
 * @param {boolean} enabled - whether to stamp a Docs Harness install.
 * @returns {string} the temporary project root.
 */
function makeProject(enabled) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'docs-harness-tools-'));
  created.push(dir);
  if (enabled) {
    fs.mkdirSync(path.join(dir, '.docs-harness'), { recursive: true });
    fs.writeFileSync(path.join(dir, '.docs-harness', 'config.json'), JSON.stringify({ version: '2.8.0' }));
  }
  return dir;
}

/**
 * @param {string | undefined} cwd - the session workspace root.
 * @returns {object} a tool execution context.
 */
const execFor = cwd => ({
  agent: cwd === undefined ? undefined : { session: { header: { cwd } } },
  signal: new AbortController().signal,
});

/** @returns {object} the tools keyed by name. */
function toolsByName() {
  const ctx = { get: () => undefined };
  return Object.fromEntries(harnessTools(ctx).map(tool => [tool.name, tool]));
}

afterEach(() => {
  resetProjectCaches();
  for (const dir of created.splice(0)) fs.rmSync(dir, { recursive: true, force: true });
});

describe('tool family', () => {
  it('registers exactly the declared names', () => {
    assert.deepEqual(Object.keys(toolsByName()), TOOL_NAMES);
  });

  it('never exposes the project write operations as tools the model can call', () => {
    for (const name of Object.keys(toolsByName())) {
      assert.ok(!name.includes('project'), `${name} would let an agent write into the user's repository`);
    }
  });

  it('refuses in an unprepared project, and tells the model NOT to enable it', async () => {
    const tools = toolsByName();
    const exec = execFor(makeProject(false));
    for (const name of ['harness_plan_select', 'harness_plan_create', 'harness_plan_settle']) {
      const thrown = await tools[name]
        .execute({ selection: 'a', content: 'b', output: 'c', plan: 'p', status: 'implemented' }, exec)
        .catch(cause => cause);
      assert.ok(thrown instanceof Error, `${name} must refuse`);
      assert.match(thrown.message, /not enabled/);
      assert.match(thrown.message, /Do NOT enable it yourself/);
    }
  });

  it('refuses without a session workspace rather than guessing a directory', async () => {
    const tools = toolsByName();
    const thrown = await tools[TOOL_PLAN_PROGRESS]
      .execute({ items: [{ content: 'x', status: 'pending' }] }, execFor(undefined))
      .catch(cause => cause);
    assert.match(thrown.message, /workspace directory/);
  });
});

describe('plan_progress', () => {
  it('counts the whole list it was handed', async () => {
    const tool = toolsByName()[TOOL_PLAN_PROGRESS];
    const items = [
      { content: 'a', status: 'completed' },
      { content: 'b', status: 'in_progress' },
    ];
    assert.deepEqual(await tool.execute({ items }, execFor(makeProject(false))), { done: 1, total: 2 });
  });

  it('works in a project with no Docs Harness install (progress is UI state, not an asset)', async () => {
    const tool = toolsByName()[TOOL_PLAN_PROGRESS];
    await tool.execute({ items: [] }, execFor(makeProject(false)));
  });

  it('fails loudly on blank content rather than showing the user an empty row', async () => {
    const tool = toolsByName()[TOOL_PLAN_PROGRESS];
    await assert.rejects(
      () => tool.execute({ items: [{ content: '   ', status: 'pending' }] }, execFor(makeProject(false))),
      /non-empty content/,
    );
  });

  it('rejects an unknown status through its declared schema', async () => {
    const tool = toolsByName()[TOOL_PLAN_PROGRESS];
    await assert.rejects(
      () => tool.execute({ items: [{ content: 'x', status: 'almost' }] }, execFor(makeProject(false))),
      /status/,
    );
  });

  it('rejects a missing items argument', async () => {
    const tool = toolsByName()[TOOL_PLAN_PROGRESS];
    await assert.rejects(() => tool.execute({}, execFor(makeProject(false))), /items/);
  });

  it('publishes the validated whole list as result metadata for the projection', () => {
    const tool = toolsByName()[TOOL_PLAN_PROGRESS];
    const items = ITEM_STATUSES.map(status => ({ content: status, status }));
    const meta = tool.output.presentationMeta({ items }, { done: 1, total: 3 });
    assert.deepEqual(meta, { items });
  });
});

describe('route guards', () => {
  it('accepts only loopback peers', () => {
    for (const address of ['127.0.0.1', '::1', '::ffff:127.0.0.1']) {
      assert.equal(isLoopback({ socket: { remoteAddress: address } }), true);
    }
    for (const address of ['10.0.0.4', '203.0.113.7', undefined]) {
      assert.equal(isLoopback({ socket: { remoteAddress: address } }), false);
    }
  });

  it('resolves the target directory from the session store, never from the request body', () => {
    const ctx = { sessions: { get: id => (id === 'live' ? { header: { cwd: 'D:/work' } } : undefined) } };
    assert.equal(workspaceOf(ctx, 'live'), 'D:/work');
    assert.equal(workspaceOf(ctx, 'ghost'), undefined);
    assert.equal(workspaceOf(ctx, ''), undefined);
    assert.equal(workspaceOf(ctx, { path: 'C:/Windows' }), undefined);
  });

  it('reports no directory when the session has no workspace', () => {
    const ctx = { sessions: { get: () => ({ header: {} }) } };
    assert.equal(workspaceOf(ctx, 'live'), undefined);
  });
});
