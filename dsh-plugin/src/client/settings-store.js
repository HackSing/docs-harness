/**
 * The browser-side store behind this plugin's switches.
 *
 * A drop-in for the framework `settingsScope` binding, carrying the same
 * snapshot contract ({@link getSnapshot} / {@link subscribe} / {@link set})
 * over the plugin's own `/docs-harness-settings` routes instead of the
 * gateway's settings transport — which serves an allowlist of namespaces this
 * plugin can never join (see host/settings-routes.js).
 *
 * Operations are serialized on one tail so a slow read never overwrites the
 * state a later write already published. The snapshot reference is stable
 * between changes, which is what lets the slot hooks feed it straight into
 * `useSyncExternalStore` selectors without re-render storms.
 *
 * @module dsh-docs-harness/client/settings-store
 */

import {
  ACTION_SETTINGS_READ,
  ACTION_SETTINGS_RESET,
  ACTION_SETTINGS_WRITE,
  SETTINGS_ROUTE_PREFIX,
} from '../shared/constants.js';
import { postJson } from './api.js';

/** The one pre-answer snapshot, shared so an idle store allocates nothing. */
const LOADING = Object.freeze({ status: 'loading', value: undefined, user: undefined, writable: false });

/** Serializes reads and writes of the docs-harness section behind a snapshot store. */
export class HarnessSettingsStore {
  /**
   * @param {(path: string, body: object) => Promise<import('./api.js').HarnessEnvelope>} [transport]
   * - the wire call; injectable for tests, defaults to {@link postJson}.
   */
  constructor(transport = postJson) {
    this.transport = transport;
    this.listeners = new Set();
    this.snapshot = LOADING;
    this.tail = Promise.resolve();
    this.disposed = false;
  }

  /** @returns {{ status: string, value: object | undefined, user: object | undefined, writable: boolean }} the current snapshot (stable reference until the next change). */
  getSnapshot() {
    return this.snapshot;
  }

  /**
   * Observe snapshot replacements. The first subscriber of an unanswered store
   * triggers a load, so a reopened settings dialog recovers from an earlier
   * transport failure without anyone calling load by hand.
   * @param {() => void} listener - invoked after each snapshot change.
   * @returns {() => void} the disposer removing this listener.
   */
  subscribe(listener) {
    if (this.listeners.size === 0 && this.snapshot.status !== 'ready') void this.load();
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /**
   * Queue a host refresh.
   * @returns {Promise<void>} settlement after the read published or failed.
   */
  load() {
    return this.enqueue(async () => {
      const envelope = await this.transport(`${SETTINGS_ROUTE_PREFIX}/${ACTION_SETTINGS_READ}`, {});
      this.publish(envelope.ok
        ? { status: 'ready', value: envelope.value?.value, user: envelope.value?.user, writable: envelope.value?.writable === true }
        : { status: 'unavailable', value: undefined, user: undefined, writable: false });
    });
  }

  /**
   * Queue one field write. Resolves on success with the fresh section already
   * published; rejects with the host's reason on refusal, leaving the previous
   * snapshot in place for the control to snap back to.
   * @param {string} field - scalar field inside the namespace section.
   * @param {unknown} value - JSON-shaped value selected by the user.
   * @returns {Promise<void>} settlement of the write.
   */
  set(field, value) {
    return this.write(ACTION_SETTINGS_WRITE, { field, value });
  }

  /**
   * Queue one field reset: unset it from the user layer so the resolved value
   * re-inherits the composition base and schema defaults. Same settlement
   * contract as {@link set}.
   * @param {string} field - the field whose user override is removed.
   * @returns {Promise<void>} settlement of the write.
   */
  reset(field) {
    return this.write(ACTION_SETTINGS_RESET, { field });
  }

  /**
   * The shared write path behind {@link set} and {@link reset}: one action,
   * one body, one publish of the fresh section the host answered with.
   * @param {string} action - the settings route action.
   * @param {object} body - the JSON payload.
   * @returns {Promise<void>} settlement of the write.
   */
  write(action, body) {
    return this.enqueue(async () => {
      const envelope = await this.transport(`${SETTINGS_ROUTE_PREFIX}/${action}`, body);
      if (!envelope.ok) {
        throw new Error(envelope.error?.message ?? 'settings write failed');
      }
      this.publish({ status: 'ready', value: envelope.value?.value, user: envelope.value?.user, writable: envelope.value?.writable === true });
    });
  }

  /** Stop publishing; queued operations become no-ops. */
  dispose() {
    this.disposed = true;
    this.listeners.clear();
  }

  /**
   * @param {object} next - the next snapshot.
   */
  publish(next) {
    if (this.disposed) return;
    this.snapshot = Object.freeze(next);
    for (const listener of [...this.listeners]) listener();
  }

  /**
   * @param {() => Promise<void>} operation - the queued step.
   * @returns {Promise<void>} the step's own settlement.
   */
  enqueue(operation) {
    if (this.disposed) return Promise.resolve();
    const task = this.tail.then(() => (this.disposed ? undefined : operation()));
    // The returned task carries its own settlement to the caller; the queue
    // tail is kept fulfilled so one rejected write cannot strand later steps.
    this.tail = task.catch(() => {});
    return task;
  }
}
