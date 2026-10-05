"""
The investigation that follows a wrong answer.

    wrong answer → the specific wrong option → evidence → competing hypotheses
    → discriminating follow-up → re-evaluation → confidence

A wrong answer never becomes a "misconception" on its own. The confidence comes from the
engine (app/engine/bayes.py); Groq, when configured, contributes what it reads in the
student's explanation and the wording of the feedback.
"""
from contextvars import ContextVar

from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.errors import ApiError
from ..core.logging import log
from ..engine import bayes
from ..engine.bank import correct_option, option
from ..models import Attempt, DiagnosticSession, FollowUpQuestion, Question, User
from ..prompts.diagnosis import DIAGNOSIS_PROMPT_VERSION
from ..prompts.followup import FOLLOWUP_PROMPT_VERSION
from . import bank_service, reward_service
from .ai_client import ProviderError
from .groq_service import get_groq

MAX_RETRIES = 2
# switched off while scripted demo data is generated, so loading it is instant and costs no AI calls
use_ai: ContextVar[bool] = ContextVar("use_ai", default=True)
STRENGTH = {"weak": 1.5, "moderate": 2.2, "strong": 3.0}
LABEL = {"MISCONCEPTION": "Misconception", "CARELESS_SLIP": "Careless slip", "GAP_IN_UNDERSTANDING": "Gap in understanding", "CALCULATION_ERROR": "Calculation error"}
# what each category means, said to the student
MEANING = {
    "misconception": "You have a wrong mental model of this idea: the same faulty rule shows up more than once.",
    "careless_slip": "You knew this, but a small error slipped in.",
    "gap_in_understanding": "This idea has not been learned yet, so it needs teaching from the start.",
    "calculation_error": "You understood the idea and the method, but the arithmetic went wrong.",
}


def band(confidence: float) -> str:
    """0-49 weak, 50-69 uncertain, 70-84 supported, 85-100 strong. A conclusion still needs MORE than the threshold."""
    return "Weak evidence" if confidence < 50 else "Uncertain" if confidence < 70 else "Supported" if confidence < 85 else "Strongly supported"


def _threshold() -> float:
    return get_settings().threshold


def _hyp_label(hyp: str, ms: dict[str, dict]) -> str:
    return "a careless slip" if hyp == "understands" else "a gap in understanding" if hyp == "unknown" else "a calculation error" if hyp == "calculation" else f"the rule “{ms[hyp]['name']}”" if hyp in ms else "a misconception"


def _kind_to_hypothesis(kind: str, slip_kind: str | None = None) -> str:
    return bayes.CATEGORIES[bayes.canonical_kind(kind)]


def _hypotheses(summary: dict, slip_kind: str | None = None) -> list[dict]:
    rows = [("MISCONCEPTION", summary["misconception"]), ("CARELESS_SLIP", summary["slip"]), ("GAP_IN_UNDERSTANDING", summary["unexplained"]), ("CALCULATION_ERROR", summary.get("calculation", 0.0))]
    return sorted(({"kind": k, "label": LABEL[k], "confidence": round(p * 100, 1)} for k, p in rows), key=lambda r: -r["confidence"])


def _refresh(db: Session, s: DiagnosticSession, qd: dict, ms: dict[str, dict]) -> None:
    """Recompute what the session currently believes, and the plain-language evidence behind it."""
    summary = bayes.summarize(s.belief)
    ranked = _hypotheses(summary, s.slip_kind)
    s.primary_hypothesis = ranked[0]["kind"]
    s.alternative_hypotheses = [r["kind"] for r in ranked[1:]]

    picked = option(qd, s.selected_option)
    evidence = []
    if picked.get("misconception") and picked["misconception"] in ms:
        evidence.append(f"Option {picked['id']} is the answer the rule “{ms[picked['misconception']]['name']}” produces. It is also the easiest place for a slip to land.")
    else:
        evidence.append(f"Option {picked['id']} does not match a known misconception pattern. {picked.get('reasoning', '')}".strip())
    for e in s.reasoning_evidence or []:
        evidence.append(f"You said “{e['matched']}”, which points towards {_hyp_label(e['hyp'], ms)}.")
    for i, step in enumerate(s.steps or [], 1):
        evidence.append(f"Follow-up {i}: {step['outcome']}")
    if not s.steps:
        evidence.append("One wrong answer cannot tell a misconception from a slip, so a follow-up question is needed.")
    s.evidence = evidence


