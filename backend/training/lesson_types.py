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
    outcome_method: str | None = None


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


def input_step(target, instruction, value):
    return Step(target, instruction, value, "input")


def select_step(target, instruction, value):
    return Step(target, instruction, value, "change")


def action_step(target, instruction, endpoint=None, status=None):
    return Step(target, instruction, outcome=endpoint, outcome_status=status)
