#!/usr/bin/env python3
"""Jev intent predictor for the intent routing baseline.

One TypeSafe System One request per case: a primary Choice, a secondary Choice,
and three Noul checks (clarify, direct override, code verification). The model
only produces an intent profile; modules and triggers are mapped here.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from score import PREDICTION_SCHEMA, load_dataset  # noqa: E402

DEFAULT_CASES = HERE / "cases.json"
DEFAULT_OUTPUT = HERE.parents[1] / ".docs-harness" / "evals" / "jev-predictions.json"
BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"
PRIMARY_CONFIDENCE_MIN = 0.5
SECONDARY_INTENT_MIN = 0.8
CLARIFY_MIN = 0.7
AUX_MIN = 0.7

INTENT_CRITERIA = {
    "answer_only": (
        "A question, explanation, fact lookup, diagnosis, or read-only review. The user does not "
        "ask to change or fix anything, run builds or tests, create lifecycle assets, or release."
    ),
    "code_task": (
        "Implement, modify, refactor, or verify code or configuration. Includes running tests or "
        "builds and executing an already-defined plan."
    ),
    "bug_fix": (
        "The user asks to fix a defect or produce a fix approach, not only diagnose it. Includes "
        "a bug report, error, failure, regression, or root cause when a fix is requested."
    ),
    "plan_decision": (
        "Produce a plan, design, architecture, tradeoff, migration or rollback strategy, or a "
        "decision before implementation. Includes cross-module or high-risk changes that need a "
        "plan first. Does not include a fix approach for a single defect."
    ),
    "asset_lifecycle": (
        "Create, update, record, or settle Knowledge, Acceptance, or ADR assets."
    ),
    "release": (
        "Bump the version, publish, package, update CHANGELOG, or sync downstream projects. "
        "Mentioning release only as timing or background does not count."
    ),
    "docs_change": (
        "Create or update documentation as the main deliverable. Does not include documentation "
        "that is only part of a release or code change."
    ),
}
PRIMARY_CRITERIA = {
    **INTENT_CRITERIA,
    "unclear": (
        "The request is too vague to choose a task type safely; ask the user before loading task modules."
    ),
}
INTENT_NOUL_QUESTIONS = {
    "intent_answer_only": {
        "type": "noul",
        "instructions": (
            "Does the user ask only for a question, explanation, fact lookup, diagnosis, or "
            "read-only review, without asking to change or fix anything?"
        ),
        "criteria": {
            "true": "The request is informational or diagnostic and asks for no action or deliverable.",
            "false": "The request asks to change, fix, run, create, release, or produce an artifact.",
        },
    },
    "intent_code_task": {
        "type": "noul",
        "instructions": (
            "Does the user ask to implement, modify, refactor, or verify code or configuration?"
        ),
        "criteria": {
            "true": "Includes code or config edits, refactors, running tests/builds as the action, or implementing an existing plan.",
            "false": "The request is only a question, diagnosis, plan, documentation, asset, or release task.",
        },
    },
    "intent_bug_fix": {
        "type": "noul",
        "instructions": (
            "Does the user ask to fix a defect or produce a fix approach, rather than only diagnose it?"
        ),
        "criteria": {
            "true": "The user reports a bug/error/failure and asks to fix it or give a fix approach.",
            "false": "The user only asks for a diagnosis or review, or the request is not about a defect.",
        },
    },
    "intent_plan_decision": {
        "type": "noul",
        "instructions": (
            "Does the user ask for a plan, design, architecture, tradeoff, migration or rollback "
            "strategy, or a decision before implementation?"
        ),
        "criteria": {
            "true": "The user wants a plan/design/decision, or the task is cross-module/high-risk and needs a plan first.",
            "false": "The request is a single-defect fix, a local implementation, a read-only question, or another task.",
        },
    },
    "intent_asset_lifecycle": {
        "type": "noul",
        "instructions": (
            "Does the user ask to create, update, record, or settle Knowledge, Acceptance, or ADR assets?"
        ),
        "criteria": {
            "true": "The request is about Knowledge, Acceptance/验收, ADR, evidence levels, or an asset lifecycle operation.",
            "false": "The request is about code, docs, release, or analysis instead.",
        },
    },
    "intent_release": {
        "type": "noul",
        "instructions": (
            "Does the user ask to bump the version, publish, package, update CHANGELOG, or sync "
            "downstream projects?"
        ),
        "criteria": {
            "true": "The user asks for a version bump, release, publish, packaging, CHANGELOG update, or downstream sync.",
            "false": "Release is only timing/background, such as 'before release, run tests', or the request is another task.",
        },
    },
    "intent_docs_change": {
        "type": "noul",
        "instructions": "Does the user ask to create or update documentation as the main deliverable?",
        "criteria": {
            "true": "Documentation is the main deliverable: README, user guide, installation steps, or similar.",
            "false": "Documentation is only part of a release or code change, or the request is another task.",
        },
    },
}
QUESTIONS = {
    "primary_intent": {
        "type": "choice",
        "instructions": (
            "What is the user's primary task intent? Choose unclear when the request is too "
            "vague to classify safely."
        ),
        "criteria": PRIMARY_CRITERIA,
    },
    **INTENT_NOUL_QUESTIONS,
    "clarify_required": {
        "type": "noul",
        "instructions": (
            "Is the request missing the target, deliverable, or scope, so the agent should ask "
            "one clarifying question before loading any task modules?"
        ),
        "criteria": {
            "true": (
                "The request refers to an unspecified target or an open-ended change, and the "
                "task context does not resolve it."
            ),
            "false": (
                "The request or task context identifies the target and deliverable well enough "
                "to start."
            ),
        },
    },
    "direct_override": {
        "type": "noul",
        "instructions": "Does the user explicitly say not to use Harness?",
        "criteria": {
            "true": "The user says not to use Harness, in Chinese or English.",
            "false": "The user does not explicitly opt out of Harness.",
        },
    },
    "code_verify": {
        "type": "noul",
        "instructions": (
            "Does the user ask to run tests, builds, or verification as the action, without "
            "asking for a code change?"
        ),
        "criteria": {
            "true": "The user asks to run tests/builds/verification and does not ask to modify code.",
            "false": (
                "The user asks for code changes, an explanation, or another task, or mentions "
                "tests only as context."
            ),
        },
    },
}
INTENT_TRIGGERS = {
    "answer_only": ["read_only"],
    "code_task": ["code_edit"],
    "bug_fix": ["bug_report"],
    "plan_decision": ["plan_required"],
    "asset_lifecycle": ["asset_operation"],
    "release": ["release"],
    "docs_change": ["docs_edit"],
}


def build_state(case: dict[str, Any]) -> dict[str, str]:
    return {
        "task_context": case["setup"],
        "user_request": case["prompt"],
        "language": "zh-CN",
        "note": "Judge the intended task from meaning, not from literal keyword matches.",
    }


def build_payload(case: dict[str, Any], model: str) -> dict[str, Any]:
    return {"model": model, "state": build_state(case), "questions": QUESTIONS}


def _require_choice(answer: Any, name: str) -> tuple[str, float]:
    if not isinstance(answer, dict) or answer.get("type") != "choice":
        raise ValueError(f"{name} 不是 choice 答案")
    choice = answer.get("choice")
    confidence = answer.get("confidence")
    if not isinstance(choice, str) or not isinstance(confidence, (int, float)):
        raise ValueError(f"{name} 缺少 choice/confidence")
    return choice, float(confidence)


def _require_noul(answer: Any, name: str) -> float:
    if not isinstance(answer, dict) or answer.get("type") != "noul":
        raise ValueError(f"{name} 不是 noul 答案")
    value = answer.get("noul")
    if not isinstance(value, (int, float)):
        raise ValueError(f"{name} 缺少 noul")
    return float(value)


def _triggers_for(intents: list[str], direct_override: float, code_verify: float) -> list[str]:
    triggers: list[str] = []
    for intent in intents:
        triggers.extend(INTENT_TRIGGERS[intent])
    if "code_task" in intents and code_verify >= AUX_MIN:
        triggers.append("code_verify")
    if direct_override >= AUX_MIN:
        triggers.append("direct_override")
    return sorted(set(triggers))


def _parse_answers(
    answers: Any,
    dataset: dict[str, Any],
    case_id: str,
) -> tuple[str, float, float, float, float, dict[str, float]]:
    if not isinstance(answers, dict):
        raise ValueError(f"{case_id} 响应缺少 answers")
    primary, primary_confidence = _require_choice(answers.get("primary_intent"), "primary_intent")
    if primary not in set(dataset["labels"]["intents"]) | {"unclear"}:
        raise ValueError(f"{case_id} primary_intent 未知选项: {primary}")
    clarify = _require_noul(answers.get("clarify_required"), "clarify_required")
    direct_override = _require_noul(answers.get("direct_override"), "direct_override")
    code_verify = _require_noul(answers.get("code_verify"), "code_verify")
    intent_scores = {
        intent: _require_noul(answers.get(f"intent_{intent}"), f"intent_{intent}")
        for intent in dataset["labels"]["intents"]
    }
    return primary, primary_confidence, clarify, direct_override, code_verify, intent_scores


def _select_intents(
    primary: str,
    primary_confidence: float,
    intent_scores: dict[str, float],
    clarify: float,
) -> tuple[list[str], bool]:
    selected: set[str] = set()
    if primary != "unclear":
        selected.add(primary)
    selected.update(
        intent for intent, score in intent_scores.items() if score >= SECONDARY_INTENT_MIN
    )
    action_intents = {
        "code_task", "bug_fix", "plan_decision", "asset_lifecycle", "release", "docs_change",
    }
    if "answer_only" in selected and selected & action_intents:
        selected.discard("answer_only")
    must_clarify = (
        primary == "unclear"
        or primary_confidence < PRIMARY_CONFIDENCE_MIN
        or clarify >= CLARIFY_MIN
        or not selected
    )
    return sorted(selected), must_clarify


def interpret_response(
    case: dict[str, Any],
    response: dict[str, Any],
    dataset: dict[str, Any],
) -> dict[str, Any]:
    answers = response.get("answers")
    (
        primary,
        primary_confidence,
        clarify,
        direct_override,
        code_verify,
        intent_scores,
    ) = _parse_answers(answers, dataset, case["id"])
    intents, must_clarify = _select_intents(
        primary, primary_confidence, intent_scores, clarify
    )
    modules = [] if must_clarify else sorted({
        module
        for intent in intents
        for module in dataset["intent_modules"][intent]
    })
    triggers = ["clarify_required"] if must_clarify else _triggers_for(
        intents, direct_override, code_verify
    )
    if not intents:
        confidence = 0.0
    elif must_clarify:
        confidence = min(primary_confidence, 1.0 - clarify)
    else:
        confidence = primary_confidence
    return {
        "id": case["id"],
        "intents": intents,
        "modules": modules,
        "triggers": triggers,
        "must_clarify": must_clarify,
        "confidence": round(confidence, 4),
        "evidence": [
            f"primary={primary} ({primary_confidence:.2f})",
            *[f"{intent}={score:.2f}" for intent, score in sorted(intent_scores.items())],
            f"clarify={clarify:.2f}",
            f"direct_override={direct_override:.2f}",
            f"code_verify={code_verify:.2f}",
        ],
        "raw": {
            "model": response.get("model"),
            "answers": answers,
            "usage": response.get("usage", {}),
        },
    }


def _retry_delay(value: str | None, fallback: float) -> float:
    try:
        return float(value) if value is not None else fallback
    except ValueError:
        return fallback


def call_systemone(
    payload: dict[str, Any],
    api_key: str,
    base_url: str,
    timeout: float = 60.0,
    retries: int = 3,
) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    url = base_url.rstrip("/") + "/v1/systemone"
    for attempt in range(retries):
        request = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if retryable and attempt + 1 < retries:
                time.sleep(_retry_delay(exc.headers.get("Retry-After"), 2 ** attempt))
                continue
            raise RuntimeError(f"TypeSafe HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"TypeSafe request failed: {exc.reason}") from exc
    raise RuntimeError("TypeSafe request failed after retries")


def _load_cases(path: Path) -> dict[str, Any]:
    dataset = load_dataset(path)
    known = set(dataset["labels"]["intents"])
    if set(INTENT_CRITERIA) != known:
        raise ValueError(
            f"INTENT_CRITERIA 与数据集 intents 不一致: {sorted(set(INTENT_CRITERIA) ^ known)}"
        )
    return dataset


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="用 Jev 生成意图路由基线预测")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        dataset = _load_cases(args.cases)
        cases = dataset["cases"][:args.limit] if args.limit else dataset["cases"]
        payloads = [build_payload(case, args.model) for case in cases]
        if args.dry_run:
            print(json.dumps(payloads[0], ensure_ascii=False, indent=2))
            return 0
        api_key = os.environ.get("TYPESAFE_API_KEY")
        if not api_key:
            print("error: TYPESAFE_API_KEY 未设置", file=sys.stderr)
            return 2
        predictions = []
        models: set[str] = set()
        input_tokens = 0
        output_tokens = 0
        for index, (case, payload) in enumerate(zip(cases, payloads), start=1):
            print(f"[{index}/{len(cases)}] {case['id']}", file=sys.stderr)
            response = call_systemone(payload, api_key, args.base_url)
            predictions.append(interpret_response(case, response, dataset))
            if response.get("model"):
                models.add(str(response["model"]))
            usage = response.get("usage") or {}
            input_tokens += int(usage.get("input_tokens", 0))
            output_tokens += int(usage.get("output_tokens", 0))
        result = {
            "schema_version": PREDICTION_SCHEMA,
            "predictor": "jev",
            "model": ",".join(sorted(models)) if models else args.model,
            "thresholds": {
                "primary_confidence_min": PRIMARY_CONFIDENCE_MIN,
                "secondary_intent_min": SECONDARY_INTENT_MIN,
                "clarify_min": CLARIFY_MIN,
                "aux_min": AUX_MIN,
            },
            "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens},
            "case_count": len(predictions),
            "predictions": predictions,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
