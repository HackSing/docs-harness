/**
 * The user's decision on a freshly frozen plan.
 *
 * This reuses the shipped `plan-review` question intent rather than inventing
 * one. Custom intents are not an option: the wire schema validates `intent` as
 * a closed discriminated union, so an unknown tag makes the host reject the
 * whole frame and the question never reaches any UI. Reusing `plan-review`
 * also means the approve / refuse / discuss card the user already knows
 * renders this, with no client code of ours in the path.
 *
 * @module dsh-docs-harness/host/plan-review
 */

import fs from 'node:fs';
import path from 'node:path';

/** Question id, echoed back in the answer. */
export const REVIEW_ID = 'docs-harness-plan-review';

/** Label of the option that approves; must match one of the offered options. */
export const APPROVE_LABEL = '批准方案';

/** Label of the option that declines. */
export const DECLINE_LABEL = '退回修改';

/** Error code the host raises when the user dismissed the card to talk instead. */
const CANCELLED = 'ASK_CANCELLED';

/**
 * Build the review question for one frozen plan.
 * @param {string} planMarkdown - the frozen plan document, shown verbatim.
 * @returns {object} the `AskUserQuestionItem`.
 */
export function reviewQuestion(planMarkdown) {
  return {
    id: REVIEW_ID,
    header: 'Docs Harness 方案确认',
    question: '批准这份方案并开始实施？',
    detail: planMarkdown,
    options: [
      { label: APPROVE_LABEL, description: '冻结合同生效，智能体按方案实施。' },
      { label: DECLINE_LABEL, description: '退回修改；你的意见回到模型。' },
    ],
    intent: { kind: 'plan-review', approve: APPROVE_LABEL },
  };
}

/**
 * Read the frozen plan document the engine just wrote.
 * @param {string} projectDir - absolute project root.
 * @param {string} documentRef - project-relative markdown path from the engine.
 * @returns {string} the document text.
 */
export function readPlanDocument(projectDir, documentRef) {
  return fs.readFileSync(path.join(projectDir, documentRef), 'utf8');
}

/**
 * Put the plan in front of the user and translate the outcome.
 *
 * A decline and a dismissal both throw, which is the tool-error path back to
 * the model: it is what stops implementation from starting, and it carries the
 * reason the model needs in order to respond usefully.
 * @param {object} questions - the `ctx.userQuestions` service.
 * @param {object} request - the ask.
 * @param {string} request.planMarkdown - the frozen document.
 * @param {object} request.agent - the calling agent.
 * @param {AbortSignal} request.signal - the tool's cancellation signal.
 * @returns {Promise<void>} resolves only on approval.
 * @throws {Error} when the user declines, dismisses, or the ask fails.
 */
export async function requireApproval(questions, { planMarkdown, agent, signal }) {
  const answer = await questions
    .ask({ questions: [reviewQuestion(planMarkdown)], agent, signal })
    .catch((cause) => {
      if (cause?.code === CANCELLED) {
        throw new Error(
          '用户关掉了方案确认卡片，改为直接说话。方案已冻结但未获批准：停在这里，不要开始实施，等用户的下一条消息。',
        );
      }
      throw cause;
    });
  const item = answer.answers.find(entry => entry.id === REVIEW_ID);
  if (item?.selected.length === 1 && item.selected[0] === APPROVE_LABEL) return;
  const feedback = item?.custom ?? '';
  throw new Error(feedback === ''
    ? '用户退回了这份方案。按用户意见修订后重新冻结，不要开始实施。'
    : `用户退回了这份方案，意见：${feedback}`);
}