def start(db: Session, user: User, attempt: Attempt, question: Question, belief_before: dict) -> DiagnosticSession:
    """Open the investigation: record the wrong option and update the hypotheses with it. No label yet."""
    qd = bank_service.q_dict(question)
    _, ms_list, _ = bank_service.context(db, question)
    belief = bayes.update(belief_before, qd, attempt.selected_option)
    summary = bayes.summarize(belief)
    s = DiagnosticSession(
        user_id=user.id, attempt_id=attempt.id, question_id=question.id, topic=question.topic, selected_option=attempt.selected_option,
        belief_before=belief_before, belief=belief, initial=summary, steps=[], status="FOLLOWUP_REQUIRED",
        initial_confidence=round(max(summary["misconception"], summary["slip"], summary["unexplained"]) * 100, 1),
    )
    _refresh(db, s, qd, {m["id"]: m for m in ms_list})
    db.add(s)
    db.flush()
    if attempt.reasoning:
        add_reasoning(db, user, s, attempt.reasoning)
    return s


def add_reasoning(db: Session, user: User, s: DiagnosticSession, text: str) -> None:
    """Fold the student's own explanation in as light evidence. Accepted once, before any follow-up."""
    text = (text or "").strip()
    if not text or s.reasoning or s.steps or s.final_diagnosis:
        return
    question = db.get(Question, s.question_id)
    qd = bank_service.q_dict(question)
    _, ms_list, _ = bank_service.context(db, question)
    ms = {m["id"]: m for m in ms_list}

    evidence, slip_kind = None, None
    groq = get_groq()
    if groq.configured and use_ai.get():
        try:
            hyps = {"understands": "understands the idea; a careless slip or a misreading", "calculation": "understands the method but got the arithmetic wrong", "unknown": "has not learned this; guessing or confused", **{k: v["rule"] for k, v in ms.items()}}
            a = groq.analyze_reasoning(qd, f"{s.selected_option}) {option(qd, s.selected_option)['text']}", text, hyps)
            evidence = [{"hyp": x.hypothesis, "ratio": STRENGTH[x.strength], "matched": x.quote[:160] or text[:60], "source": "groq"} for x in a.signals if x.hypothesis in s.belief]
            # a kind of slip only means something if the explanation actually pointed to a slip
            slip_kind = a.slip_kind if a.slip_kind in ("CALCULATION_ERROR", "MISINTERPRETATION") and any(e["hyp"] in ("understands", "calculation") for e in evidence) else None
            s.prompt_version = DIAGNOSIS_PROMPT_VERSION
        except ProviderError:
            log.warning("Groq unavailable for reasoning analysis; using phrase matching")
    if evidence is None:
        evidence, slip_kind = bayes.analyze_reasoning(text, ms_list)

    s.reasoning = text[:4000]
    s.reasoning_evidence = evidence
    s.slip_kind = slip_kind
    # Words alone never settle it: if the explanation would push a hypothesis over the threshold,
    # its weight is scaled back until the follow-up is still what decides.
    before = s.belief
    for weight in (1.0, 0.8, 0.6, 0.4, 0.2, 0.0):
        s.belief = bayes.apply_reasoning(before, [{**e, "ratio": float(e["ratio"]) ** weight} for e in evidence])
        if bayes.verdict_of(bayes.summarize(s.belief), _threshold())["kind"] == "inconclusive":
            break
    _refresh(db, s, qd, ms)


