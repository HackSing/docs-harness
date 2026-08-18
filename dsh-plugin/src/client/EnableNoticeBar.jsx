/**
 * The enable/upgrade notice bar.
 *
 * This is the ONLY place in the product that can start writing Docs Harness
 * files into a repository, and it does so from a click — never from an agent
 * decision, never from a heuristic about the project. Auto-enable and
 * auto-upgrade exist as settings, off by default, and even then the action runs
 * through this same bar so the user sees what happened.
 *
 * While an operation runs the bar shows a spinner and disables its buttons. It
 * does NOT block the composer: a Python subprocess writing template files is no
 * reason the user cannot keep typing.
 *
 * The file is split the way the code standards ask for: {@link NoticeBarView}
 * renders and nothing else, {@link readNotice} reduces a wire envelope and
 * nothing else, and only {@link EnableNoticeBar} touches the network.
 *
 * @module dsh-docs-harness/client/EnableNoticeBar
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import {
  ACTION_INIT,
  ACTION_STATUS,
  ACTION_UPGRADE,
  DEFAULT_AUTO_ENABLE,
  DEFAULT_AUTO_UPGRADE,
  PROMPT_ENABLE,
  PROMPT_UPGRADE,
} from '../shared/constants.js';
import { CODE_ABSENT, callHarness } from './api.js';
import { css } from './styles.js';

/** Which write action each prompt state offers. */
export const ACTION_FOR = { [PROMPT_ENABLE]: ACTION_INIT, [PROMPT_UPGRADE]: ACTION_UPGRADE };

/** Nothing to show: no answer yet, or a prepared project, or a hidden capability. */
export const SILENT = Object.freeze({ prompt: undefined, dir: undefined, versions: undefined, error: undefined });

/**
 * Reduce one route envelope to what the bar renders.
 * @param {import('./api.js').HarnessEnvelope} envelope - the host's answer.
 * @returns {{ prompt?: string, dir?: string, versions?: object, error?: string }} the bar's state.
 */
export function readNotice(envelope) {
  if (!envelope.ok) {
    // A missing route means governance is switched off — a deliberate state,
    // not a failure to report at the user.
    if (envelope.error?.code === CODE_ABSENT || envelope.error?.code === 'no-session') return SILENT;
    return { ...SILENT, error: envelope.error?.message ?? '' };
  }
  const state = envelope.value?.state;
  if (state?.prompt === undefined || ACTION_FOR[state.prompt] === undefined) return SILENT;
  return {
    prompt: state.prompt,
    dir: envelope.value?.dir,
    versions: { from: state.projectVersion ?? '', to: state.seedVersion ?? '' },
    error: undefined,
  };
}

/**
 * The bar itself. Pure: everything it shows arrives as a prop.
 * @param {object} props - view props.
 * @param {{ prompt?: string, dir?: string, versions?: object, error?: string }} props.notice - reduced state.
 * @param {boolean} props.working - whether an operation is in flight.
 * @param {(key: string, params?: Record<string, unknown>) => string} props.t - translator.
 * @param {() => void} props.onAct - run the offered action.
 * @param {() => void} props.onDismiss - stop offering it for this project.
 * @returns {import('react').ReactElement | null} the bar, or null when there is nothing to say.
 */
export function NoticeBarView({ notice, working, t, onAct, onDismiss }) {
  if (notice.error !== undefined) {
    return <div className={css.bar} role="status">{t('notice.failed', { message: notice.error })}</div>;
  }
  if (notice.prompt === undefined) return null;
  const message = notice.prompt === PROMPT_UPGRADE
    ? t('notice.upgrade', notice.versions ?? {})
    : t('notice.enable');
  return (
    <div className={css.bar} role="status" aria-busy={working}>
      {working ? <span className={css.spinner} aria-hidden="true" /> : null}
      <span className={css.barText}>{working ? t('notice.working') : message}</span>
      <span className={css.barActions}>
        <button type="button" className={`${css.button} ${css.buttonPrimary}`} disabled={working} onClick={onAct}>
          {t(`notice.${notice.prompt}.action`)}
        </button>
        <button
          type="button"
          className={css.button}
          disabled={working || notice.dir === undefined}
          onClick={onDismiss}
        >
          {t('notice.dismiss')}
        </button>
      </span>
    </div>
  );
}

/**
 * @param {object} props - composed slot props.
 * @param {string} props.sessionId - the framework-resolved session id.
 * @param {(key: string, params?: Record<string, unknown>) => string} props.t - translator.
 * @param {(selector: (snapshot: any) => any) => any} props.useHarness - bound settings-scope hook.
 * @param {(dir: string) => void} props.onDismiss - persist one more dismissal.
 * @returns {import('react').ReactElement | null} the bar, or null when there is nothing to say.
 */
export function EnableNoticeBar({ sessionId, t, useHarness, onDismiss }) {
  // The selector reads the settled section object, whose reference is stable
  // between changes — returning a fresh literal here would re-render forever.
  const settings = useHarness(snapshot => snapshot.value);
  const [notice, setNotice] = useState(SILENT);
  const [working, setWorking] = useState(false);
  // The ref closes the same-render window: two clicks before the state flush
  // would otherwise start two engine subprocesses on one repository.
  const busy = useRef(false);

  const run = useCallback(async (action) => {
    if (busy.current) return;
    busy.current = true;
    setWorking(true);
    const envelope = await callHarness(action, sessionId);
    busy.current = false;
    setWorking(false);
    setNotice(readNotice(envelope));
  }, [sessionId]);

  useEffect(() => {
    const controller = new AbortController();
    setNotice(SILENT);
    void callHarness(ACTION_STATUS, sessionId, controller.signal).then((envelope) => {
      if (!controller.signal.aborted) setNotice(readNotice(envelope));
    });
    return () => { controller.abort(); };
  }, [sessionId]);

  const prompt = notice.prompt;
  const auto = prompt === PROMPT_ENABLE ? settings?.autoEnable ?? DEFAULT_AUTO_ENABLE
    : prompt === PROMPT_UPGRADE ? settings?.autoUpgrade ?? DEFAULT_AUTO_UPGRADE
      : false;
  // Automatic modes are still this bar's action, taken once the answer arrives.
  useEffect(() => {
    if (auto && prompt !== undefined) void run(ACTION_FOR[prompt]);
  }, [auto, prompt, run]);

  const hidden = notice.dir !== undefined && (settings?.dismissed ?? []).includes(notice.dir);
  if (hidden) return null;
  return (
    <NoticeBarView
      notice={notice}
      working={working}
      t={t}
      onAct={() => { if (prompt !== undefined) void run(ACTION_FOR[prompt]); }}
      onDismiss={() => { if (notice.dir !== undefined) onDismiss(notice.dir); }}
    />
  );
}
