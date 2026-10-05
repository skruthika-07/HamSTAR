"""Demo data for presentations. The mistake history is produced by running the real diagnosis flow on scripted answers."""
from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..engine import bayes
from ..engine.bank import correct_option
from ..models import MistakeLog, Attempt, Badge, Certificate, DiagnosticSession, EvaluationRun, Question, Reward, User
from ..models.base import now
from . import answer_evaluation_service, bank_service, diagnostic_service, reward_service

# (question, option picked, how the follow-ups are answered, days ago, went on to correct it, what the student said)
SCRIPT = [
    # first, so it is judged on its own answers rather than on the history the later entries build up
    ("f4", "A", "arithmetic", 7, False, "I think I worked out the sum wrong."),
    ("f1", "A", "holds:F_ADD_ACROSS", 6, True, "I added the tops and then added the bottoms."),
    ("a2", "C", "knows", 4, True, None),
    ("f3", "B", "knows", 3, True, "I rushed and forgot to flip the second fraction."),
    ("f5", "B", "lost", 2, False, None),
    ("a3", "A", "holds:A_SQUARE_SUM", 1, False, None),
]


def reset(db: Session, user: User) -> None:
    for model in (Reward, Badge, Certificate, EvaluationRun):
        db.execute(delete(model).where(model.user_id == user.id))
    db.execute(delete(MistakeLog).where(MistakeLog.user_id == user.id))
    for a in db.scalars(select(Attempt).where(Attempt.user_id == user.id)).all():
        db.delete(a)  # cascades to diagnostic sessions and their follow-ups
    user.tiara_count = user.current_streak = user.longest_streak = user.noskip_count = 0
    user.answered_count = user.correct_count = user.skipped_count = user.mistakes_corrected = 0
    user.beliefs, user.cursors = {}, {}
    db.flush()


def _answer(mode: str, probe: dict) -> str:
    if mode.startswith("holds:"):
        m = mode.split(":", 1)[1]
        return (next((o for o in probe["options"] if o.get("misconception") == m), None) or correct_option(probe))["id"]
    if mode == "arithmetic":
        # the method is right but the sums go wrong: the likeliest near miss whenever there is something to work out
        slips = [o for o in probe["options"] if not o["correct"] and not o.get("misconception")]
        if bayes.computational(probe) and slips:
            return max(slips, key=lambda o: o.get("slip_weight", 1))["id"]
        return correct_option(probe)["id"]
    if mode == "lost":
        return next(o for o in probe["options"] if not o["correct"] and not o.get("misconception"))["id"]
    return correct_option(probe)["id"]


def load(db: Session, user: User) -> None:
    token = diagnostic_service.use_ai.set(False)
    try:
        _load(db, user)
    finally:
        diagnostic_service.use_ai.reset(token)


def _load(db: Session, user: User) -> None:
    reset(db, user)
    for qid, pick, mode, days_ago, fixed, said in SCRIPT:
        question = db.get(Question, qid)
        result = answer_evaluation_service.evaluate(db, user, question, None, pick, said, None)
        s = db.get(DiagnosticSession, result["diagnostic"]["session_id"])
        while not s.final_diagnosis:
            f = diagnostic_service.next_followup(db, user, s)
            if f is None:
                break
            diagnostic_service.evaluate_followup(db, user, s, _answer(mode, bank_service.q_dict(db.get(Question, f.question_id))))
        if fixed and not s.corrected:
            for _ in range(diagnostic_service.MAX_RETRIES):
                step = diagnostic_service.retry_start(db, user, s)
                retest = bank_service.q_dict(db.get(Question, step["question"]["id"]))
                if diagnostic_service.retry_evaluate(db, user, s, retest["id"], correct_option(retest)["id"])["corrected"]:
                    break
        when = now() - timedelta(days=days_ago)
        s.created_at = when
        s.attempt.created_at = when
    # a learner some way in: totals a real history of this size would have
    user.answered_count, user.correct_count, user.tiara_count = 421, 342, 342
    user.current_streak, user.longest_streak, user.noskip_count, user.skipped_count, user.mistakes_corrected = 7, 14, 21, 6, 47
    user.cursors = {}
    db.add(Badge(user_id=user.id, code="streak", unlocked_at=now() - timedelta(days=9)))
    db.flush()


def run(db: Session, user: User, action: str, amount: int) -> list[dict]:
    if action == "reset":
        reset(db, user)
    elif action == "load":
        load(db, user)
    else:
        reward_service.add_demo_tiara(db, user, amount)
    unlocked = reward_service.check_unlocks(db, user) if action == "add_tiara" else []
    db.commit()
    return unlocked
