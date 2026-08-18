/**
 * What the notice bar concludes from one route answer.
 *
 * The decisions under test are the ones with a cost when wrong: prompting to
 * install a project that already has it, showing a scary error for a capability
 * the user deliberately switched off, or offering an action for a prompt state
 * that has none.
 */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { ACTION_INIT, ACTION_UPGRADE, PROMPT_ENABLE, PROMPT_NONE, PROMPT_UPGRADE } from '../src/shared/constants.js';
import { CODE_ABSENT } from '../src/client/api.js';
import { ACTION_FOR, SILENT, readNotice } from '../src/client/EnableNoticeBar.jsx';

/**
 * @param {object} state - the project state the host reported.
 * @param {string} [dir] - the resolved workspace root.
 * @returns {object} a success envelope.
 */
const ok = (state, dir = 'D:/work') => ({ ok: true, value: { state, changed: [], dir } });

describe('notice state', () => {
  it('offers install for a project that has none', () => {
    const notice = readNotice(ok({ enabled: false, projectVersion: null, seedVersion: '2.8.0', prompt: PROMPT_ENABLE }));
    assert.equal(notice.prompt, PROMPT_ENABLE);
    assert.equal(notice.dir, 'D:/work');
    assert.equal(ACTION_FOR[notice.prompt], ACTION_INIT);
  });

  it('offers upgrade with both versions to name in the message', () => {
    const notice = readNotice(ok({ enabled: true, projectVersion: '2.7.0', seedVersion: '2.8.0', prompt: PROMPT_UPGRADE }));
    assert.deepEqual(notice.versions, { from: '2.7.0', to: '2.8.0' });
    assert.equal(ACTION_FOR[notice.prompt], ACTION_UPGRADE);
  });

  it('says nothing about a project that is already current', () => {
    assert.deepEqual(readNotice(ok({ enabled: true, projectVersion: '2.8.0', seedVersion: '2.8.0', prompt: PROMPT_NONE })), SILENT);
  });

  it('stays silent when the routes are gone, which is how governance-off looks', () => {
    assert.deepEqual(readNotice({ ok: false, error: { code: CODE_ABSENT, message: 'HTTP 404' } }), SILENT);
  });

  it('stays silent before any session exists', () => {
    assert.deepEqual(readNotice({ ok: false, error: { code: 'no-session', message: 'no current session' } }), SILENT);
  });

  it('stays silent when the session has no workspace bound yet, which is normal right after launch', () => {
    assert.deepEqual(
      readNotice({ ok: false, error: { code: 'unknown-session', message: 'no live session with a workspace' } }),
      SILENT,
    );
  });

  it('reports a real failure with the engine\'s own message', () => {
    const notice = readNotice({ ok: false, error: { code: 'python_missing', message: 'Docs Harness needs Python 3' } });
    assert.equal(notice.error, 'Docs Harness needs Python 3');
    assert.equal(notice.prompt, undefined);
  });

  it('offers nothing for a prompt state it has no action for', () => {
    assert.deepEqual(readNotice(ok({ prompt: 'reboot-the-universe' })), SILENT);
  });

  it('survives an envelope with no value at all', () => {
    assert.deepEqual(readNotice({ ok: true }), SILENT);
  });
});
