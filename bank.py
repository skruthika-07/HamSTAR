"""The verified question bank in the shape the engine works with."""
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import bayes

SEED_FILE = Path(__file__).resolve().parent.parent / "seed" / "bank.json"


@dataclass
class Bank:
    topics: list[dict]
    misconceptions: list[dict]
    questions: list[dict]
    by_id: dict[str, dict] = field(default_factory=dict)

    def __post_init__(self):
        self.by_id = {q["id"]: q for q in self.questions}

    def misconceptions_for(self, topic: str) -> list[dict]:
        return [m for m in self.misconceptions if m["topic"] == topic]

    def prior(self, topic: str) -> dict:
        return bayes.base_prior([m["id"] for m in self.misconceptions_for(topic)])

    def main(self, topic: str) -> list[dict]:
        return [q for q in self.questions if q["topic"] == topic and q["role"] == "main"]

    def probes(self, topic: str) -> list[dict]:
        return [q for q in self.questions if q["topic"] == topic and q["role"] == "probe"]


def correct_option(question: dict) -> dict:
    return next(o for o in question["options"] if o["correct"])


def option(question: dict, option_id: str) -> dict | None:
    return next((o for o in question["options"] if o["id"] == option_id), None)


@lru_cache
def seed_bank() -> Bank:
    """The bank exactly as shipped in seed/bank.json (exported from the original frontend data)."""
    raw = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    questions = [
        {
            "id": q["id"],
            "topic": q["topic"],
            "role": q["role"],
            "prompt": q["prompt"],
            "solution": q["solution"],
            "targets": q.get("targets"),
            "options": [
                {"id": o["id"], "text": o["text"], "correct": o["correct"], "misconception": o.get("misconception"), "reasoning": o["reasoning"], "slip_weight": o["slipWeight"]}
                for o in q["options"]
            ],
        }
        for q in raw["questions"]
    ]
    misconceptions = [
        {"id": m["id"], "topic": m["topic"], "name": m["name"], "rule": m["rule"], "explanation": m["explanation"], "worked_example": m["workedExample"], "indicators": m["cues"]}
        for m in raw["misconceptions"]
    ]
    return Bank(topics=raw["topics"], misconceptions=misconceptions, questions=questions)
