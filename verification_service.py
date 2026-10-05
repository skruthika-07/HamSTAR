"""
A second look at maths answers before a student sees them. The model that writes a question can get its own
arithmetic wrong (it once keyed -(4-3x)+2x as x+4; it is 5x-4), so a different model works each maths question
out step by step and the answer key is corrected to what it finds.

It runs when questions are written, and once more on first use for questions stored before this check existed.
A model can still be wrong: this lowers the chance of a bad key, it does not remove it.
"""
import re

from sqlalchemy.orm import Session

from ..core.logging import log
from ..models import Question
from .ai_client import ProviderError
from .groq_service import get_groq

CHECKED_TYPES = ("MCQ", "FILL_BLANK", "ONE_WORD")
MATH = re.compile(
    r"\d\s*[-+*/×÷^=<>]\s*[\d(a-z]|[a-z)]\s*[-+*/×÷^=]\s*[\d(a-z]\b|\d+\s*/\s*\d+|[√%²³π]|\b\d+[a-z]\b"
    r"|\b(simplify|solve|expand|factori[sz]e|evaluate|calculate|compute|differentiate|integrate|how many|what is the (value|sum|product|difference|area|perimeter|volume|mean|median))\b",
    re.IGNORECASE,
)


def is_math(text: str) -> bool:
    return bool(MATH.search(text or ""))


def _same(a: str, b: str) -> bool:
    """The same answer, whatever the spacing, case or a leading "x =" (4 - 5x and -5x + 4 still differ: the key is replaced)."""
    norm = lambda s: re.sub(r"^[a-z]=", "", re.sub(r"[\s$.]+$|\s+", "", (s or "").lower().replace("−", "-").replace("×", "*")))  # noqa: E731
    return norm(a) == norm(b)


def _check(entries: list[dict]) -> dict[int, object]:
    """Ask for each maths question to be worked out. {} when it cannot be done just now."""
    groq = get_groq()
    if not entries or not groq.configured:
        return {}
    try:
        return {r.number: r for r in groq.verify_math(entries).results}
    except ProviderError:
        log.warning("Maths answers could not be verified just now; they are kept as written")
        return {}


def verify_items(question_type: str, items: list) -> tuple[list, set[int]]:
    """Generated items (before they are stored) with their maths answer keys verified. Unfixable ones are dropped."""
    verified: set[int] = set()
    if question_type not in CHECKED_TYPES:
        return items, verified
    entries = []
    for i, item in enumerate(items, 1):
        if not is_math(item.question):
            continue
        if question_type == "MCQ":
            entries.append({"number": i, "question": item.question, "proposed": item.options["ABCD".index(item.correct_option)], "options": item.options})
        else:
            entries.append({"number": i, "question": item.question, "proposed": item.expected_answer, "options": None})
    results = _check(entries)
    kept = []
    for i, item in enumerate(items, 1):
        r = results.get(i)
        if r is None:
            kept.append(item)
            continue
        verified.add(id(item))
        if r.proposed_is_correct or not r.final_answer.strip():
            kept.append(item)
            continue
        log.warning("A generated maths answer was corrected by verification")
        if question_type == "MCQ":
            match = next((n for n, o in enumerate(item.options) if _same(o, r.final_answer)), None)
            if match is None:
                continue  # none of the options is right: the question is not asked
            letter = "ABCD"[match]
            item.wrong_option_diagnosis = {k: v for k, v in item.wrong_option_diagnosis.items() if k != letter}
            item.correct_option = letter
        else:
            item.expected_answer, item.accepted_answers = r.final_answer.strip(), []
        item.explanation = r.working or item.explanation
        kept.append(item)
    return kept, verified


def ensure(db: Session, q: Question) -> None:
    """A stored, generated maths question is verified once, the first time it is about to be used."""
    meta = q.diagnostic_metadata or {}
    if q.owner_id is None or q.role != "main" or q.question_type not in CHECKED_TYPES or "math_verified" in meta or not is_math(q.question_text):
        return
    if q.question_type == "MCQ":
        correct = next((o for o in q.options if o["correct"]), None)
        if not correct:
            return
        entry = {"number": 1, "question": q.question_text, "proposed": correct["text"], "options": [o["text"] for o in q.options]}
    else:
        entry = {"number": 1, "question": q.question_text, "proposed": q.expected_answer or "", "options": None}
    r = _check([entry]).get(1)
    if r is None:
        return  # not verified this time; it will be tried again
    if not r.proposed_is_correct and r.final_answer.strip():
        log.warning("A stored maths answer was corrected by verification")
        if q.question_type == "MCQ":
            match = next((o for o in q.options if _same(o["text"], r.final_answer)), None)
            if match:
                q.options = [{**o, "correct": o["id"] == match["id"], **({"misconception": None, "reasoning": "", "slip_weight": 0} if o["id"] == match["id"] else {})} for o in q.options]
                q.correct_option = match["id"]
                q.explanation = r.working or q.explanation
        else:
            q.expected_answer, q.accepted_answers = r.final_answer.strip(), []
            q.explanation = r.working or q.explanation
    q.diagnostic_metadata = {**meta, "math_verified": True}
    db.commit()