def _pending(s: DiagnosticSession) -> FollowUpQuestion | None:
    return next((f for f in s.followups if f.response is None), None)


def _generate_probe(db: Session, s: DiagnosticSession, question: Question, qd: dict, ms: dict[str, dict], top: str | None) -> dict | None:
    """For questions made from uploaded material there is no verified probe, so Groq writes one."""
    groq = get_groq()
    if not (question.owner_id and groq.configured):
        return None
    asked = [qd["prompt"]] + [f.question for f in s.followups]
    # with no known pattern behind the chosen option, the follow-up tests the idea itself
    suspected = ms[top]["rule"] if top and top in ms else "has not fully understood the idea this question tests"
    g = groq.follow_up(qd, option(qd, s.selected_option)["text"], correct_option(qd)["text"], suspected, asked)
    letters = "ABCD"
    options = [
        {"id": letters[i], "text": t, "correct": letters[i] == g.correct_option, "misconception": top if letters[i] == g.misconception_option else None,
         "reasoning": "Follows the mistaken rule." if letters[i] == g.misconception_option else "", "slip_weight": 3 if letters[i] == g.misconception_option else 1}
        for i, t in enumerate(g.options)
    ]
    row = Question(
        owner_id=question.owner_id, study_material_id=question.study_material_id, topic=question.topic, role="probe", question_type="MCQ", question_text=g.question,
        marks=1, options=options, correct_option=g.correct_option, explanation=g.explanation,
        diagnostic_metadata={"parent": (question.diagnostic_metadata or {}).get("parent") or question.id, "targets": top, "purpose": g.purpose, "prompt_version": FOLLOWUP_PROMPT_VERSION},
    )
    db.add(row)
    db.flush()
    return bank_service.q_dict(row)


def next_followup(db: Session, user: User, s: DiagnosticSession) -> FollowUpQuestion | None:
    """
    Choose the question that best separates the hypotheses still in play and record why.
    Returns None when nothing useful is left to ask; the session is then concluded.
    """
    if s.final_diagnosis:
        raise ApiError("DIAGNOSTIC_CLOSED", "This diagnosis is already complete.", 409)
    if pending := _pending(s):
        return pending

    question = db.get(Question, s.question_id)
    qd = bank_service.q_dict(question)
    _, ms_list, probes = bank_service.context(db, question)
    ms = {m["id"]: m for m in ms_list}
    used = [s.question_id] + [st["question_id"] for st in s.steps]
    summary = bayes.summarize(s.belief)
    top = summary["top_misconception"]

    choice = bayes.select_follow_up(s.belief, probes, used) if len(s.steps) < bayes.MAX_FOLLOW_UPS else None
    source = "bank"
    if not choice and len(s.steps) < bayes.MAX_FOLLOW_UPS:
        probe = _generate_probe(db, s, question, qd, ms, top)
        if probe:
            choice, source = (probe, bayes.expected_info_gain(s.belief, probe)), "groq"
    if not choice:
        conclude(db, user, s)
        return None

    probe, gain = choice
    a = bayes.predict(probe, top) if top else None
    b = bayes.predict(probe, "understands")
    name_a = ms[top]["name"] if top in ms else "Misconception"
    discriminates = bool(a and a["option_id"] != b["option_id"])
    f = FollowUpQuestion(
        diagnostic_session_id=s.id, question_id=probe["id"], question=probe["prompt"], source=source, gain=gain,
        purpose=(
            "Chosen because the two explanations expect different answers to it: your answer counts as evidence for one and against the other."
            if discriminates else "Checks whether the same idea holds up on a fresh problem."
        ),
        hypothesis_a=f"Misconception: {name_a}", hypothesis_b="Careless slip",
        expected_signal_a=f"{a['option_id']}) {option(probe, a['option_id'])['text']}" if a else "",
        expected_signal_b=f"{b['option_id']}) {option(probe, b['option_id'])['text']}",
    )
    db.add(f)
    s.followups.append(f)
    s.status = "FOLLOWUP_REQUIRED"
    db.flush()
    return f


