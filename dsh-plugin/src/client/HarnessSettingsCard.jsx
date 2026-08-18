/**
 * The Docs Harness card in Settings → Plugins.
 *
 * Three switches and one destructive action. The switches write into the same
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
 * One labelled checkbox row.
 * @param {object} props - row props.
 * @param {string} props.field - the settings field this row writes.
 * @param {boolean} props.checked - current value.
 * @param {boolean} props.disabled - whether writes are accepted.
 * @param {(next: boolean) => void} props.onChange - write the new value.
 * @param {(key: string) => string} props.t - translator.
 * @returns {import('react').ReactElement} the row.
 */
function SwitchRow({ field, checked, disabled, onChange, t }) {
  const id = `docs-harness-${field}`;
  return (
    <div className={css.cardRow}>
      <label htmlFor={id}>
        {t(`settings.${field}`)}
        <div className={css.cardHint}>{t(`settings.${field}.hint`)}</div>
      </label>
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
 * @param {object} props - composed slot props.
 * @param {(selector: (snapshot: any) => any) => any} props.useHarness - bound settings-scope hook.
 * @param {(selector: (snapshot: any) => any) => any} props.useSessions - framework session-list hook.
 * @param {(field: string, value: unknown) => Promise<{ ok: boolean, message?: string }>} props.write - persist one field.
 * @param {(key: string, params?: Record<string, unknown>) => string} props.t - translator.
 * @returns {import('react').ReactElement} the card.
 */
export function HarnessSettingsCard({ useHarness, useSessions, write, t }) {
  const snapshot = useHarness(current => current);
  const sessionId = useSessions(list => list.current);
  const [action, setAction] = useState({ working: false, message: undefined });

  const remove = useCallback(async () => {
    setAction({ working: true, message: undefined });
    const envelope = await callHarness(ACTION_UNINSTALL, sessionId);
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

  const readonly = snapshot.status !== 'ready' || !snapshot.writable;
  const values = snapshot.value ?? {};

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
          disabled={readonly}
          onChange={(next) => { void save(field, next); }}
          t={t}
        />
      ))}
      <div className={css.cardRow}>
        <label>
          {t('settings.remove')}
          <div className={css.cardHint}>{t('settings.remove.hint')}</div>
        </label>
        <button
          type="button"
          className={css.button}
          disabled={action.working || sessionId === undefined}
          onClick={() => { void remove(); }}
        >
          {action.working ? t('settings.working') : t('settings.remove')}
        </button>
      </div>
      {sessionId === undefined ? <div className={css.cardHint}>{t('settings.noSession')}</div> : null}
      {action.message === undefined ? null : <div className={css.cardHint}>{action.message}</div>}
    </div>
  );
}
