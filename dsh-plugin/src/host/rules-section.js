/**
 * The governance prompt section.
 *
 * The body is the project's AGENTS.md managed block, verbatim and complete —
 * no summarising, no reordering, no dropped clauses. Rewriting it here would
 * fork the rules from the file the user reads and the engine maintains, and a
 * fork is worse than the tokens it saves.
 *
 * Only one thing is added: the block tells an agent to invoke `python3
 * scripts/harness.py …`, and in this app the same operations arrive as tools.
 * The adapter states that equivalence AND forbids the terminal path for the
 * plan operations — a model that runs `plan create` through the shell bypasses
 * the blocking user approval and the plan projection, leaving the UI with no
 * plan to show. The prohibition leads the note because a weak model follows
 * whichever phrasing dominates, and the verbatim body is full of CLI spelling.
 *
 * @module dsh-docs-harness/host/rules-section
 */

import {
  TOOL_PLAN_CREATE,
  TOOL_PLAN_PROGRESS,
  TOOL_PLAN_SELECT,
  TOOL_PLAN_SETTLE,
} from '../shared/constants.js';

/**
 * How to run the operations the rules above name, in this application.
 * @returns {string} the adapter block appended after the verbatim rules.
 */
export function toolAdapterNote() {
  return [
    '## 在本应用中如何调用上述能力',
    '',
    '上述规则正文来自本项目的 AGENTS.md 受管块，已完整注入，**不需要再读取该文件**。',
    '',
    `**禁止经终端执行 \`plan select\` / \`plan create\` / \`plan settle\`。** 规则正文、方案文档和历史文档中`,
    '写作 `python3 scripts/harness.py plan ...` 的这三条命令，在本应用中一律改用下列等价工具，语义与参数完全一致。',
    '经终端执行会绕过用户确认和进度投影，方案审批与进度气泡都不会出现，属于流程违规：',
    '',
    `- \`plan select\` → 工具 \`${TOOL_PLAN_SELECT}\``,
    `- \`plan create\` → 工具 \`${TOOL_PLAN_CREATE}\`（冻结后会请用户当面确认；用户批准前不要开始实施）`,
    `- \`plan settle\` → 工具 \`${TOOL_PLAN_SETTLE}\``,
    '',
    `方案冻结后，用 \`${TOOL_PLAN_PROGRESS}\` 声明并推进任务清单：每次提交完整清单（整表替换），`,
    '条目状态取 `pending` / `in_progress` / `completed`。进度与代码增删行数会实时显示给用户，',
    '所以清单要如实反映当前工作，不要一次性全部标完。',
    `执行方案期间不要再使用内置待办工具：进度一律以 \`${TOOL_PLAN_PROGRESS}\` 为准，避免两套进度互相矛盾。`,
    '',
    '其余子命令（knowledge / acceptance / assets-check / project）仍按规则原文经终端调用项目内的 `scripts/harness.py`。',
  ].join('\n');
}

/**
 * Assemble the full section text for one project.
 * @param {{ text: string, source: 'project' | 'seed' } | undefined} rules - the extracted managed block.
 * @returns {string} the section text, or `''` when there are no rules to inject.
 */
export function buildRulesSection(rules) {
  if (rules === undefined) return '';
  return `${rules.text}\n\n${toolAdapterNote()}`;
}
