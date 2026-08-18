/**
 * The model-facing tool family: the three plan-lifecycle operations that cross
 * into the Python engine, plus the progress declaration that drives the UI.
 *
 * Parameters mirror the CLI the governance rules describe, so the rules text
 * stays literally true and only the invocation shape is adapted.
 *
 * @module dsh-docs-harness/host/tools
 */

import { defineTool } from '@deepseek-ai/dsh-tools';

import {
  ITEM_STATUSES,
  TOOL_PLAN_CREATE,
  TOOL_PLAN_PROGRESS,
  TOOL_PLAN_SELECT,
  TOOL_PLAN_SETTLE,
} from '../shared/constants.js';
import { readPlanDocument, requireApproval } from './plan-review.js';
import { projectDirOf, requireEnabledProject, runForTool, withFlags } from './tool-support.js';

/** Free-form JSON result shape shared by the engine-backed tools. */
const JSON_OUTPUT = {
  schema: { type: 'json' },
  render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
};

/**
 * `harness_plan_select` — choose the plan level and profile for a task.
 * @returns {object} the tool definition.
 */
function planSelectTool() {
  return defineTool({
    name: TOOL_PLAN_SELECT,
    description:
      'Choose the Docs Harness plan level and profile for the task at hand, and return the exact '
      + 'content fields the frozen plan must fill. Call this before harness_plan_create; its `fields` '
      + 'output is the authoritative list of keys the content JSON may contain. Equivalent to '
      + '`harness.py plan select`.',
    parameters: {
      level: { type: 'string', enum: ['none', 'brief', 'full'], description: 'Force a plan level instead of inferring one.' },
      profile: { type: 'string', description: 'Force a primary profile (general, frontend_ui, backend_service, bugfix, architecture, migration_release).' },
      secondary_profile: { type: 'string', description: 'Additional profile whose fields are merged in.' },
      complexity: { type: 'string', enum: ['simple', 'moderate', 'complex'], description: 'Task complexity used to infer the level.' },
      surface: { type: 'string', description: 'Primary surface touched, used to infer the profile.' },
      cross_module: { type: 'boolean', description: 'Whether the change spans modules.' },
      high_risk: { type: 'boolean', description: 'Whether the change is irreversible or high risk.' },
      user_requested_plan: { type: 'boolean', description: 'Whether the user explicitly asked for a plan.' },
    },
    output: JSON_OUTPUT,
    execute(args, exec) {
      const flags = withFlags(['plan', 'select'], {
        '--level': args.level,
        '--profile': args.profile,
        '--secondary-profile': args.secondary_profile,
        '--complexity': args.complexity,
        '--surface': args.surface,
      });
      if (args.cross_module === true) flags.push('--cross-module');
      if (args.high_risk === true) flags.push('--high-risk');
      if (args.user_requested_plan === true) flags.push('--user-requested-plan');
      return runForTool(exec, flags);
    },
    presentCall: () => ({ card: 'generic', title: 'Docs Harness：选择方案级别', kind: 'other' }),
  });
}

/**
 * `harness_plan_create` — freeze the plan, then hold until the user rules on it.
 * @param {object} ctx - the host plugin context (for `ctx.userQuestions`).
 * @returns {object} the tool definition.
 */
function planCreateTool(ctx) {
  return defineTool({
    name: TOOL_PLAN_CREATE,
    description:
      'Freeze a plan into docs/plans and register it in docs/INDEX.md, then present it to the user '
      + 'for approval. `selection` and `content` are paths to JSON files you have already written '
      + 'inside the project; `output` is the project-relative docs/plans/<name>.json target. '
      + 'Equivalent to `harness.py plan create`. THIS TOOL BLOCKS until the user approves or '
      + 'declines: a declined plan comes back as an error and you must not start implementing.',
    parameters: {
      selection: { type: 'string', required: true, description: 'Project-relative path of the JSON written from harness_plan_select output.' },
      content: { type: 'string', required: true, description: 'Project-relative path of the plan content JSON, keyed by the selection `fields`.' },
      output: { type: 'string', required: true, description: 'Project-relative docs/plans/<name>.json path to freeze into.' },
    },
    output: JSON_OUTPUT,
    async execute(args, exec) {
      const projectDir = requireEnabledProject(exec);
      const questions = ctx.get('userQuestions');
      if (questions === undefined) {
        throw new Error('no user-questions channel is available to review the plan; ask the user to review docs/plans manually');
      }
      const payload = await runForTool(exec, withFlags(['plan', 'create'], {
        '--selection': args.selection,
        '--content': args.content,
        '--output': args.output,
      }));
      const documentRef = payload['document_ref'];
      if (typeof documentRef !== 'string') throw new Error('plan create returned no document_ref');
      await requireApproval(questions, {
        planMarkdown: readPlanDocument(projectDir, documentRef),
        agent: exec.agent,
        signal: exec.signal,
      });
      return { ...payload, approved: true };
    },
    presentCall: () => ({ card: 'generic', title: 'Docs Harness：冻结方案并请用户确认', kind: 'other' }),
  });
}