def evaluate_followup(db: Session, user: User, s: DiagnosticSession, option_id: str, reasoning: str | None = None) -> list[dict]:
    """Take the answer to the pending follow-up as new evidence and re-evaluate. Returns anything newly unlocked."""
    f = _pending(s)
    if not f:
        raise ApiError("FOLLOWUP_NOT_REQUESTED", "Ask for a follow-up question first.", 409)
    probe_row = db.get(Question, f.question_id)
    probe = bank_service.q_dict(probe_row)
    picked = option(probe, option_id)
    if not picked:
        raise ApiError("INVALID_OPTION", "That is not one of the options for this question.", 422)

    question = db.get(Question, s.question_id)
    qd = bank_service.q_dict(question)
    _, ms_list, probes = bank_service.context(db, question)
    ms = {m["id"]: m for m in ms_list}

    before = bayes.summarize(s.belief)
    target = before["top_misconception"]
    pattern = next((o for o in probe["options"] if o.get("misconception") and o["misconception"] == target), None)
    s.belief = bayes.update(s.belief, probe, option_id)
    after = bayes.summarize(s.belief)

    outcome = (
        "the same pattern appeared again, which a one-off slip would be unlikely to repeat." if pattern and pattern["id"] == option_id
        else "answered correctly, the way someone who understands the idea would." if picked["correct"]
        else "wrong, but not in the way the suspected misconception predicts."
    )
    if_mis = bayes.predict(probe, target) if target else None
    if_slip = bayes.predict(probe, "understands")
    s.steps = [*s.steps, {
        "question_id": probe["id"], "selected": option_id, "correct": bool(picked["correct"]), "before": before, "after": after, "gain": f.gain,
        "purpose": f.purpose, "outcome": outcome, "reasoning": (reasoning or "")[:1000] or None,
        "predictions": {"misconception": if_mis, "slip": if_slip, "discriminates": bool(if_mis and if_mis["option_id"] != if_slip["option_id"])},
    }]
    f.response = option_id
    s.followup_question_id, s.followup_response = probe["id"], f"{option_id}) {picked['text']}"
    _refresh(db, s, qd, ms)

    used = [s.question_id] + [st["question_id"] for st in s.steps]
    inconclusive = bayes.verdict_of(after, _threshold())["kind"] == "inconclusive"
    more_possible = any(p["id"] not in used for p in probes) or bool(question.owner_id and get_groq().configured)
    if inconclusive and len(s.steps) < bayes.MAX_FOLLOW_UPS and more_possible:
        s.status = "FOLLOWUP_REQUIRED"
        return []
    return conclude(db, user, s)


def _feedback(s: DiagnosticSession, qd: dict, ms: dict[str, dict], kind: str) -> str:
    m = ms.get(s.misconception_id or "")
    n = len(s.steps)
    template = {
        "misconception": f"Misconception: you have a wrong mental model of this idea. The same pattern showed up again on the follow-up, which points to a rule rather than a one-off error: {m['name'] if m else 'a misconception'}. {m['rule'] if m else ''} A few minutes on this now will stop it coming back.",
        "careless_slip": "Careless slip: you knew this but made a small error. You handled the follow-up the way someone who understands the idea would, so there is nothing to reteach here. Slow down on the last step next time.",
        "gap_in_understanding": "Gap in understanding: this idea has not been learned yet. Your answers do not follow any one pattern, which is what happens when a topic is new. Working through it from the start is the best next step.",
        "calculation_error": "Calculation error: you understood the idea and the method, but the arithmetic went wrong. The concept is fine; practise the working and check each step.",
        "inconclusive": f"After {n} follow-up question{'' if n == 1 else 's'} the evidence still points more than one way, so no label is being put on this. More evidence is needed before drawing a conclusion.",
    }[kind].strip()
    if kind == "careless_slip" and s.slip_kind == "MISINTERPRETATION":
        template = "It looks like the question was misread. " + template
    groq = get_groq()
    if groq.configured and use_ai.get():
        try:
            return groq.feedback(qd, option(qd, s.selected_option)["text"], correct_option(qd)["text"], LABEL.get(s.final_diagnosis or "", "Not enough evidence"), round(s.final_confidence or 0), s.status, s.evidence)
        except ProviderError:
            log.warning("Groq unavailable for feedback; using the built-in wording")
    return template


