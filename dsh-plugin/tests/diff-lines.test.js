import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { NO_DIFF, addResultDiff, countHunk, hunksFromMeta } from '../src/host/diff-lines.js';

describe('countHunk', () => {
  it('counts a new file as pure addition', () => {
    assert.deepEqual(countHunk({ oldText: null, newText: 'a\nb\nc\n' }), { added: 3, removed: 0 });
  });

  it('ignores the context lines a hunk carries on both sides', () => {
    // Three context lines each side, one line replaced — the shape tool-fs emits.
    const before = 'c1\nc2\nc3\nold\nc4\nc5\nc6\n';
    const after = 'c1\nc2\nc3\nnew\nc4\nc5\nc6\n';
    assert.deepEqual(countHunk({ oldText: before, newText: after }), { added: 1, removed: 1 });
  });

  it('counts a pure insertion inside context as addition only', () => {
    assert.deepEqual(
      countHunk({ oldText: 'a\nb\n', newText: 'a\nx\ny\nb\n' }),
      { added: 2, removed: 0 },
    );
  });

  it('counts a pure deletion inside context as removal only', () => {
    assert.deepEqual(
      countHunk({ oldText: 'a\nx\ny\nb\n', newText: 'a\nb\n' }),
      { added: 0, removed: 2 },
    );
  });

  it('reports nothing for identical texts', () => {
    assert.deepEqual(countHunk({ oldText: 'a\nb\n', newText: 'a\nb\n' }), { added: 0, removed: 0 });
  });

  it('treats a missing trailing newline as the same line count', () => {
    assert.deepEqual(countHunk({ oldText: null, newText: 'a\nb' }), { added: 2, removed: 0 });
  });
});

describe('hunksFromMeta', () => {
  it('accepts the tool-fs FsDiffMeta shape', () => {
    const meta = { diffs: [{ path: 'a.js', oldText: null, newText: 'x\n' }] };
    assert.equal(hunksFromMeta(meta).length, 1);
  });

  it('rejects everything else without throwing', () => {
    for (const meta of [undefined, null, 42, 'x', {}, { diffs: 'no' }, { diffs: [{ newText: 1 }] }]) {
      assert.deepEqual(hunksFromMeta(meta), []);
    }
  });
});

describe('addResultDiff', () => {
  it('returns the same reference when nothing counted (the projection change gate)', () => {
    const totals = { added: 1, removed: 2 };
    assert.equal(addResultDiff(totals, { nothing: true }), totals);
  });

  it('accumulates across hunks and across calls', () => {
    const first = addResultDiff(NO_DIFF, {
      diffs: [{ oldText: null, newText: 'a\nb\n' }, { oldText: 'x\n', newText: '' }],
    });
    assert.deepEqual(first, { added: 2, removed: 1 });
    assert.deepEqual(addResultDiff(first, { diffs: [{ oldText: null, newText: 'c\n' }] }), { added: 3, removed: 1 });
  });
});
