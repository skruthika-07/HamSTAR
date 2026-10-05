"""Bridges database rows and the plain dicts the engine works with, and seeds the verified bank."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..engine import bayes
from ..engine.bank import Bank, seed_bank
from ..models import Misconception, Question


def seed(db: Session) -> None:
    """Load the verified starter bank once. Safe to call on every start. Uploaded material adds any other subject."""
    bank = seed_bank()
    have_q = set(db.scalars(select(Question.id).where(Question.owner_id.is_(None))))
    have_m = set(db.scalars(select(Misconception.id)))
    for m in bank.misconceptions:
        if m["id"] in have_m:
            continue
        wrong = [{"question_id": q["id"], "option_id": o["id"], "text": o["text"]} for q in bank.questions for o in q["options"] if o.get("misconception") == m["id"]]
        db.add(Misconception(id=m["id"], topic=m["topic"], name=m["name"], description=m["rule"], indicators=m["indicators"], common_wrong_options=wrong, remediation={"explanation": m["explanation"], "worked_example": m["worked_example"]}))
    for i, q in enumerate(bank.questions):
        if q["id"] in have_q:
            continue
        correct = next(o for o in q["options"] if o["correct"])
        db.add(Question(
            id=q["id"], topic=q["topic"], role=q["role"], question_type="MCQ", question_text=q["prompt"], marks=1, options=q["options"],
            correct_option=correct["id"], explanation=q["solution"], diagnostic_metadata={"targets": q.get("targets"), "position": i, "verified": True},
        ))
    db.commit()


def q_dict(q: Question) -> dict:
    return {"id": q.id, "topic": q.topic, "role": q.role, "prompt": q.question_text, "solution": q.explanation, "targets": (q.diagnostic_metadata or {}).get("targets"), "options": q.options or [], "owner_id": q.owner_id}


def m_dict(m: Misconception) -> dict:
    r = m.remediation or {}
    return {"id": m.id, "topic": m.topic, "name": m.name, "rule": m.description, "indicators": m.indicators or [], "explanation": r.get("explanation", []), "worked_example": r.get("worked_example", "")}


def bank(db: Session) -> Bank:
    """The shared bank as it stands in the database (so misconceptions added later are picked up)."""
    rows = db.scalars(select(Question).where(Question.owner_id.is_(None))).all()
    rows.sort(key=lambda q: (q.diagnostic_metadata or {}).get("position", 0))
    return Bank(topics=seed_bank().topics, misconceptions=[m_dict(m) for m in db.scalars(select(Misconception)).all()], questions=[q_dict(q) for q in rows])


def is_bank_topic(topic: str) -> bool:
    return any(t["id"] == topic for t in seed_bank().topics)


def context(db: Session, question: Question) -> tuple[dict, list[dict], list[dict]]:
    """For a question: the prior over hypotheses, the misconceptions in play, and the probes available."""
    if question.owner_id is None and is_bank_topic(question.topic):
        b = bank(db)
        return b.prior(question.topic), b.misconceptions_for(question.topic), b.probes(question.topic)
    # generated question: each diagnosed wrong option is its own hypothesis
    root = (question.diagnostic_metadata or {}).get("parent") or question.id
    parent = db.get(Question, root) or question
    ms = [
        {"id": o["misconception"], "topic": parent.topic, "name": (o.get("reasoning") or f"The pattern behind option {o['id']}").split(". ")[0].rstrip(".")[:90], "rule": o.get("reasoning", ""), "indicators": [], "explanation": [parent.explanation] if parent.explanation else [], "worked_example": ""}
        for o in parent.options if o.get("misconception")
    ]
    probes = [q_dict(q) for q in db.scalars(select(Question).where(Question.role == "probe", Question.owner_id == parent.owner_id)).all() if (q.diagnostic_metadata or {}).get("parent") == root]
    return bayes.base_prior([m["id"] for m in ms]), ms, probes


def starter_material(db: Session, user, topic: str):
    """
    A hidden material holding a starter folder's own content (its questions, worked solutions and the
    explanations of its misconceptions), so questions of any type can be written for that folder too.
    """
    from ..models import StudyMaterial

    m = db.scalar(select(StudyMaterial).where(StudyMaterial.user_id == user.id, StudyMaterial.file_type == "starter", StudyMaterial.topic == topic))
    if m:
        return m
    b = bank(db)
    name = next(t["name"] for t in b.topics if t["id"] == topic)
    lines = [f"# {name}", next(t["blurb"] for t in b.topics if t["id"] == topic), ""]
    for q in b.questions:
        if q["topic"] == topic:
            lines.append(f"Worked example: {q['prompt']} Answer: {next(o['text'] for o in q['options'] if o['correct'])}. {q['solution']}")
    for mc in b.misconceptions_for(topic):
        lines += ["", f"Common mistake: {mc['rule']}", *mc["explanation"], mc["worked_example"]]
    m = StudyMaterial(user_id=user.id, title=name, file_name=f"{topic}.starter", file_type="starter", file_path="", subject=name, topic=topic,
                      extracted_text="\n".join(lines), concepts=[mc["name"] for mc in b.misconceptions_for(topic)], processing_status="PROCESSED")
    db.add(m)
    db.flush()
    return m


def public(q: Question | dict) -> dict:
    """A question as the student sees it before answering: no answer key, no diagnostic tags."""
    if isinstance(q, Question):
        base = {"id": q.id, "topic": q.topic, "type": q.question_type, "marks": q.marks, "prompt": q.question_text, "difficulty": q.difficulty}
        options = q.options or []
    else:
        base = {"id": q["id"], "topic": q["topic"], "type": "MCQ", "marks": 1, "prompt": q["prompt"], "difficulty": "medium"}
        options = q["options"]
    return {**base, "options": [{"id": o["id"], "text": o["text"]} for o in options]}


def revealed(q: Question | dict) -> dict:
    """A question after it has been answered: which option was right, and the worked solution."""
    out = public(q)
    options = q.options if isinstance(q, Question) else q["options"]
    out["options"] = [{"id": o["id"], "text": o["text"], "correct": bool(o["correct"]), "reasoning": o.get("reasoning", "")} for o in options or []]
    out["solution"] = q.explanation if isinstance(q, Question) else q["solution"]
    if isinstance(q, Question) and q.question_type != "MCQ":
        out["expected_answer"] = q.expected_answer or q.model_answer
    return out
