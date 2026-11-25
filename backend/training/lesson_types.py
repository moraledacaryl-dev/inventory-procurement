"""Shared typed contracts for independently maintained curriculum modules."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Step:
    target: str
    instruction: str
    value: str | None = None
    event: str = "click"
    outcome: str | None = None
    outcome_status: int | None = None


@dataclass(frozen=True)
class Lesson:
    id: str
    module: str
    title: str
    roles: tuple[str, ...]
    route: str
    workflow: str
    situation: str
    concept: str
    example: str
    rule: str
    question: str
    answer: str
    correction: str
    sources: tuple[str, ...]
    steps: tuple[Step, ...] = field(default_factory=tuple)
    quantity: int = 0
    rejected: int = 0
    global_access: bool = False
