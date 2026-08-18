/**
 * Build the browser bundle.
 *
 * The artifact contract is fixed by the host's client module system, not by
 * this package: executing the script must only REGISTER a factory
 * (`window.__ModuleLoader__.load({ id, factory })`), the factory receives the
 * module table's synchronous `require`, and it returns `module.exports`. Every
 * module-body side effect therefore runs at materialization, not at script
 * execution.
 *
 * The upstream repository builds the same shape with tsdown/rolldown. Reusing
 * that toolchain would mean depending on the harness monorepo's build packages
 * from outside the monorepo; esbuild produces a byte-compatible wrapper from
 * three string options, and the plan pre-approved it.
 *
 * @module dsh-docs-harness/scripts/build-client
 */

import { fileURLToPath } from 'node:url';
import path from 'node:path';

import esbuild from 'esbuild';

import { PACKAGE_NAME } from '../src/shared/constants.js';

const ROOT = fileURLToPath(new URL('..', import.meta.url));

/**
 * Specifiers the host's frozen module table answers, which must therefore stay
 * as `require()` calls in the artifact. Mirrors `PLATFORM_MODULES` in
 * `@deepseek-ai/dsh-client-web`; anything not listed here has no table row and
 * must be inlined instead, because a `require` the table cannot answer throws
 * at materialization.
 */
const CLIENT_EXTERNALS = [
  'react',
  'react/jsx-runtime',
  'react-dom',
  'react-dom/client',
  '@deepseek-ai/cordis',
  '@deepseek-ai/dsh-client-ui-slots',
  '@deepseek-ai/dsh-client-web-react',
  '@deepseek-ai/dsh-client-ui-primitives',
  '@deepseek-ai/dsh-client-ui-attachment',
  '@deepseek-ai/dsh-client-schema-form',
];

/**
 * Build-time mirror of the runtime module-edge rule: a value import of another
 * plugin's package either inlines a second copy of a shared runtime identity or
 * asks the frozen table for a row it does not have. Both fail in the browser,
 * far from the edit that caused them, so the build refuses instead.
 */
const purityGate = {
  name: 'docs-harness-purity',
  setup(build) {
    build.onResolve({ filter: /^@deepseek-ai\// }, (args) => {
      if (CLIENT_EXTERNALS.includes(args.path)) return null;
      throw new Error(
        `client bundle purity: "${args.path}" is not a platform module; `
        + 'cross-plugin value imports cannot resolve in the browser — collaborate through cordis services',
      );
    });
  },
};

/** @returns {Promise<void>} settled once `lib/client.js` is written. */
async function build() {
  const result = await esbuild.build({
    entryPoints: [path.join(ROOT, 'src', 'client', 'index.jsx')],
    outfile: path.join(ROOT, 'lib', 'client.js'),
    bundle: true,
    format: 'cjs',
    platform: 'browser',
    target: ['es2022'],
    jsx: 'automatic',
    sourcemap: true,
    logLevel: 'warning',
    external: CLIENT_EXTERNALS,
    define: { 'process.env.NODE_ENV': JSON.stringify(process.env.NODE_ENV ?? 'production') },
    // esbuild has no separate `intro`, so the module/exports pair the CJS body
    // assigns to is declared at the end of the banner, inside the factory.
    banner: {
      js: `window.__ModuleLoader__.load({ id: ${JSON.stringify(PACKAGE_NAME)}, factory: (require) => {\n`
        + 'var module = { exports: {} }; var exports = module.exports;',
    },
    footer: { js: 'return module.exports; } });' },
    plugins: [purityGate],
  });
  for (const warning of result.warnings) {
    process.stderr.write(`${warning.text}\n`);
  }
}

await build();
