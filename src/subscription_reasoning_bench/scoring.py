from __future__ import annotations

import math
import re
from typing import Any

from .models import Task


FINAL_TAG = re.compile(r"<final_answer>\s*(.*?)\s*</final_answer>", re.IGNORECASE | re.DOTALL)
FINAL_PREFIX = re.compile(r"(?:the\s+)?final\s+answer\s*(?:is|:)\s*(.+)", re.IGNORECASE)


def extract_final_answer(response: str) -> str:
    matches = FINAL_TAG.findall(response)
    if matches:
        return matches[-1].strip()
    for line in reversed(response.splitlines()):
        match = FINAL_PREFIX.search(line.strip())
        if match:
            return match.group(1).strip()
    lines = [line.strip() for line in response.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _strip_latex(value: str) -> str:
    value = value.strip()
    if value.startswith("$") and value.endswith("$"):
        value = value[1:-1]
    for marker in (r"\boxed{", r"\text{", r"\texttt{"):
        if marker in value and value.endswith("}"):
            value = value.rsplit(marker, 1)[-1][:-1]
    return value


def normalize(value: str) -> str:
    value = _strip_latex(value).strip().lower()
    value = value.replace("**", "").replace(", ", ",")
    value = value[:-1] if value.endswith(".") else value
    return " ".join(value.split())


def bbeh_match(prediction: str, reference: str) -> bool:
    prediction = normalize(prediction).splitlines()[0]
    reference = normalize(reference)
    if prediction == reference:
        return True
    if len(prediction) == 3 and prediction[0] == "(" and prediction[-1] == ")":
        if prediction[1] == reference:
            return True
    if len(reference) == 3 and reference[0] == "(" and reference[-1] == ")":
        if reference[1] == prediction:
            return True
    try:
        if math.isclose(float(prediction), float(reference), rel_tol=0.0, abs_tol=0.0):
            return True
    except ValueError:
        pass
    if prediction.replace("'", "") == reference.replace("'", ""):
        return True
    if prediction == f"[{reference}]" or reference == f"[{prediction}]":
        return True
    return prediction.endswith("?") and prediction[:-1] == reference


def score_response(task: Task, response: str) -> tuple[str, float]:
    answer = extract_final_answer(response)
    if task.scorer == "exact":
        return answer, float(normalize(answer) == normalize(task.reference))
    if task.scorer == "bbeh":
        return answer, float(bbeh_match(answer, task.reference))
    if task.scorer == "numeric":
        try:
            return answer, float(math.isclose(float(answer), float(task.reference), rel_tol=1e-9, abs_tol=1e-9))
        except ValueError:
            return answer, 0.0
    if task.scorer == "regex":
        return answer, float(re.fullmatch(task.reference, answer, re.IGNORECASE) is not None)
    if task.scorer == "contains":
        return answer, float(normalize(task.reference) in normalize(answer))
    if task.scorer == "reasoning_gym":
        return answer, _score_reasoning_gym(task, answer)
    raise ValueError(f"unknown scorer: {task.scorer}")


def _score_reasoning_gym(task: Task, answer: str) -> float:
    try:
        import reasoning_gym
    except ImportError as exc:
        raise RuntimeError("install the reasoning-gym extra to score this suite") from exc
    dataset_name = str(task.metadata["reasoning_gym_dataset"])
    entry: dict[str, Any] = dict(task.metadata["reasoning_gym_entry"])
    scorer = reasoning_gym.get_score_answer_fn(dataset_name)
    return float(scorer(answer, entry))
