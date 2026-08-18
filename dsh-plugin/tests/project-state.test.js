import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { afterEach, describe, it } from 'node:test';

import { MANAGED_BEGIN, MANAGED_END, readManagedBlock } from '../src/host/managed-block.js';
import { detectProject, readGovernanceRules, resetProjectCaches, seedVersion } from '../src/host/project-state.js';
import { buildRulesSection, toolAdapterNote } from '../src/host/rules-section.js';
import { governanceText } from '../src/host/index.js';

const created = [];

/**
 * @param {object} [options] - fixture options.
 * @param {string} [options.version] - version stamped into .docs-harness/config.json.
 * @param {string} [options.rules] - managed block body written into AGENTS.md.
 * @returns {string} the temporary project root.
 */
function makeProject({ version, rules } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'docs-harness-test-'));
  created.push(dir);
  if (version !== undefined) {
    fs.mkdirSync(path.join(dir, '.docs-harness'), { recursive: true });
    fs.writeFileSync(
      path.join(dir, '.docs-harness', 'config.json'),
      JSON.stringify({ schema_version: 'docs-harness/project-config/v9', version }),
    );
  }
  if (rules !== undefined) {
    fs.writeFileSync(path.join(dir, 'AGENTS.md'), `# AGENTS.md\n\n${MANAGED_BEGIN}\n${rules}\n${MANAGED_END}\n`);
  }
  return dir;
}

afterEach(() => {
  resetProjectCaches();
  for (const dir of created.splice(0)) fs.rmSync(dir, { recursive: true, force: true });
});

describe('managed block reader', () => {
  it('extracts the body between the engine markers', () => {
    assert.equal(readManagedBlock(`x\n${MANAGED_BEGIN}\nbody\n${MANAGED_END}\ny`), 'body');
  });

  it('normalizes a CRLF checkout, so the injected text matches the seed byte for byte', () => {
    const crlf = `x\r\n${MANAGED_BEGIN}\r\nbody\r\nmore\r\n${MANAGED_END}\r\n`;
    assert.equal(readManagedBlock(crlf), 'body\nmore');
  });

  it('refuses a file with no, duplicated, or inverted markers rather than guessing', () => {
    assert.equal(readManagedBlock('nothing here'), undefined);
    assert.equal(readManagedBlock(`${MANAGED_END}\nbody\n${MANAGED_BEGIN}`), undefined);
    assert.equal(readManagedBlock(`${MANAGED_BEGIN}\na\n${MANAGED_END}\n${MANAGED_BEGIN}\nb\n${MANAGED_END}`), undefined);
  });
});

describe('detectProject', () => {
  it('offers to enable a project with no install stamp', () => {
    const state = detectProject(makeProject());
    assert.equal(state.enabled, false);
    assert.equal(state.projectVersion, null);
    assert.equal(state.prompt, 'enable');
  });

  it('is quiet when the project matches the version this plugin ships', () => {
    const state = detectProject(makeProject({ version: seedVersion() }));
    assert.equal(state.enabled, true);
    assert.equal(state.prompt, 'none');
  });

  it('offers an upgrade when the project version is behind', () => {
    const state = detectProject(makeProject({ version: '0.0.1-ancient' }));
    assert.equal(state.enabled, true);
    assert.equal(state.projectVersion, '0.0.1-ancient');
    assert.equal(state.prompt, 'upgrade');
  });

  it('reports the seed version this plugin would install', () => {
    assert.match(String(seedVersion()), /^\d+\.\d+\.\d+/);
  });
});

describe('governance rules', () => {
  it('reads the project AGENTS.md managed block verbatim', () => {
    const dir = makeProject({ version: seedVersion(), rules: 'PROJECT RULES\nline two' });
    const rules = readGovernanceRules(dir);
    assert.equal(rules.source, 'project');
    assert.equal(rules.text, 'PROJECT RULES\nline two');
  });

  it('falls back to the shipped seed text when the project file is damaged', () => {
    const dir = makeProject({ version: seedVersion() });
    const rules = readGovernanceRules(dir);
    assert.equal(rules.source, 'seed');
    assert.match(rules.text, /Docs Harness/);
  });

  it('injects the project block with ZERO edits, plus only the invocation adapter', () => {
    const body = 'RULE ONE\n\n- bullet\n\n## 收尾\n\n最后一行。';
    const dir = makeProject({ version: seedVersion(), rules: body });
    const section = governanceText({ agent: { session: { header: { cwd: dir } } } });
    assert.ok(section.startsWith(body), 'the rules body must lead, unmodified');
    assert.equal(section, `${body}\n\n${toolAdapterNote()}`);
  });

  it('injects nothing for a project with no Docs Harness install', () => {
    const dir = makeProject({ rules: 'RULES' });
    assert.equal(governanceText({ agent: { session: { header: { cwd: dir } } } }), '');
  });

  it('injects nothing for an assembly with no agent', () => {
    assert.equal(governanceText({}), '');
    assert.equal(governanceText({ agent: { session: { header: {} } } }), '');
  });

  it('re-reads after the file changes, so enabling mid-session takes effect', () => {
    const dir = makeProject({ version: seedVersion(), rules: 'FIRST' });
    assert.match(governanceText({ agent: { session: { header: { cwd: dir } } } }), /^FIRST/);
    resetProjectCaches();
    fs.writeFileSync(path.join(dir, 'AGENTS.md'), `${MANAGED_BEGIN}\nSECOND\n${MANAGED_END}\n`);
    assert.match(governanceText({ agent: { session: { header: { cwd: dir } } } }), /^SECOND/);
  });

  it('states the CLI/tool equivalence and that the file need not be re-read', () => {
    const note = toolAdapterNote();
    assert.match(note, /不需要再读取该文件/);
    assert.match(note, /harness_plan_select/);
    assert.match(note, /harness_plan_create/);
    assert.match(note, /harness_plan_settle/);
    assert.match(note, /plan_progress/);
  });

  it('forbids the terminal path for plan operations, covering CLI mentions inside plan documents', () => {
    const note = toolAdapterNote();
    assert.match(note, /禁止经终端执行/);
    assert.match(note, /方案文档和历史文档/);
    assert.match(note, /不要再使用内置待办工具/);
    assert.match(note, /knowledge \/ acceptance \/ assets-check \/ project/);
  });

  it('contributes nothing at all when neither source is readable', () => {
    assert.equal(buildRulesSection(undefined), '');
  });
});