def conclude(db: Session, user: User, s: DiagnosticSession) -> list[dict]:
    """State the diagnosis the evidence supports, or say plainly that it does not support one."""
    if s.final_diagnosis:
        return []
    question = db.get(Question, s.question_id)
    qd = bank_service.q_dict(question)
    prior, ms_list, _ = bank_service.context(db, question)
    ms = {m["id"]: m for m in ms_list}

    final = bayes.summarize(s.belief)
    verdict = bayes.verdict_of(final, _threshold())
    kind = verdict["kind"]
    # the concept is sound and the student says the arithmetic went wrong: that one-off is a calculation error
    if kind == "careless_slip" and s.slip_kind == "CALCULATION_ERROR":
        kind = "calculation_error"
    s.final = {**final, "verdict": kind}
    s.final_confidence = round(verdict["confidence"] * 100, 1)
    if kind == "inconclusive":
        # the leaning is recorded, but the status says it was not confirmed
        s.final_diagnosis = _hypotheses(final, s.slip_kind)[0]["kind"]
        s.status = "UNCERTAIN"
        s.misconception_id = None
    else:
        s.final_diagnosis = _kind_to_hypothesis(kind, s.slip_kind)
        s.status = "SUPPORTED"
        s.misconception_id = verdict["misconception"]
    _refresh(db, s, qd, ms)

    if verdict["kind"] == "careless_slip":
        # the follow-up itself was the retest: understanding was demonstrated above the threshold
        s.corrected, s.understanding, s.status = True, round(final["slip"] * 100, 1), "CORRECTED"
        reward_service.award_correction(db, user, s.id)
    if question.owner_id is None and bank_service.is_bank_topic(s.topic):
        user.beliefs = {**(user.beliefs or {}), s.topic: s.belief}
    s.feedback = _feedback(s, qd, ms, kind)
    db.flush()
    return reward_service.check_unlocks(db, user)


# ───────────────────────── targeted help and retest ─────────────────────────


def _retry_pool(db: Session, s: DiagnosticSession, question: Question) -> list[dict]:
    qd = bank_service.q_dict(question)
    _, _, probes = bank_service.context(db, question)
    used = [s.question_id] + [st["question_id"] for st in s.steps]
    if s.misconception_id:
        own = [p for p in probes if p.get("targets") == s.misconception_id]
        fresh = [p for p in own if p["id"] not in used]
        pool = fresh + [p for p in own if p["id"] in used]
        return pool or [qd]
    # prefer a different question on the same idea; fall back to the original
    return [p for p in probes if p["id"] not in used] + [qd]


def _help(db: Session, s: DiagnosticSession, question: Question) -> dict:
    """Help aimed at the specific faulty rule, or a worked solution when no rule was identified."""
    _, ms_list, _ = bank_service.context(db, question)
    m = next((x for x in ms_list if x["id"] == s.misconception_id), None)
    last = s.retry[-1] if s.retry else None
    shown = bank_service.q_dict(db.get(Question, last["question_id"])) if last else bank_service.q_dict(question)
    picked = option(shown, last["selected"] if last else s.selected_option)
    return {
        "kind": "targeted" if m else "worked_solution",
        "misconception": {"id": m["id"], "name": m["name"], "rule": m["rule"], "explanation": m["explanation"], "worked_example": m["worked_example"]} if m else None,
        "question": shown["prompt"],
        "your_answer": {"id": picked["id"], "text": picked["text"], "reasoning": picked.get("reasoning", "")},
        "correct_answer": {"id": correct_option(shown)["id"], "text": correct_option(shown)["text"]},
        "solution": shown["solution"],
    }