/**
 * `harness_plan_settle` — close the plan out.
 * @returns {object} the tool definition.
 */
function planSettleTool() {
  return defineTool({
    name: TOOL_PLAN_SETTLE,
    description:
      'Settle a frozen plan: `implemented` once the work landed and was verified, or `deprecated` '
      + 'when it was superseded. Equivalent to `harness.py plan settle`.',
    parameters: {
      plan: { type: 'string', required: true, description: 'Project-relative docs/plans/<name>.json path.' },
      status: { type: 'string', required: true, enum: ['implemented', 'deprecated'], description: 'How the plan ends.' },
      replacement: { type: 'string', description: 'Project-relative path of the plan that supersedes this one.' },
      governance_input: { type: 'string', description: 'Project-relative path of the governance-input JSON required by a Full plan.' },
    },
    output: JSON_OUTPUT,
    execute(args, exec) {
      return runForTool(exec, withFlags(['plan', 'settle'], {
        '--plan': args.plan,
        '--status': args.status,
        '--replacement': args.replacement,
        '--governance-input': args.governance_input,
      }));
    },
    presentCall: args => ({ card: 'generic', title: `Docs Harness：结算方案（${args.status}）`, kind: 'other' }),
  });
}

/**
 * `plan_progress` — the whole-list progress declaration behind the composer bubble.
 *
 * Whole-table replacement, like the built-in todo list: a delta protocol would
 * let a dropped call leave the user looking at a plan that never finishes.
 * @returns {object} the tool definition.
 */
function planProgressTool() {
  return defineTool({
    name: TOOL_PLAN_PROGRESS,
    description:
      'Declare the current state of the approved plan\'s task list. Send the COMPLETE list every '
      + 'time — it replaces the previous one wholesale. Mark a task in_progress before starting it '
      + 'and completed the moment it is done and verified; several tasks may be in_progress at once '
      + 'when work genuinely runs in parallel. The user watches this live above the composer, '
      + 'alongside the running count of lines you have added and removed, so it must reflect '
      + 'reality rather than intent.',
    parameters: {
      items: {
        type: 'array',
        required: true,
        description: 'The complete task list, in execution order.',
        items: {
          type: 'object',
          additionalProperties: false,
          properties: {
            content: { type: 'string', required: true, description: 'What this task delivers, in the imperative.' },
            status: { type: 'string', required: true, enum: ITEM_STATUSES, description: 'Current state of this task.' },
          },
        },
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        properties: { done: { type: 'number', required: true }, total: { type: 'number', required: true } },
      },
      render: (_args, value) => [{ type: 'text', text: `Plan progress: ${value.done}/${value.total} complete.` }],
      // The projection reads its whole list from here: `execute` has already
      // validated the shape, so what lands in the log is known-good.
      presentationMeta: args => ({ items: args.items.map(item => ({ content: item.content, status: item.status })) }),
    },
    execute(args, exec) {
      projectDirOf(exec);
      const items = args.items;
      const blank = items.find(item => item.content.trim() === '');
      if (blank !== undefined) throw new Error('plan_progress items must each carry non-empty content');
      return Promise.resolve({ done: items.filter(item => item.status === 'completed').length, total: items.length });
    },
    presentCall: args => ({
      card: 'generic',
      title: `方案进度 ${args.items.filter(item => item.status === 'completed').length}/${args.items.length}`,
      kind: 'other',
    }),
  });
}

/**
 * Build every tool this plugin registers.
 * @param {object} ctx - the host plugin context.
 * @returns {object[]} definitions in registration order.
 */
export function harnessTools(ctx) {
  return [planSelectTool(), planCreateTool(ctx), planSettleTool(), planProgressTool()];
}
