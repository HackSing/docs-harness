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
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from score import PREDICTION_SCHEMA, load_dataset  # noqa: E402

DEFAULT_CASES = HERE / "cases.json"
DEFAULT_OUTPUT = HERE.parents[1] / ".docs-harness" / "evals" / "jev-predictions.json"
BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com"
GEMINI_DECISIONS_PATH = "/v1beta/decisions"
GEMINI_DECISION_MODEL = "gemini-decision-1"
GEMINI_INPUT_PRICE_PER_MTOK = 0.10
GEMINI_DECISIONS_TIMEOUT_SECONDS = 15.0
PRIMARY_CONFIDENCE_MIN = 0.5
SECONDARY_INTENT_MIN = 0.8
CLARIFY_MIN = 0.7
AUX_MIN = 0.7

INTENT_CRITERIA = {
    "answer_only": "A question, explanation, fact lookup, diagnosis, or read-only review. The user does not ask to change or fix anything, run builds or tests, create lifecycle assets, or release.",
    "code_task": "Implement, modify, refactor, or verify code or configuration. Includes running tests or builds and executing an already-defined plan.",
    "bug_fix": "The user asks to fix a defect or produce a fix approach, not only diagnose it. Includes a bug report, error, failure, regression, or root cause when a fix is requested.",
    "plan_decision": "Produce a plan, design, architecture, tradeoff, migration or rollback strategy, or a decision before implementation. Includes cross-module or high-risk changes that need a plan first. Does not include a fix approach for a single defect.",
    "asset_lifecycle": "Create, update, record, or settle Knowledge, Acceptance, or ADR assets.",
    "release": "Bump the version, publish, package, update CHANGELOG, or sync downstream projects. Mentioning release only as timing or background does not count.",
    "docs_change": "Create or update documentation as the main deliverable. Does not include documentation that is only part of a release or code change.",
}
PRIMARY_CRITERIA = {
    **INTENT_CRITERIA,
    "unclear": "The request is too vague to choose a task type safely; ask the user before loading task modules.",
}
INTENT_NOUL_QUESTIONS = {
    "intent_answer_only": {
        "type": "noul",
        "instructions": "Does the user ask only for a question, explanation, fact lookup, diagnosis, or read-only review, without asking to change or fix anything?",
        "criteria": {
            "true": "The request is informational or diagnostic and asks for no action or deliverable.",
            "false": "The request asks to change, fix, run, create, release, or produce an artifact.",
        },
    },
    "intent_code_task": {
        "type": "noul",
        "instructions": "Does the user ask to implement, modify, refactor, or verify code or configuration?",
        "criteria": {
            "true": "Includes code or config edits, refactors, running tests/builds as the action, or implementing an existing plan.",
            "false": "The request is only a question, diagnosis, plan, documentation, asset, or release task.",
        },
    },
    "intent_bug_fix": {
        "type": "noul",
        "instructions": "Does the user ask to fix a defect or produce a fix approach, rather than only diagnose it?",
        "criteria": {
            "true": "The user reports a bug/error/failure and asks to fix it or give a fix approach.",
            "false": "The user only asks for a diagnosis or review, or the request is not about a defect.",
        },
    },
    "intent_plan_decision": {
        "type": "noul",
        "instructions": "Does the user ask for a plan, design, architecture, tradeoff, migration or rollback strategy, or a decision before implementation?",
        "criteria": {
            "true": "The user wants a plan/design/decision, or the task is cross-module/high-risk and needs a plan first.",
            "false": "The request is a single-defect fix, a local implementation, a read-only question, or another task.",
        },
    },
    "intent_asset_lifecycle": {
        "type": "noul",
        "instructions": "Does the user ask to create, update, record, or settle Knowledge, Acceptance, or ADR assets?",
        "criteria": {
            "true": "The request is about Knowledge, Acceptance/验收, ADR, evidence levels, or an asset lifecycle operation.",
            "false": "The request is about code, docs, release, or analysis instead.",
        },
    },
    "intent_release": {
        "type": "noul",
        "instructions": "Does the user ask to bump the version, publish, package, update CHANGELOG, or sync downstream projects?",
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
        "instructions": "What is the user's primary task intent? Choose unclear when the request is too vague to classify safely.",
        "criteria": PRIMARY_CRITERIA,
    },
    **INTENT_NOUL_QUESTIONS,
    "clarify_required": {
        "type": "noul",
        "instructions": "Is the request missing the target, deliverable, or scope, so the agent should ask one clarifying question before loading any task modules?",
        "criteria": {
            "true": "The request refers to an unspecified target or an open-ended change, and the task context does not resolve it.",
            "false": "The request or task context identifies the target and deliverable well enough to start.",
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
        "instructions": "Does the user ask to run tests, builds, or verification as the action, without asking for a code change?",
        "criteria": {
            "true": "The user asks to run tests/builds/verification and does not ask to modify code.",
            "false": "The user asks for code changes, an explanation, or another task, or mentions tests only as context.",
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


def _to_gemini_questions(questions: Mapping[str, Any]) -> dict[str, Any]:
    converted: dict[str, Any] = {}
    for name, spec in questions.items():
        item = dict(spec)
        criteria = item.get("criteria")
        if item.get("type") == "noul" and isinstance(criteria, Mapping):
            item["criteria"] = {
                "true_description": criteria["true"],
                "false_description": criteria["false"],
            }
        converted[name] = item
    return converted


GEMINI_QUESTIONS = _to_gemini_questions(QUESTIONS)


def is_gemini_decision_model(model: str) -> bool:
    return model.strip().lower().startswith("gemini-decision")


def build_state(case: Mapping[str, Any]) -> dict[str, str]:
    return {
        "task_context": str(case.get("setup") or ""),
        "user_request": str(case["prompt"]),
        "language": "zh-CN",
        "note": "Judge the intended task from meaning, not from literal keyword matches.",
    }


def build_decisions_payload(
    case_or_prompt: Mapping[str, Any] | str, model: str = GEMINI_DECISION_MODEL
) -> dict[str, Any]:
    case = {"setup": "", "prompt": case_or_prompt} if isinstance(case_or_prompt, str) else case_or_prompt
    return {
        "model": model,
        "input": json.dumps(build_state(case), ensure_ascii=False),
        "questions": GEMINI_QUESTIONS,
    }


def build_payload(case: dict[str, Any], model: str) -> dict[str, Any]:
    if is_gemini_decision_model(model):
        return build_decisions_payload(case, model)
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
    known_intents: Sequence[str],
    case_id: str,
) -> tuple[str, float, float, float, float, dict[str, float]]:
    if not isinstance(answers, dict):
        raise ValueError(f"{case_id} 响应缺少 answers")
    primary, primary_confidence = _require_choice(answers.get("primary_intent"), "primary_intent")
    if primary not in set(known_intents) | {"unclear"}:
        raise ValueError(f"{case_id} primary_intent 未知选项: {primary}")
    clarify = _require_noul(answers.get("clarify_required"), "clarify_required")
    direct_override = _require_noul(answers.get("direct_override"), "direct_override")
    code_verify = _require_noul(answers.get("code_verify"), "code_verify")
    intent_scores = {
        intent: _require_noul(answers.get(f"intent_{intent}"), f"intent_{intent}")
        for intent in known_intents
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


def answers_to_profile(
    answers: Any,
    known_intents: Sequence[str] = tuple(INTENT_CRITERIA),
    case_id: str = "task",
) -> dict[str, Any]:
    (
        primary,
        primary_confidence,
        clarify,
        direct_override,
        code_verify,
        intent_scores,
    ) = _parse_answers(answers, known_intents, case_id)
    intents, must_clarify = _select_intents(
        primary, primary_confidence, intent_scores, clarify
    )
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
        "intents": intents,
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
    }


def interpret_response(
    case: dict[str, Any],
    response: dict[str, Any],
    dataset: dict[str, Any],
) -> dict[str, Any]:
    answers = response.get("answers")
    profile = answers_to_profile(answers, dataset["labels"]["intents"], case["id"])
    intents = profile["intents"]
    must_clarify = profile["must_clarify"]
    modules = [] if must_clarify else sorted({
        module
        for intent in intents
        for module in dataset["intent_modules"][intent]
    })
    return {
        "id": case["id"],
        "intents": intents,
        "modules": modules,
        "triggers": profile["triggers"],
        "must_clarify": must_clarify,
        "confidence": profile["confidence"],
        "evidence": profile["evidence"],
        "raw": {
            "model": response.get("model"),
            "answers": answers,
            "usage": response.get("usage", {}),
        },
    }


def extract_usage(response: Mapping[str, Any]) -> tuple[int, int]:
    usage = response.get("usage")
    if not isinstance(usage, Mapping):
        return 0, 0
    tokens_in = int(usage.get("total_input_tokens", usage.get("input_tokens", 0)) or 0)
    tokens_out = int(usage.get("total_output_tokens", usage.get("output_tokens", 0)) or 0)
    return tokens_in, tokens_out


def _retry_delay(value: str | None, fallback: float) -> float:
    try:
        return float(value) if value is not None else fallback
    except ValueError:
        return fallback


def _post_json_with_retry(
    url: str,
    payload: Mapping[str, Any],
    headers: Mapping[str, str],
    provider_label: str,
    timeout: float,
    retries: int,
) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    is_local = url.startswith(("http://127.0.0.1", "http://localhost"))
    opener = (
        urllib.request.build_opener(urllib.request.ProxyHandler({}))
        if is_local
        else urllib.request.build_opener()
    )
    for attempt in range(retries):
        request = urllib.request.Request(
            url, data=data, method="POST", headers=dict(headers)
        )
        try:
            with opener.open(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            retryable = exc.code == 429 or 500 <= exc.code < 600
            if retryable and attempt + 1 < retries:
                time.sleep(_retry_delay(exc.headers.get("Retry-After"), 2 ** attempt))
                continue
            raise RuntimeError(f"{provider_label} HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"{provider_label} request failed: {exc.reason}") from exc
    raise RuntimeError(f"{provider_label} request failed after retries")


def call_systemone(
    payload: dict[str, Any],
    api_key: str,
    base_url: str,
    timeout: float = 60.0,
    retries: int = 3,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/v1/systemone"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return _post_json_with_retry(url, payload, headers, "TypeSafe", timeout, retries)


def call_gemini_decisions(
    payload: Mapping[str, Any],
    api_key: str,
    base_url: str = GEMINI_BASE_URL,
    timeout: float = 60.0,
    retries: int = 3,
) -> dict[str, Any]:
    url = base_url.rstrip("/") + GEMINI_DECISIONS_PATH
    headers = {
        "x-goog-api-key": api_key,
        "Content-Type": "application/json",
    }
    return _post_json_with_retry(
        url, payload, headers, "Gemini Decisions", timeout, retries
    )


def _gemini_api_key(explicit: str | None = None) -> str:
    direct = (explicit or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "").strip()
    if direct:
        return direct
    env_file = os.environ.get("DOCS_HARNESS_GEMINI_ENV_FILE", "").strip()
    if env_file and Path(env_file).is_file():
        for raw in Path(env_file).read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                if k.strip() in {"GEMINI_API_KEY", "GOOGLE_API_KEY"} and v.strip():
                    return v.strip().strip("\"'")
    return ""


def route_prompt_with_decisions(
    prompt: str,
    *,
    model: str = GEMINI_DECISION_MODEL,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float = GEMINI_DECISIONS_TIMEOUT_SECONDS,
) -> tuple[dict[str, Any], dict[str, Any]]:
    resolved_key = _gemini_api_key(api_key)
    if not resolved_key:
        raise ValueError("gemini_api_key_missing")
    resolved_url = (
        base_url or os.environ.get("DOCS_HARNESS_DECISIONS_BASE_URL") or GEMINI_BASE_URL
    ).strip()
    payload = build_decisions_payload(prompt, model=model)
    response = call_gemini_decisions(payload, resolved_key, resolved_url, timeout=timeout, retries=2)
    if not isinstance(response, Mapping):
        raise ValueError("decisions_response_not_object")
    profile = answers_to_profile(response.get("answers"))
    profile["evidence"] = profile["evidence"][:8]
    tokens_in, tokens_out = extract_usage(response)
    metadata: dict[str, Any] = {
        "name": str(response.get("model") or model),
        "version": "v1beta",
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": round(tokens_in * GEMINI_INPUT_PRICE_PER_MTOK / 1_000_000, 8),
    }
    return profile, metadata


def _load_cases(path: Path) -> dict[str, Any]:
    dataset = load_dataset(path)
    known = set(dataset["labels"]["intents"])
    if set(INTENT_CRITERIA) != known:
        raise ValueError(
            f"INTENT_CRITERIA 与数据集 intents 不一致: {sorted(set(INTENT_CRITERIA) ^ known)}"
        )
    return dataset


def _resolve_cli_backend(
    model: str, base_url: str | None
) -> tuple[str, str, str, Any]:
    if is_gemini_decision_model(model):
        api_key = _gemini_api_key()
        if not api_key:
            raise ValueError("GEMINI_API_KEY 未设置")
        return (
            "gemini-decision",
            api_key,
            base_url or GEMINI_BASE_URL,
            call_gemini_decisions,
        )
    api_key = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if not api_key:
        raise ValueError("TYPESAFE_API_KEY 未设置")
    return "jev", api_key, base_url or BASE_URL, call_systemone


def _run_batch(
    cases: list[dict[str, Any]],
    payloads: list[dict[str, Any]],
    dataset: dict[str, Any],
    caller: Any,
    api_key: str,
    base_url: str,
) -> tuple[list[dict[str, Any]], set[str], int, int]:
    predictions = []
    models: set[str] = set()
    input_tokens = 0
    output_tokens = 0
    for index, (case, payload) in enumerate(zip(cases, payloads), start=1):
        print(f"[{index}/{len(cases)}] {case['id']}", file=sys.stderr)
        response = caller(payload, api_key, base_url)
        predictions.append(interpret_response(case, response, dataset))
        if response.get("model"):
            models.add(str(response["model"]))
        tokens_in, tokens_out = extract_usage(response)
        input_tokens += tokens_in
        output_tokens += tokens_out
    return predictions, models, input_tokens, output_tokens


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="用 Jev 或 Gemini Decisions 生成意图路由基线预测")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=None)
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
        predictor, api_key, base_url, caller = _resolve_cli_backend(
            args.model, args.base_url
        )
        predictions, models, input_tokens, output_tokens = _run_batch(
            cases, payloads, dataset, caller, api_key, base_url
        )
        result = {
            "schema_version": PREDICTION_SCHEMA,
            "predictor": predictor,
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
