/**
 * The Docs Harness settings page (Settings → Docs Harness nav entry).
 *
 * Three switches and one destructive action behind a two-step confirm. The
 * switches write into the same
 * host settings namespace the host half reads, so the master switch here is
 * literally the gate that adds or removes the tools, the prompt section, the
 * projection, and the routes — there is no second copy of that decision.
 *
 * The removal button acts on the CURRENT session's project, named in the hint,
 * because a settings pane has no project of its own.
 *
 * @module dsh-docs-harness/client/HarnessSettingsCard
 */

import { useCallback, useState } from 'react';

import {
  ACTION_UNINSTALL,
  DEFAULT_AUTO_ENABLE,
  DEFAULT_AUTO_UPGRADE,
  DEFAULT_GOVERNANCE_ENABLED,
  FIELD_AUTO_ENABLE,
  FIELD_AUTO_UPGRADE,
  FIELD_GOVERNANCE,
} from '../shared/constants.js';
import { callHarness } from './api.js';
import { css } from './styles.js';

/** Each switch's settings field and its default when the namespace has no value yet. */
const SWITCHES = [
  { field: FIELD_GOVERNANCE, fallback: DEFAULT_GOVERNANCE_ENABLED },
  { field: FIELD_AUTO_ENABLE, fallback: DEFAULT_AUTO_ENABLE },
  { field: FIELD_AUTO_UPGRADE, fallback: DEFAULT_AUTO_UPGRADE },
];

/**
 * One labelled checkbox row, with the "user-overridden" mark and the reset
 * control when the field sits in the raw user layer.
 * @param {object} props - row props.
 * @param {string} props.field - the settings field this row writes.
 * @param {boolean} props.checked - current value.
 * @param {boolean} props.overridden - whether the user layer overrides this field.
 * @param {boolean} props.disabled - whether writes are accepted.
 * @param {(next: boolean) => void} props.onChange - write the new value.
 * @param {() => void} props.onReset - remove the user override.
 * @param {(key: string) => string} props.t - translator.
 * @returns {import('react').ReactElement} the row.
 */
function SwitchRow({ field, checked, overridden, disabled, onChange, onReset, t }) {
  const id = `docs-harness-${field}`;
  return (
    <div className={css.cardRow}>
      <label htmlFor={id}>
        {t(`settings.${field}`)}
        <div className={css.cardHint}>{t(`settings.${field}.hint`)}</div>
      </label>
      {overridden ? (
        <span className={css.cardActions}>
          <span className={css.overriddenMark}>{t('settings.overridden')}</span>
          <button type="button" className={css.button} disabled={disabled} onClick={onReset}>
            {t('settings.reset')}
          </button>
        </span>
      ) : null}
      <input
        id={id}
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => { onChange(event.target.checked); }}
      />
    </div>
  );
}

/**
 * The removal row: one destructive action behind a two-step confirm. Split as
 * a pure view so both states render from props and stay testable without a DOM.
 * @param {object} props - row props.
 * @param {boolean} props.confirming - whether the confirm step is showing.
 * @param {boolean} props.working - whether a removal is in flight.
 * @param {boolean} props.disabled - whether the action is reachable at all.
 * @param {(key: string) => string} props.t - translator.
 * @param {() => void} props.onAsk - show the confirm step.
 * @param {() => void} props.onConfirm - run the removal.
 * @param {() => void} props.onCancel - back out of the confirm step.
 * @returns {import('react').ReactElement} the row.
 */
export function RemoveRow({ confirming, working, disabled, t, onAsk, onConfirm, onCancel }) {
  return (
    <div className={css.cardRow}>
      <label>
        {t('settings.remove')}
        <div className={css.cardHint}>{confirming ? t('settings.remove.confirm') : t('settings.remove.hint')}</div>
      </label>
      {confirming ? (
        <span className={css.cardActions}>
          <button type="button" className={css.button} disabled={working} onClick={onConfirm}>
            {working ? t('settings.working') : t('settings.remove.confirmAction')}
          </button>
          <button type="button" className={css.button} disabled={working} onClick={onCancel}>
            {t('settings.remove.cancel')}
          </button>
        </span>
      ) : (
        <button type="button" className={css.button} disabled={disabled || working} onClick={onAsk}>
          {working ? t('settings.working') : t('settings.remove')}
        </button>
      )}
    </div>
  );
}

/**
 * @param {object} props - composed slot props.
 * @param {(selector: (snapshot: any) => any) => any} props.useHarness - bound settings-scope hook.
 * @param {(selector: (snapshot: any) => any) => any} props.useSessions - framework session-list hook.
 * @param {(field: string, value: unknown) => Promise<{ ok: boolean, message?: string }>} props.write - persist one field.
 * @param {(field: string) => Promise<{ ok: boolean, message?: string }>} props.reset - remove one field's user override.
 * @param {(key: string, params?: Record<string, unknown>) => string} props.t - translator.
 * @returns {import('react').ReactElement} the settings page.
 */
export function HarnessSettingsCard({ useHarness, useSessions, write, reset, t }) {
  const snapshot = useHarness(current => current);
  const sessionId = useSessions(list => list.current);
  const [action, setAction] = useState({ working: false, message: undefined });
  const [confirming, setConfirming] = useState(false);

  const remove = useCallback(async () => {
    setAction({ working: true, message: undefined });
    const envelope = await callHarness(ACTION_UNINSTALL, sessionId);
    setConfirming(false);
    setAction({
      working: false,
      message: envelope.ok ? t('settings.remove.done') : envelope.error?.message ?? '',
    });
  }, [sessionId, t]);

  const save = useCallback(async (field, next) => {
    const settled = await write(field, next);
    // A rejected write reloads the host section, so the switch snaps back on
    // its own; the message is what tells the user why it did.
    if (!settled.ok) setAction({ working: false, message: settled.message ?? '' });
  }, [write]);

  const restore = useCallback(async (field) => {
    const settled = await reset(field);
    if (!settled.ok) setAction({ working: false, message: settled.message ?? '' });
  }, [reset]);

  const readonly = snapshot.status !== 'ready' || !snapshot.writable;
  const values = snapshot.value ?? {};
  const userLayer = snapshot.user ?? {};

  return (
    <div className={css.card}>
      <div className={css.cardTitle}>{t('settings.title')}</div>
      <div className={css.cardHint}>{t('settings.description')}</div>
      {readonly ? <div className={`${css.cardHint} ${css.error}`}>{t('settings.unavailable')}</div> : null}
      {SWITCHES.map(({ field, fallback }) => (
        <SwitchRow
          key={field}
          field={field}
          checked={values[field] ?? fallback}
          overridden={Object.hasOwn(userLayer, field)}
          disabled={readonly}
          onChange={(next) => { void save(field, next); }}
          onReset={() => { void restore(field); }}
          t={t}
        />
      ))}
      <RemoveRow
        confirming={confirming}
        working={action.working}
        disabled={sessionId === undefined}
        t={t}
        onAsk={() => { setConfirming(true); }}
        onConfirm={() => { void remove(); }}
        onCancel={() => { setConfirming(false); }}
      />
      {sessionId === undefined ? <div className={css.cardHint}>{t('settings.noSession')}</div> : null}
      {action.message === undefined ? null : <div className={css.cardHint}>{action.message}</div>}
    </div>
  );
}