def retry_start(db: Session, user: User, s: DiagnosticSession) -> dict:
    if not s.final_diagnosis:
        raise ApiError("DIAGNOSTIC_OPEN", "Finish the diagnosis before retrying.", 409)
    question = db.get(Question, s.question_id)
    pool = _retry_pool(db, s, question)
    # a retest starts a fresh run of at most MAX_RETRIES questions
    run = [r for r in s.retry if not r.get("closed")]
    current = pool[min(len(run), len(pool) - 1)]
    return {"mistake_id": s.id, "help": _help(db, s, question), "question": bank_service.public(current), "retry_number": len(run) + 1, "max_retries": MAX_RETRIES}


def retry_evaluate(db: Session, user: User, s: DiagnosticSession, question_id: str, option_id: str) -> dict:
    """The retest. The mistake counts as corrected only if understanding, judged on this answer, is above the threshold."""
    if not s.final_diagnosis:
        raise ApiError("DIAGNOSTIC_OPEN", "Finish the diagnosis before retrying.", 409)
    question = db.get(Question, s.question_id)
    pool = _retry_pool(db, s, question)
    run = [r for r in s.retry if not r.get("closed")]
    expected = pool[min(len(run), len(pool) - 1)]
    last = s.retry[-1] if s.retry else None

    if last and last["question_id"] == question_id and last["selected"] == option_id and question_id != expected["id"]:
        asked = bank_service.q_dict(db.get(Question, question_id))  # the same request sent twice
        understanding, unlocked = last["understanding"], []
    else:
        if question_id != expected["id"]:
            raise ApiError("INVALID_QUESTION", "That is not the current retry question.", 409)
        asked = expected
        if not option(asked, option_id):
            raise ApiError("INVALID_OPTION", "That is not one of the options for this question.", 422)
        understanding = bayes.understanding_after_retry([(asked, option_id)], s.misconception_id)
        passed = understanding > _threshold()
        run_len = len(run) + 1
        done = passed or run_len >= MAX_RETRIES or run_len >= len(pool)
        entry = {"question_id": question_id, "selected": option_id, "understanding": understanding, "passed": passed}
        s.retry = [*([{**r, "closed": True} for r in s.retry] if done else s.retry), {**entry, "closed": True} if done else entry]
        s.understanding = round(understanding * 100, 1)

        prior, _, _ = bank_service.context(db, question)
        if question.owner_id is None and bank_service.is_bank_topic(s.topic):
            # help may have changed what the student knows: ease the old belief, then add the retry evidence
            eased = bayes.relax((user.beliefs or {}).get(s.topic, s.belief), prior, 0.6)
            user.beliefs = {**(user.beliefs or {}), s.topic: bayes.update(eased, asked, option_id)}
        if passed and not s.corrected:
            s.corrected, s.status = True, "CORRECTED"
            reward_service.award_correction(db, user, s.id)
        unlocked = reward_service.check_unlocks(db, user)
        db.flush()

    open_run = [r for r in s.retry if not r.get("closed")]
    return {
        "mistake_id": s.id,
        "question": bank_service.revealed(asked),
        "selected_option": option_id,
        "is_correct": bool(option(asked, option_id)["correct"]),
        "understanding": round(understanding * 100, 1),
        "threshold": get_settings().understanding_threshold,
        "corrected": understanding > _threshold(),
        "mistake_status": status_of(s),
        "can_retry_again": bool(open_run),
        "unlocked": unlocked,
    }


