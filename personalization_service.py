"""What should this student practise next? Answered from their own history, not from a fixed syllabus order."""
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..engine import bayes
from ..engine.bank import seed_bank
from ..models import Attempt, DiagnosticSession, Question, StudyMaterial, User
from . import answer_evaluation_service, bank_service, diagnostic_service, folder_service, mistake_service, reward_service


def understanding(user: User, topic: str, prior: dict) -> float:
    return bayes.understanding((user.beliefs or {}).get(topic, prior))


def progress(db: Session, user: User) -> dict:
    """Confidence per folder and per concept, plus where the student is in each folder."""
    bank = bank_service.bank(db)
    topics = []
    for t in bank.topics:
        prior = bank.prior(t["id"])
        belief = (user.beliefs or {}).get(t["id"], prior)
        total = len(bank.main(t["id"]))
        topics.append({
            "id": t["id"], "name": t["name"], "blurb": t["blurb"],
            "confidence": round(bayes.understanding(belief) * 100),
            "question_number": min((user.cursors or {}).get(t["id"], 0) + 1, max(total, 1)),
            "completed": total > 0 and (user.cursors or {}).get(t["id"], 0) >= total,
            "total_questions": total,
            "concepts": [{"id": m["id"], "name": m["name"], "confidence": round((1 - belief.get(m["id"], 0)) * 100), "suspected": round(belief.get(m["id"], 0) * 100)} for m in bank.misconceptions_for(t["id"])],
        })
    return {"total_confidence": round(sum(t["confidence"] for t in topics) / len(topics)) if topics else 0, "topics": topics}


def weak_areas(db: Session, user: User, limit: int = 3) -> list[dict]:
    """
    Ranked by, in order of weight: unresolved misconceptions, low confidence,
    repetition, recency (newer mistakes add a little), and the topic being weak overall.
    """
    bank = bank_service.bank(db)
    sessions = db.scalars(select(DiagnosticSession).where(DiagnosticSession.user_id == user.id, DiagnosticSession.final_diagnosis.is_not(None)).order_by(DiagnosticSession.created_at.desc())).all()
    open_by_m = Counter(s.misconception_id for s in sessions if s.misconception_id and not s.corrected)
    seen_by_m = Counter(s.misconception_id for s in sessions if s.misconception_id)
    recent = {s.misconception_id for s in sessions[:5] if s.misconception_id and not s.corrected}

    areas = []
    for m in bank.misconceptions:
        prior = bank.prior(m["topic"])
        belief = (user.beliefs or {}).get(m["topic"], prior)
        p = belief.get(m["id"], 0.0)
        unresolved, seen = open_by_m[m["id"]], seen_by_m[m["id"]]
        if p <= 0.1 and not unresolved:
            continue
        score = unresolved * 0.5 + p + max(0, seen - 1) * 0.15 + (0.1 if m["id"] in recent else 0) + (1 - bayes.understanding(belief)) * 0.2
        reason = f"{unresolved} mistake{'' if unresolved == 1 else 's'} to retry" if unresolved else f"{round(p * 100)}% suspected from your answers"
        if seen > 1:
            reason += f", seen {seen} times"
        areas.append({"id": m["id"], "name": m["name"], "topic": m["topic"], "topic_name": next(t["name"] for t in bank.topics if t["id"] == m["topic"]), "suspected": round(p * 100), "open_mistakes": unresolved, "times_seen": seen, "reason": reason, "score": round(score, 3)})
    return sorted(areas, key=lambda a: -a["score"])[:limit]


def recommendations(db: Session, user: User) -> dict:
    bank = bank_service.bank(db)
    areas = weak_areas(db, user, 3)
    prog = progress(db, user)
    answered = set(db.scalars(select(Attempt.question_id).where(Attempt.user_id == user.id, Attempt.is_correct.is_(True))))

    questions, topics = [], []
    for a in areas:
        if a["topic"] not in topics:
            topics.append(a["topic"])
        # a different question on the same idea, not the one they already got wrong
        fresh = [q for q in bank.questions if q.get("targets") == a["id"] and q["id"] not in answered]
        for q in fresh[:2]:
            questions.append({"question_id": q["id"], "prompt": q["prompt"], "topic": q["topic"], "why": f"Tests “{a['name']}”"})
    if not topics:
        weakest = min(prog["topics"], key=lambda t: t["confidence"], default=None)
        if weakest:
            topics.append(weakest["id"])

    if areas:
        reason = f"Your past mistakes point to “{areas[0]['name']}” ({areas[0]['reason']})."
    elif prog["topics"]:
        w = min(prog["topics"], key=lambda t: t["confidence"])
        reason = f"No weak spot stands out. {w['name']} has your lowest confidence at {w['confidence']}/100, so start there."
    else:
        reason = "Answer a few questions and recommendations will appear here."
    names = {t["id"]: t["name"] for t in bank.topics}
    return {"recommended_topics": [{"id": t, "name": names.get(t, t)} for t in topics], "reason": reason, "recommended_questions": questions[:5], "weak_areas": areas}


