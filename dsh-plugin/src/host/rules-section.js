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
 * The adapter states that equivalence and nothing else.
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
    '规则中写作 `python3 scripts/harness.py <cmd>` 的调用，在本应用中改为等价工具，语义与参数完全一致：',
    '',
    `- \`plan select\` → 工具 \`${TOOL_PLAN_SELECT}\``,
    `- \`plan create\` → 工具 \`${TOOL_PLAN_CREATE}\``,
    `- \`plan settle\` → 工具 \`${TOOL_PLAN_SETTLE}\``,
    '- 其余子命令（knowledge / acceptance / assets-check / project）仍按规则原文经终端调用项目内的 `scripts/harness.py`。',
    '',
    `方案冻结后，用 \`${TOOL_PLAN_PROGRESS}\` 声明并推进任务清单：每次提交完整清单（整表替换），`,
    '条目状态取 `pending` / `in_progress` / `completed`。进度与代码增删行数会实时显示给用户，',
    '所以清单要如实反映当前工作，不要一次性全部标完。',
    '',
    '`plan create` 冻结方案后会请用户当面确认；用户批准前不要开始实施。',
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