# ───────────────────────── views ─────────────────────────


def status_of(s: DiagnosticSession) -> str:
    kind = bayes.canonical_kind((s.final or {}).get("verdict"))
    if kind == "careless_slip":
        return "SLIP_IDENTIFIED"
    if s.corrected:
        return "CORRECTED"
    return {"misconception": "MISCONCEPTION_IDENTIFIED", "gap_in_understanding": "GAP_IDENTIFIED", "calculation_error": "CALCULATION_IDENTIFIED"}.get(kind, "NEEDS_REVIEW")


def _summary_view(summary: dict) -> dict:
    return {k: round(summary.get(k, 0), 4) for k in ("misconception", "slip", "unexplained", "calculation")}


def _steps_view(db: Session, s: DiagnosticSession, ms: dict[str, dict]) -> list[dict]:
    out = []
    for st in s.steps or []:
        probe = bank_service.q_dict(db.get(Question, st["question_id"]))
        pred = st.get("predictions") or {}

        def named(p):
            return {"option_id": p["option_id"], "text": option(probe, p["option_id"])["text"], "probability": round(p["probability"], 3)} if p else None

        out.append({
            "question": bank_service.revealed(probe),
            "selected": {"id": st["selected"], "text": option(probe, st["selected"])["text"]},
            "is_correct": st["correct"],
            "before": _summary_view(st["before"]), "after": _summary_view(st["after"]),
            "gain": round(st["gain"], 3), "purpose": st.get("purpose", ""), "outcome": st.get("outcome", ""),
            "expected_if_misconception": named(pred.get("misconception")), "expected_if_slip": named(pred.get("slip")), "discriminates": pred.get("discriminates", False),
        })
    return out


def view(db: Session, s: DiagnosticSession) -> dict:
    """Everything the frontend needs to show the investigation at its current stage."""
    question = db.get(Question, s.question_id)
    qd = bank_service.q_dict(question)
    _, ms_list, _ = bank_service.context(db, question)
    ms = {m["id"]: m for m in ms_list}
    summary = bayes.summarize(s.belief)
    done = bool(s.final_diagnosis)
    kind = bayes.canonical_kind((s.final or {}).get("verdict")) if s.final_diagnosis else None
    m = ms.get(s.misconception_id or "")
    pending = _pending(s)
    picked = option(qd, s.selected_option)
    secondary = next((h for h in [s.primary_hypothesis, *(s.alternative_hypotheses or [])] if h != s.final_diagnosis), None)
    return {
        "session_id": s.id,
        "status": s.status,
        "question": bank_service.revealed(question) if done else bank_service.public(question),
        "selected": {"id": picked["id"], "text": picked["text"]},
        "summary": _summary_view(summary),
        "initial": _summary_view(s.initial),
        "hypotheses": _hypotheses(summary, s.slip_kind),
        "evidence": s.evidence,
        "reasoning": s.reasoning,
        "reasoning_evidence": [{"hypothesis": e["hyp"], "label": _hyp_label(e["hyp"], ms), "quote": e["matched"]} for e in s.reasoning_evidence or []],
        "steps": _steps_view(db, s, ms),
        "followups_used": len(s.steps or []),
        "max_followups": bayes.MAX_FOLLOW_UPS,
        "followup": {"required": not done, "pending": followup_view(db, pending) if pending else None},
        "threshold": get_settings().understanding_threshold,
        "diagnosis": {
            "primary": s.final_diagnosis if s.status != "UNCERTAIN" else None,
            "leaning": s.final_diagnosis,
            "secondary": secondary,
            "label": LABEL.get(s.final_diagnosis or "", "") if s.status != "UNCERTAIN" else "Not enough evidence yet",
            "verdict": kind,
            # what this category means, in a sentence for the student
            "meaning": MEANING.get(kind or ""),
            "confidence": s.final_confidence,
            "band": band(s.final_confidence or 0),
            "status": s.status,
            "misconception": {"id": m["id"], "name": m["name"], "rule": m["rule"]} if m else None,
        } if done else None,
        "feedback": s.feedback if done else "",
        "corrected": s.corrected,
        "mistake_status": status_of(s) if done else None,
    }


