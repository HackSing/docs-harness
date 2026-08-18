/**
 * Module customization hook: compile `.jsx` on import so the unit tests can
 * import the browser components directly from source.
 *
 * The alternative — testing the built bundle — would test one artifact through
 * a wrapper designed for a browser module table, and would report every failure
 * against a generated line number. This keeps the test subject and the shipped
 * subject the same file, compiled by the same tool the build uses.
 */

import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

import { transform } from 'esbuild';

/**
 * @param {string} url - the module being loaded.
 * @param {object} context - loader context.
 * @param {Function} nextLoad - the next hook in the chain.
 * @returns {Promise<object>} the module source.
 */
export async function load(url, context, nextLoad) {
  if (!url.endsWith('.jsx')) return nextLoad(url, context);
  const source = await readFile(fileURLToPath(url), 'utf8');
  const { code } = await transform(source, {
    loader: 'jsx',
    jsx: 'automatic',
    format: 'esm',
    target: 'node22',
    sourcefile: fileURLToPath(url),
  });
  return { format: 'module', source: code, shortCircuit: true };
}
