"""Questions written by Mistral from a student's own material, checked before they are stored."""
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.errors import ApiError
from ..models import MARK_RULES, Question, StudyMaterial, User
from ..prompts.question_generation import QUESTION_GENERATION_PROMPT_VERSION
from .ai_client import ProviderError
from . import verification_service
from .mistral_service import get_mistral

LETTERS = "ABCD"


def check_marks(question_type: str, marks: int) -> None:
    """One word 1 · MCQ 1 · fill in the blank 1-2 · answer in brief 4-8 · answer in detail 12-20."""
    if question_type not in MARK_RULES:
        raise ApiError("INVALID_QUESTION_TYPE", f"Question type must be one of {', '.join(MARK_RULES)}.", 422)
    lo, hi = MARK_RULES[question_type]
    if not lo <= marks <= hi:
        allowed = str(lo) if lo == hi else f"{lo} to {hi}"
        raise ApiError("INVALID_MARKS", f"{question_type} questions carry {allowed} mark{'s' if hi > 1 else ''}.", 422)


def _context(material: StudyMaterial, topic: str) -> str:
    """The part of the material that is about the topic, so the questions stay on it."""
    text = material.extracted_text or ""
    if not topic or len(text) < 6000:
        return text
    words = [w for w in re.findall(r"\w{4,}", topic.lower())]
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    hits = [p for p in paragraphs if any(w in p.lower() for w in words)]
    return "\n\n".join(hits) if sum(len(p) for p in hits) > 500 else text


def _row(user: User, material: StudyMaterial, question_type: str, marks: int, topic: str, item, verified: bool = False) -> Question:
    meta = {"prompt_version": QUESTION_GENERATION_PROMPT_VERSION}
    if verified:
        meta["math_verified"] = True  # its answer key was worked out a second time, by another model
    meta["concept"] = item.topic
    # the one document this question was written from: it is only ever asked inside that document
    meta["document"] = material.id
    q = Question(owner_id=user.id, study_material_id=material.id, topic=(material.subject or "General")[:80], role="main", question_type=question_type,
                 question_text=item.question.strip(), marks=marks, difficulty=item.difficulty, source_context=material.title, diagnostic_metadata=meta)
    if question_type == "MCQ":
        q.correct_option = item.correct_option
        q.explanation = item.explanation
        q.options = []
        for i, text in enumerate(item.options):
            letter = LETTERS[i]
            # models sometimes write the letter into the option ("B. Mitochondria")
            text = re.sub(r"^\s*\(?[A-Da-d][.):]\s+", "", text)
            why = item.wrong_option_diagnosis.get(letter, "")
            wrong = letter != item.correct_option
            q.options.append({
                "id": letter, "text": text.strip(), "correct": not wrong,
                # each diagnosed distractor is a hypothesis the engine can weigh: misconception vs slip
                "misconception": f"GEN:{letter}" if wrong and why else None,
                "reasoning": why, "slip_weight": 0 if not wrong else 3 if why else 1,
            })
    elif question_type in ("FILL_BLANK", "ONE_WORD"):
        q.expected_answer, q.accepted_answers, q.explanation = item.expected_answer, item.accepted_answers, item.explanation
    else:
        q.model_answer, q.rubric = item.model_answer, [r.model_dump() for r in item.rubric]
        q.explanation = item.model_answer
        meta.update({"expected_concepts": item.expected_concepts, "key_points": item.key_points})
    return q


def generate(db: Session, user: User, material: StudyMaterial, question_type: str, marks: int, n: int, difficulty: str, topic: str) -> list[Question]:
    check_marks(question_type, marks)
    if material.processing_status != "PROCESSED" or not material.extracted_text:
        raise ApiError("DOCUMENT_PROCESSING_FAILED", material.processing_error or "This material has not been read yet.", 409)
    # Only this document's own text goes to the model: nothing from other documents in the same folder.
    # stay on the requested topic if one was given, otherwise on the material's subject
    focus = topic or material.subject or material.title
    # a batch that comes back unusable (malformed, or every item invalid) is asked for once more before giving up
    items: list = []
    for attempt in range(2):
        try:
            items = get_mistral().generate_questions(question_type, marks, n, difficulty, focus, _context(material, topic))
        except ProviderError as e:
            if attempt:
                raise ApiError("QUESTION_GENERATION_FAILED", e.message, 503)
            continue
        if items:
            break
    # maths answer keys are worked out again before anything is stored; a wrong key is corrected or the question dropped
    items, verified = verification_service.verify_items(question_type, items)

    seen = {q.strip().lower() for q in db.scalars(select(Question.question_text).where(Question.study_material_id == material.id))}
    rows: list[Question] = []
    for item in items:
        key = item.question.strip().lower()
        if key in seen:  # no duplicates, within the batch or with earlier batches
            continue
        seen.add(key)
        row = _row(user, material, question_type, marks, topic, item, id(item) in verified)
        db.add(row)
        rows.append(row)
        if len(rows) == n:
            break
    if not rows:
        raise ApiError("QUESTION_GENERATION_FAILED", "No usable questions could be written from this material. Try another topic.", 502)
    db.flush()
    # distractor hypotheses are scoped to their own question
    for row in rows:
        if row.question_type == "MCQ":
            row.options = [{**o, "misconception": f"GEN:{row.id}:{o['id']}" if o["misconception"] else None} for o in row.options]
    db.commit()
    return rows
