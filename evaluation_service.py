"""
Evaluation Lab: evidence that the diagnosis works.

Simulated students with a known, injected cause are run through the same engine the
real students use. Nothing here is a fixed number: change the seed and the figures move.
"""
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..engine import bayes
from ..engine.bank import Bank, correct_option, option
from ..engine.simulation import simulate
from ..models import EvaluationRun, User
from . import bank_service
from .diagnostic_service import LABEL, band

POLICIES = ("targeted", "random", "none")

# the five demo students: (name, what is really going on, how they describe their own answer)
CASES = [
    ("Student A", "MISCONCEPTION", "Applies the same faulty rule whenever a question allows it.", "I added the tops and then added the bottoms."),
    ("Student B", "CARELESS_SLIP", "Understands the idea and made one isolated error.", "I rushed and picked the wrong one."),
    ("Student C", "CALCULATION_ERROR", "Understands the idea; keeps getting the arithmetic wrong.", "I think I calculated it wrong in my head."),
    ("Student D", "MISINTERPRETATION", "Understands the idea; misread what was asked (a careless slip).", "I misread the question."),
    ("Student E", "STRONG_UNDERSTANDING", "Answers correctly; no diagnosis should be opened.", ""),
]


def _case(bank: Bank, name: str, truth: str, description: str, says: str, threshold: float) -> dict:
    question = bank.by_id["f1"]
    wrong = next(o for o in question["options"] if o.get("misconception"))
    m = wrong["misconception"]
    prior = bank.prior(question["topic"])
    base = {"name": name, "actual_cause": truth, "description": description, "question": question["prompt"]}

    if truth == "STRONG_UNDERSTANDING":
        right = correct_option(question)
        after = bayes.update(prior, question, right["id"])
        return {**base, "selected": f"{right['id']}) {right['text']}", "is_correct": True, "diagnosis": None, "diagnosis_label": "No diagnosis opened", "confidence": round(bayes.understanding(after) * 100, 1),
                "confidence_meaning": "understanding", "followups": [], "student_said": None, "outcome_correct": True}

    def near_miss(fq: dict) -> str:
        # shaky arithmetic: the most likely slip (never the misconception's option) whenever there is a sum to do
        slips = [o for o in fq["options"] if not o["correct"] and not o.get("misconception")]
        if bayes.computational(fq) and slips:
            return max(slips, key=lambda o: o.get("slip_weight", 1))["id"]
        return correct_option(fq)["id"]

    if truth == "CALCULATION_ERROR":
        # their first wrong answer is an arithmetic near miss too, not the answer a faulty rule gives
        wrong = option(question, near_miss(question))
    if truth == "MISCONCEPTION":
        answer = lambda fq: (next((o for o in fq["options"] if o.get("misconception") == m), None) or correct_option(fq))["id"]  # noqa: E731
    elif truth == "CALCULATION_ERROR":
        answer = near_miss
    else:
        answer = lambda fq: correct_option(fq)["id"]  # noqa: E731
    # the student's words are light evidence, applied before the follow-up
    evidence, slip_kind = bayes.analyze_reasoning(says, bank.misconceptions_for(question["topic"]))
    start = bayes.apply_reasoning(bayes.update(prior, question, wrong["id"]), evidence)
    # then the follow-ups, each chosen for the most information about the hypotheses still open
    belief, steps, used = start, [], [question["id"]]
    while len(steps) < bayes.MAX_FOLLOW_UPS:
        if steps and bayes.verdict_of(bayes.summarize(belief), threshold)["kind"] != "inconclusive":
            break
        choice = bayes.select_follow_up(belief, bank.probes(question["topic"]), used)
        if not choice:
            break
        probe, gain = choice
        before = bayes.summarize(belief)
        picked = answer(probe)
        belief = bayes.update(belief, probe, picked)
        after = bayes.summarize(belief)
        steps.append({"question": probe["prompt"], "response": f"{picked}) {option(probe, picked)['text']}", "gain": round(gain, 3), "misconception_before": round(before["misconception"] * 100, 1), "misconception_after": round(after["misconception"] * 100, 1)})
        used.append(probe["id"])

    initial = bayes.summarize(bayes.update(prior, question, wrong["id"]))
    verdict = bayes.verdict_of(bayes.summarize(belief), threshold)
    diagnosis = bayes.CATEGORIES.get(verdict["kind"])
    confidence = round(verdict["confidence"] * 100, 1)
    return {
        **base, "selected": f"{wrong['id']}) {wrong['text']}", "is_correct": False, "student_said": says,
        "initial": {"misconception": round(initial["misconception"] * 100, 1), "slip": round(initial["slip"] * 100, 1)},
        "followups": steps, "diagnosis": diagnosis, "diagnosis_label": LABEL.get(diagnosis or "", "Not enough evidence"),
        "confidence": confidence, "confidence_meaning": "diagnosis", "band": band(confidence), "outcome_correct": diagnosis == {"MISINTERPRETATION": "CARELESS_SLIP"}.get(truth, truth),
    }


def run(db: Session, user: User, students: int, seed: int) -> EvaluationRun:
    bank = bank_service.bank(db)
    threshold = get_settings().threshold
    policies = [simulate(bank, students, seed, p, threshold) for p in POLICIES]
    main = policies[0]
    results = {
        "seed": seed, "students": students, "threshold": get_settings().understanding_threshold,
        "precision": main["precision"], "recall": main["recall"], "f1": main["f1"],
        "slip_false_positive_rate": main["slip_false_positive_rate"],
        "calibration": main["calibration"], "followup_discrimination": main["followup_discrimination"],
        "policies": policies,
        "cases": [_case(bank, *c, threshold) for c in CASES],
    }
    row = EvaluationRun(user_id=user.id, seed=seed, students=students, results=results)
    db.add(row)
    db.commit()
    return row
