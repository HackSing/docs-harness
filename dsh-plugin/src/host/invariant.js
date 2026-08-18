/**
 * Invariant companion. This package owns no cross-package runtime invariant:
 * the governance gate is a fiber whose absence is indistinguishable from the
 * package not being installed, which is the property the design relies on.
 *
 * @module dsh-docs-harness/invariant
 */

/** Registers no assertions. */
export function apply() {}