def followup_view(db: Session, f: FollowUpQuestion) -> dict:
    probe = db.get(Question, f.question_id)
    pub = bank_service.public(probe)
    return {"session_id": f.diagnostic_session_id, "followup_id": f.id, "question": pub["prompt"], "question_id": probe.id, "options": pub["options"], "purpose": f.purpose, "gain": round(f.gain, 3), "source": f.source, "hypothesis_a": f.hypothesis_a, "hypothesis_b": f.hypothesis_b}


def mistake_view(db: Session, s: DiagnosticSession) -> dict:
    """A finished investigation as a learning record for the Past Mistakes page."""
    question = db.get(Question, s.question_id)
    qd = bank_service.q_dict(question)
    _, ms_list, _ = bank_service.context(db, question)
    ms = {m["id"]: m for m in ms_list}
    m = ms.get(s.misconception_id or "")
    kind = bayes.canonical_kind((s.final or {}).get("verdict", "inconclusive"))
    picked, right = option(qd, s.selected_option), correct_option(qd)
    explanation = (
        f"{m['name']}. {m['rule']}" if m
        else f"Careless slip: {picked.get('reasoning', '')} The follow-up was answered the way someone who understands the idea would." if kind == "careless_slip"
        else "Gap in understanding: the answers did not follow any one pattern, as happens when a topic has not been learned yet." if kind == "gap_in_understanding"
        else f"Calculation error: the method was right but the arithmetic went wrong. {picked.get('reasoning', '')}".strip() if kind == "calculation_error"
        else "The evidence did not pass 70% for any one cause, so no label was given."
    )
    improvements = (
        m["explanation"] if m
        else ["You know this idea. Slow down on the last step.", "Check your answer against the question before you submit."] if kind == "careless_slip"
        else ["Write out every step of the working instead of doing it in your head.", "Check the result by working backwards or estimating it first.", qd["solution"]] if kind == "calculation_error"
        else [qd["solution"], "Start from the basic idea, then try a fresh question."]
    )
    steps = _steps_view(db, s, ms)
    return {
        "id": s.id,
        "created_at": reward_service.iso(s.created_at),
        "topic": s.topic,
        "question": bank_service.revealed(question),
        "selected": {"id": picked["id"], "text": picked["text"], "reasoning": picked.get("reasoning", "")},
        "correct": {"id": right["id"], "text": right["text"]},
        "reasoning": s.reasoning,
        "verdict": kind,
        "diagnosis": s.final_diagnosis if s.status != "UNCERTAIN" else None,
        "diagnosis_label": LABEL.get(s.final_diagnosis or "", "") if s.status != "UNCERTAIN" else "Not enough evidence",
        "misconception": {"id": m["id"], "name": m["name"], "rule": m["rule"]} if m else None,
        "confidence": s.final_confidence,
        "initial": _summary_view(s.initial), "final": _summary_view(s.final or {}),
        "steps": steps,
        "followup_question": steps[0]["question"]["prompt"] if steps else None,
        "followup_response": s.followup_response,
        "status": status_of(s),
        "corrected": s.corrected,
        "understanding": s.understanding,
        "explanation": explanation,
        "improvements": improvements,
        "what_was_learned": (m["explanation"][0] if m and m["explanation"] else qd["solution"]) if s.corrected else None,
        "meaning": MEANING.get(kind),
        "retry_status": "PASSED" if s.corrected and kind != "careless_slip" else "NOT_NEEDED" if kind == "careless_slip" else "ATTEMPTED" if s.retry else "NOT_ATTEMPTED",
        "evidence": s.evidence,
        "feedback": s.feedback,
    }
