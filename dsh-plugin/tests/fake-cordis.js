/**
 * The cordis machinery both fake contexts share: effects, child fibers,
 * optional-service injects, and the teardown cascade.
 *
 * Only the surface the two plugin halves actually touch is modelled. The one
 * behaviour worth being careful about is disposal order — cordis unwinds child
 * fibers before the parent's own effects, and a fake that forgot to would let a
 * leak pass every test.
 */

/**
 * Build a root context over a service map.
 *
 * A service may expose `__bind(ctx)` to return a per-context face; the slot
 * registry needs that, because its `inject` installs an effect on the CALLER's
 * fiber rather than on the service's own.
 * @param {Map<string, object>} services - the services to expose.
 * @param {{ warnings: string[], disposed: number }} ledger - shared recording ledger.
 * @returns {object} the root context, carrying `__dispose()`.
 */
export function createCordis(services, ledger) {
  /**
   * @param {object} parent - the context being extended.
   * @returns {object} a child context sharing the ledger.
   */
  const makeContext = (parent = {}) => {
    const disposers = [];
    const children = [];
    const ctx = {
      ...parent,
      logger: { warn: message => ledger.warnings.push(String(message)) },
      get: name => services.get(name),
      effect(execute, _label) {
        const produced = execute();
        const list = typeof produced === 'function' ? [produced]
          : produced != null && typeof produced[Symbol.iterator] === 'function' ? [...produced]
            : [];
        disposers.push(...list);
        return () => { for (const dispose of list.splice(0)) dispose(); };
      },
      inject(names, callback) {
        if (!names.every(service => services.has(service))) return { dispose: () => Promise.resolve() };
        const child = makeContext(ctx);
        children.push(child);
        callback(child);
        return { dispose: () => { child.__dispose(); return Promise.resolve(); } };
      },
      plugin(pluginObject) {
        const child = makeContext(ctx);
        children.push(child);
        pluginObject.apply(child);
        return {
          dispose: () => {
            ledger.disposed += 1;
            child.__dispose();
            return Promise.resolve();
          },
        };
      },
      // Child fibers unwind with their parent, as they do in cordis.
      __dispose() {
        for (const child of children.splice(0).reverse()) child.__dispose();
        for (const dispose of disposers.splice(0).reverse()) dispose();
      },
    };
    for (const [name, value] of services) {
      ctx[name] = typeof value.__bind === 'function' ? value.__bind(ctx) : value;
    }
    return ctx;
  };
  return makeContext();
}
