from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Provider = Literal["codex", "claude"]
Speed = Literal["standard", "fast"]
Protocol = Literal["strict", "orchestrated"]


@dataclass(frozen=True)
class Task:
    id: str
    prompt: str
    reference: str
    scorer: str = "exact"
    category: str = "uncategorized"
    source: str = "local"
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Task":
        required = {"id", "prompt", "reference"}
        missing = sorted(required - value.keys())
        if missing:
            raise ValueError(f"task is missing required fields: {', '.join(missing)}")
        return cls(
            id=str(value["id"]),
            prompt=str(value["prompt"]),
            reference=str(value["reference"]),
            scorer=str(value.get("scorer", "exact")),
            category=str(value.get("category", "uncategorized")),
            source=str(value.get("source", "local")),
            metadata=dict(value.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RunConfig:
    provider: Provider
    model: str
    effort: str
    speed: Speed = "standard"
    protocol: Protocol = "strict"
    timeout_seconds: int = 900

    @property
    def label(self) -> str:
        parts = [self.provider, self.model, self.effort]
        if self.provider == "codex":
            parts.append(self.speed)
        if self.protocol != "strict":
            parts.append(self.protocol)
        return "/".join(parts)


@dataclass
class AdapterResult:
    status: str
    response: str
    latency_ms: int
    exit_code: int | None
    native_metrics: dict[str, Any]
    trace: list[dict[str, Any]]
    error: str | None = None


@dataclass
class RunRecord:
    schema_version: int
    run_id: str
    task_id: str
    task_category: str
    task_source: str
    suite_hash: str
    attempt: int
    provider: str
    requested_model: str
    observed_primary_model: str | None
    observed_models: list[str]
    effort: str
    speed: str
    protocol: str
    started_at: str
    status: str
    response: str
    extracted_answer: str
    score: float | None
    correct: bool | None
    latency_ms: int
    protocol_violation: bool
    exit_code: int | None
    native_metrics: dict[str, Any]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
