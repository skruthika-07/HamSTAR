"""
What the student sees after a wrong answer: the correct answer and an explanation of it.
"Explain again" asks for a simpler version with an everyday example, as many times as needed.
"""
from sqlalchemy.orm import Session

from ..core.logging import log
from ..models import Attempt, Misconception, Question
from ..prompts.explanation import EXPLANATION_PROMPT_VERSION
from . import bank_service
from .ai_client import ProviderError
from .groq_service import get_groq


def _correct_answer(q: Question) -> dict:
    if q.question_type == "MCQ":
        o = next(o for o in q.options if o["correct"])
        return {"id": o["id"], "text": o["text"]}
    return {"id": None, "text": q.expected_answer or q.model_answer or ""}


def _built_in_structure(db: Session, q: Question) -> dict:
    """Key terms, core concepts and a line to remember, from the answer key, when Groq is not available."""
    answer = _correct_answer(q)["text"]
    targets = (q.diagnostic_metadata or {}).get("targets")
    ids = [targets] if targets else [o.get("misconception") for o in (q.options or []) if o.get("misconception")]
    m = next((x for x in (db.get(Misconception, i) for i in ids if i) if x), None)
    notes = (m.remediation or {}).get("explanation", []) if m else []
    example = (m.remediation or {}).get("worked_example", "") if m else ""
    meta = q.diagnostic_metadata or {}
    terms = [t for t in [*meta.get("expected_concepts", [])[:3], answer if len(answer) <= 40 else None] if t]
    first = (q.explanation or "").split(". ")[0].strip().rstrip(".")
    return {
        "key_terms": terms or [answer[:40]],
        "core_concepts": notes[:2] or ([first + "."] if first else []),
        "remember": example or (f"{first}." if first else f"The answer is {answer}."),
    }


def _built_in(db: Session, q: Question, level: int) -> str:
    """Wording used when Groq is not available: the answer key first, then the step-by-step teaching notes."""
    base = q.explanation or f"The correct answer is {_correct_answer(q)['text']}."
    if level == 0:
        return base
    # the bank's own teaching notes for the idea this question is about
    targets = (q.diagnostic_metadata or {}).get("targets")
    ids = [targets] if targets else [o.get("misconception") for o in (q.options or []) if o.get("misconception")]
    for mid in ids:
        m = db.get(Misconception, mid) if mid else None
        if m:
            notes = (m.remediation or {}).get("explanation", [])
            example = (m.remediation or {}).get("worked_example", "")
            return " ".join(["Let's take it one small step at a time.", *notes, f"For example: {example}." if example else "", f"So here: {base}"]).strip()
    return f"Let's take it one small step at a time. {base} Read the question once more, then say the answer back in your own words."


MISTAKE_LABELS = {
    "CARELESS_SLIP": ("Careless Slip", "You knew the idea but a small error slipped in."),
    "MISCONCEPTION": ("Misconception", "The idea itself needs another look."),
    "GAP_IN_UNDERSTANDING": ("Gap in Understanding", "This idea has not been learned yet, so let's build it up from the start."),
    "CALCULATION_ERROR": ("Calculation Error", "The method was right, the arithmetic went astray."),
}


def _guess_mistake_type(attempt: Attempt, q: Question) -> str:
    """Without Groq: what the answer key and the marking already say about this answer."""
    if q.question_type == "MCQ":
        picked = next((o for o in q.options if o["id"] == attempt.selected_option), {})
        if picked.get("misconception"):
            return "MISCONCEPTION"
        if picked.get("slip_weight", 1) >= 2:
            return "CALCULATION_ERROR" if all(any(c.isdigit() for c in o.get("text", "")) for o in q.options) else "CARELESS_SLIP"
        return "GAP_IN_UNDERSTANDING"
    ev = attempt.evaluation or {}
    if ev.get("classification") in ("CALCULATION_ERROR", "MISCONCEPTION"):
        return ev["classification"]
    if ev.get("classification") in ("MINOR_ERROR", "MISINTERPRETATION"):
        return "CARELESS_SLIP"
    if ev.get("misconceptions"):
        return "MISCONCEPTION"
    return "GAP_IN_UNDERSTANDING"


def mistake_type(db: Session, attempt: Attempt, q: Question) -> dict:
    """
    The kind of mistake a wrong answer most looks like. Worked out once per attempt and kept with it.
    It is a first impression from one answer, so it is worded as "looks like"; for multiple choice the
    follow-up question remains what confirms or overturns it.
    """
    stored = (attempt.evaluation or {}).get("mistake_type")
    if stored:
        return stored
    kind, reason, source = None, "", "built-in"
    groq = get_groq()
    if groq.configured:
        try:
            if q.question_type == "MCQ":
                picked = next((o for o in q.options if o["id"] == attempt.selected_option), {})
                given, notes = picked.get("text", ""), picked.get("reasoning", "")
            else:
                given, notes = attempt.answer or "", q.explanation or ""
            m = groq.mistake_type(q.question_text, _correct_answer(q)["text"], given, notes)
            kind, reason, source = m.mistake_type, m.reason, "groq"
        except ProviderError:
            log.warning("Groq unavailable for classifying a mistake; using the answer key")
    kind = kind or _guess_mistake_type(attempt, q)
    label, about = MISTAKE_LABELS[kind]
    out = {"kind": kind, "label": label, "about": about, "reason": reason, "message": f"Looks like this was {'an' if label[0] in 'AEIOU' else 'a'} {label}", "source": source}
    attempt.evaluation = {**(attempt.evaluation or {}), "mistake_type": out}
    from . import mistake_service

    mistake_service.set_type(db, attempt, kind)
    db.commit()
    return out


def explain(db: Session, q: Question, level: int, attempt: Attempt | None = None) -> dict:
    """`attempt` is given when the question being explained is the one the student just got wrong."""
    answer = _correct_answer(q)
    text, source, parts = None, "built-in", None
    groq = get_groq()
    if groq.configured:
        try:
            e = groq.explain(q.question_text, answer["text"], q.explanation or "", level)
            text, source, parts = e.explanation, "groq", {"key_terms": e.key_terms[:5], "core_concepts": e.core_concepts[:3], "remember": e.remember}
        except ProviderError:
            log.warning("Groq unavailable for an explanation; using the built-in wording")
    built = _built_in_structure(db, q)
    parts = {k: (parts or {}).get(k) or built[k] for k in built}  # never an empty section
    return {
        "question": bank_service.revealed(q),
        "correct_answer": answer,
        # always the same four parts: key terms, core concepts, full explanation, a line to remember
        **parts,
        "explanation": text or _built_in(db, q, level),
        "level": level,
        "simpler": level > 0,
        "source": source,
        "prompt_version": EXPLANATION_PROMPT_VERSION if source == "groq" else None,
        "mistake_type": mistake_type(db, attempt, q) if attempt is not None and not attempt.is_correct else None,
    }