def dashboard(db: Session, user: User) -> dict:
    """Everything the dashboard shows, computed here so the frontend only renders."""
    sessions = db.scalars(select(DiagnosticSession).where(DiagnosticSession.user_id == user.id, DiagnosticSession.final_diagnosis.is_not(None)).order_by(DiagnosticSession.created_at.desc()).limit(4)).all()
    mistakes = [diagnostic_service.mistake_view(db, s) for s in sessions]
    badges = reward_service.badges_view(db, user)
    # the hidden per-folder material that holds non-MCQ questions for a starter folder is not an upload
    materials = db.scalars(select(StudyMaterial).where(StudyMaterial.user_id == user.id, StudyMaterial.file_type != "starter").order_by(StudyMaterial.created_at.desc())).all()

    activity = [{"at": m["created_at"], "text": f"{'Corrected' if m['corrected'] else 'Diagnosed'}: {m['question']['prompt']}"} for m in mistakes]
    activity += [{"at": b["unlocked_at"], "text": f"Badge earned: {b['name']}"} for b in badges if b["unlocked"]]
    activity += [{"at": m.created_at.isoformat(), "text": f"Uploaded {m.file_name}"} for m in materials[:3]]
    activity = sorted([a for a in activity if a["at"]], key=lambda a: a["at"], reverse=True)[:4]

    cert = reward_service.certificate_view(db, user)
    return {
        "user": profile(db, user)["user"],
        "tiara": {"count": user.tiara_count, "target": cert["target"], "to_go": cert["to_go"], "rule": "1 correct question = 1 Tiara"},
        "streak": {"current": user.current_streak, "longest": user.longest_streak, "no_skip": user.noskip_count},
        "stats": {
            "answered": user.answered_count, "correct": user.correct_count, "skipped": user.skipped_count, "mistakes_corrected": user.mistakes_corrected,
            "accuracy": round(user.correct_count / user.answered_count * 100) if user.answered_count else 0,
        },
        "progress": progress(db, user),
        "recent_mistakes": mistakes,
        "recent_activity": activity,
        "badges": badges,
        "certificate": cert,
        "recommendations": recommendations(db, user),
        "materials": [material_folder(db, user, m) for m in materials],
        # parent folders → subfolders → documents, with confidence and weakness at every level
        "folders": folder_service.tree(db, user),
        "recurring": mistake_service.summary(db, user),
    }


def material_folder(db: Session, user: User, m: StudyMaterial) -> dict:
    """An uploaded material as a folder: its subject, how many questions it has, and how the student is doing on them."""
    questions = db.scalars(select(Question).where(Question.study_material_id == m.id, Question.role == "main")).all()
    by_type: dict[str, int] = {}
    for q in questions:
        by_type[q.question_type] = by_type.get(q.question_type, 0) + 1
    ids = [q.id for q in questions]
    attempts = db.scalars(select(Attempt).where(Attempt.user_id == user.id, Attempt.question_id.in_(ids), Attempt.skipped.is_(False))).all() if ids else []
    correct = sum(a.is_correct for a in attempts)
    return {
        "id": m.id, "title": m.title, "file_name": m.file_name, "file_type": m.file_type, "topic": m.topic,
        "subject": m.subject or "General", "subject_detected": bool(m.subject), "parent": m.parent_subject or folder_service.place(m.subject)[0],
        "processing_status": m.processing_status, "processing_error": m.processing_error, "question_count": len(questions), "questions_by_type": by_type,
        "question_number": min((user.cursors or {}).get(f"material:{m.id}", 0) + 1, max(by_type.get("MCQ", 0), 1)),
        "answered": len(attempts), "correct": correct, "accuracy": round(correct / len(attempts) * 100) if attempts else None,
    }


def profile(db: Session, user: User) -> dict:
    return {
        "user": {"id": user.id, "name": user.name, "email": user.email, "role": user.role, "avatar": user.avatar},
        "tiara": user.tiara_count,
        "streak": {"current": user.current_streak, "longest": user.longest_streak, "no_skip": user.noskip_count},
        "badges": reward_service.badges_view(db, user),
        "certificate": reward_service.certificate_view(db, user),
        "progress": progress(db, user),
    }


def retry_queue(db: Session, user: User) -> list[DiagnosticSession]:
    """Unresolved mistakes in the order they are worth retrying."""
    sessions = db.scalars(select(DiagnosticSession).where(DiagnosticSession.user_id == user.id, DiagnosticSession.final_diagnosis.is_not(None), DiagnosticSession.corrected.is_(False))).all()
    repeats = Counter(s.misconception_id for s in sessions if s.misconception_id)
    bank = seed_bank()

    def rank(s: DiagnosticSession):
        prior = bank.prior(s.topic) if bank_service.is_bank_topic(s.topic) else {}
        return (0 if s.misconception_id else 1, understanding(user, s.topic, prior), -repeats[s.misconception_id], -s.created_at.timestamp())

    return sorted(sessions, key=rank)

