/**
 * Integration coverage for the Python boundary. These run the real vendored
 * engine against real throwaway repositories — a mock would only prove the mock
 * agrees with itself, and the contract being verified (argument shape, exit-code
 * meaning, error propagation) lives entirely on the other side of the process.
 */
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, describe, it } from 'node:test';

import { EngineError, SEED_ENGINE, engineFor, runEngine } from '../src/host/engine.js';
import { PYTHON_CANDIDATES } from '../src/shared/constants.js';
import { PROJECT_ENGINE_RELATIVE } from '../src/shared/constants.js';
import { detectProject, resetProjectCaches, seedVersion } from '../src/host/project-state.js';
import { runProjectOperation } from '../src/host/project-ops.js';
import { readManagedBlock } from '../src/host/managed-block.js';

const created = [];
// Probed at module scope: node:test evaluates a suite's `skip` before any
// `before` hook runs, so an async probe would always read as "unavailable".
const pythonAvailable = PYTHON_CANDIDATES.some(candidate =>
  spawnSync(candidate, ['--version'], { windowsHide: true }).status === 0);

/** @returns {string} a throwaway git repository. */
function makeRepo() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'docs-harness-engine-'));
  created.push(dir);
  execFileSync('git', ['init', '--quiet'], { cwd: dir });
  return dir;
}

after(() => {
  resetProjectCaches();
  for (const dir of created.splice(0)) fs.rmSync(dir, { recursive: true, force: true });
});

describe('engine boundary', { skip: pythonAvailable ? false : 'no Python 3 on PATH' }, () => {
  it('installs a project from the vendored seed and stamps the seed version', async () => {
    const repo = makeRepo();
    const { state } = await runProjectOperation('init', repo);
    assert.equal(state.enabled, true);
    assert.equal(state.projectVersion, seedVersion());
    assert.equal(state.prompt, 'none');
    assert.ok(fs.existsSync(path.join(repo, PROJECT_ENGINE_RELATIVE)), 'the project gets its own engine copy');
  });

  it('writes an AGENTS.md whose managed block is the text the plugin would inject', async () => {
    const repo = makeRepo();
    await runProjectOperation('init', repo);
    const written = readManagedBlock(fs.readFileSync(path.join(repo, 'AGENTS.md'), 'utf8'));
    const seeded = readManagedBlock(fs.readFileSync(path.join(SEED_ENGINE, '..', '..', 'managed-entry.md'), 'utf8'));
    assert.equal(written, seeded, 'the committed seed text must stay byte-identical to what the engine writes');
  });

  it('prefers the project engine once one exists, and the seed before that', async () => {
    const repo = makeRepo();
    assert.equal(engineFor(repo), SEED_ENGINE);
    await runProjectOperation('init', repo);
    assert.equal(engineFor(repo), path.join(repo, PROJECT_ENGINE_RELATIVE));
  });

  it('treats exit 3 (written but not committed) as success, not failure', async () => {
    // A fresh install always lands uncommitted, so this is the ordinary path;
    // reading exit codes alone would report a successful install as a failure.
    const repo = makeRepo();
    const settled = await runEngine({ engine: SEED_ENGINE, args: ['project', 'check'], projectDir: repo })
      .catch(cause => cause);
    // An uninstalled project fails `check` with red findings (exit 1) — that IS
    // an error. What must not throw is the pending-commit path below.
    assert.ok(settled instanceof EngineError);
    await runProjectOperation('init', repo);
    const after = await runEngine({ engine: engineFor(repo), args: ['project', 'check'], projectDir: repo });
    assert.equal(after.exitCode, 3);
    assert.equal(after.payload.delivery_status, 'pending_commit');
  });

  it('returns the plan-select payload the create step consumes', async () => {
    const repo = makeRepo();
    await runProjectOperation('init', repo);
    const { payload } = await runEngine({
      engine: engineFor(repo),
      args: ['plan', 'select', '--level', 'brief', '--profile', 'general'],
      projectDir: repo,
    });
    assert.equal(payload.plan_level, 'brief');
    assert.ok(Array.isArray(payload.fields) && payload.fields.length > 0);
  });

  it('propagates an engine refusal with its own code and message', async () => {
    const repo = makeRepo();
    await runProjectOperation('init', repo);
    const thrown = await runEngine({
      engine: engineFor(repo),
      args: ['plan', 'create', '--selection', 'docs/nope.json', '--content', 'docs/nope.json', '--output', 'docs/plans/x.json'],
      projectDir: repo,
    }).catch(cause => cause);
    assert.ok(thrown instanceof EngineError);
    assert.equal(thrown.code, 'invalid_plan_selection');
    assert.match(thrown.message, /docs\/nope\.json/);
  });

  it('refuses a path that escapes the project, and says so', async () => {
    const repo = makeRepo();
    await runProjectOperation('init', repo);
    const thrown = await runEngine({
      engine: engineFor(repo),
      args: ['plan', 'create', '--selection', path.join(os.tmpdir(), 'x.json'), '--content', 'a.json', '--output', 'docs/plans/x.json'],
      projectDir: repo,
    }).catch(cause => cause);
    assert.ok(thrown instanceof EngineError);
    assert.match(thrown.message, /路径越出项目目录/);
  });

  it('round-trips install and removal, leaving the user\'s own AGENTS.md prose intact', async () => {
    const repo = makeRepo();
    fs.writeFileSync(path.join(repo, 'AGENTS.md'), '# AGENTS.md\n\n## My own house rules\n\nkeep me.\n');
    await runProjectOperation('init', repo);
    const installed = fs.readFileSync(path.join(repo, 'AGENTS.md'), 'utf8');
    assert.match(installed, /My own house rules/);
    assert.ok(readManagedBlock(installed) !== undefined);

    const { state } = await runProjectOperation('uninstall', repo);
    assert.equal(state.enabled, false);
    const removed = fs.readFileSync(path.join(repo, 'AGENTS.md'), 'utf8');
    assert.match(removed, /My own house rules/, 'text outside the managed block is untouched');
    assert.equal(readManagedBlock(removed), undefined, 'the managed block is gone');
    assert.ok(!fs.existsSync(path.join(repo, PROJECT_ENGINE_RELATIVE)), 'the unmodified engine copy is removed');
    assert.ok(fs.existsSync(path.join(repo, 'docs', 'plans')), 'docs/ is project data and survives removal');
  });

  it('leaves a project the user modified alone rather than deleting their work', async () => {
    const repo = makeRepo();
    await runProjectOperation('init', repo);
    const engine = path.join(repo, PROJECT_ENGINE_RELATIVE);
    fs.appendFileSync(engine, '\n# local edit\n');
    await runProjectOperation('uninstall', repo);
    assert.ok(fs.existsSync(engine), 'a fingerprint mismatch means hands off');
  });

  it('detects the state the notice bar reads, at every stage', async () => {
    const repo = makeRepo();
    assert.equal(detectProject(repo).prompt, 'enable');
    await runProjectOperation('init', repo);
    assert.equal(detectProject(repo).prompt, 'none');
    const stamp = path.join(repo, '.docs-harness', 'config.json');
    const config = JSON.parse(fs.readFileSync(stamp, 'utf8'));
    fs.writeFileSync(stamp, JSON.stringify({ ...config, version: '0.0.1-ancient' }));
    resetProjectCaches();
    assert.equal(detectProject(repo).prompt, 'upgrade');
  });

  it('rejects an unknown project operation instead of guessing', async () => {
    await assert.rejects(() => runProjectOperation('destroy', makeRepo()), /unknown project operation/);
  });
});
