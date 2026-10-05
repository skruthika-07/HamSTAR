"""
HamSTAR diagnostic engine.

A wrong answer is evidence, not a verdict. For each topic the engine keeps a
probability over hypotheses about the student:

    understands        – the concept is sound; any error is a careless slip
    <misconception id> – the student applies one specific faulty rule (a misconception)
    unknown            – the concept has not been learned: a gap in understanding
    calculation        – the method is understood but the arithmetic goes wrong

The verdict names one of four categories: misconception, careless_slip,
gap_in_understanding or calculation_error (or "inconclusive" below the threshold).

Every answer updates that probability with Bayes' rule. Follow-up questions are
chosen to maximise expected information gain: the question whose answer the
hypotheses still in play disagree about most.

Questions are plain dicts: {id, role, options: [{id, correct, misconception, slip_weight}]}.
Nothing here touches the database or an AI provider, so the confidence it
reports is reproducible.
"""
import math
import re

MAX_FOLLOW_UPS = 3

PARAMS = {
    "slip_main": 0.12,  # chance a student who understands still gets a main question wrong
    "slip_probe": 0.06,  # probes are simpler, so slips are rarer
    "consistency": 0.82,  # chance a student holding a misconception picks the option it predicts
    "lucky": 0.08,  # chance that student still lands on the correct answer
    "unknown_correct": 0.35,  # chance a student with an unmodelled gap answers correctly
    "prior_misconception": 0.09,
    "prior_unknown": 0.07,
    # shaky arithmetic: a sound method, but sums go wrong far more often than a one-off slip would
    "prior_calculation": 0.06,
    "calc_error_main": 0.4,
    "calc_error_probe": 0.3,
}

# the four categories a wrong answer can be put in, and the code each is stored under
CATEGORIES = {
    "misconception": "MISCONCEPTION",
    "careless_slip": "CARELESS_SLIP",
    "gap_in_understanding": "GAP_IN_UNDERSTANDING",
    "calculation_error": "CALCULATION_ERROR",
}
# names used before the four categories existed
LEGACY_KINDS = {"slip": "careless_slip", "unknown": "gap_in_understanding"}


def canonical_kind(kind: str | None) -> str:
    return LEGACY_KINDS.get(kind or "", kind or "inconclusive")

NUMBER = re.compile(r"\d")


def computational(question: dict) -> bool:
    """A question answered by working something out: every option is a number or an expression."""
    return all(NUMBER.search(str(o.get("text", ""))) for o in question["options"])
CARRY_OVER_FADE = 0.4

Belief = dict[str, float]


def base_prior(misconception_ids: list[str]) -> Belief:
    belief = {"unknown": PARAMS["prior_unknown"], "calculation": PARAMS["prior_calculation"]}
    for m in misconception_ids:
        belief[m] = PARAMS["prior_misconception"]
    belief["understands"] = 1 - PARAMS["prior_unknown"] - PARAMS["prior_calculation"] - len(misconception_ids) * PARAMS["prior_misconception"]
    return belief


def normalize(belief: Belief) -> Belief:
    total = sum(belief.values())
    return {k: (v / total if total > 0 else 0.0) for k, v in belief.items()}


def likelihood(question: dict, option_id: str, hyp: str) -> float:
    """P(student picks this option | hypothesis). Sums to 1 over the options."""
    options = question["options"]
    option = next(o for o in options if o["id"] == option_id)
    wrong = [o for o in options if not o["correct"]]

    if hyp == "unknown":
        return PARAMS["unknown_correct"] if option["correct"] else (1 - PARAMS["unknown_correct"]) / len(wrong)

    total_weight = sum(o.get("slip_weight", 1) for o in wrong)
    if hyp == "calculation":
        if computational(question):
            err = PARAMS["calc_error_probe"] if question.get("role") == "probe" else PARAMS["calc_error_main"]
            if option["correct"]:
                return 1 - err
            # an arithmetic error lands on a near miss, not on the answer a faulty rule produces
            near = [o for o in wrong if not o.get("misconception")] or wrong
            far_each = 0.01 * err  # almost never; never zero, so one odd answer cannot rule the hypothesis out
            if option not in near:
                return far_each
            near_total = err - far_each * (len(wrong) - len(near))
            return near_total * option.get("slip_weight", 1) / (sum(o.get("slip_weight", 1) for o in near) or 1)
        hyp = "understands"  # nothing to calculate: answers like anyone who knows the idea

    if hyp != "understands":
        predicted = [o for o in wrong if o.get("misconception") == hyp]
        if predicted:
            others = len(wrong) - len(predicted)
            rest = 1 - PARAMS["consistency"] - PARAMS["lucky"]
            if option.get("misconception") == hyp:
                return PARAMS["consistency"] / len(predicted)
            if option["correct"]:
                return PARAMS["lucky"] if others > 0 else PARAMS["lucky"] + rest
            return rest / others
        # the question does not trigger this misconception: answer like anyone who understands it

    slip = PARAMS["slip_probe"] if question.get("role") == "probe" else PARAMS["slip_main"]
    if option["correct"]:
        return 1 - slip
    return slip * option.get("slip_weight", 1) / total_weight


def update(belief: Belief, question: dict, option_id: str) -> Belief:
    return normalize({h: p * likelihood(question, option_id, h) for h, p in belief.items()})


def relax(belief: Belief, prior: Belief, amount: float) -> Belief:
    """Pull the belief part of the way back to the prior: students change, old evidence should fade."""
    return normalize({h: (1 - amount) * belief.get(h, p) + amount * p for h, p in prior.items()})


def carry_over(belief: Belief, prior: Belief) -> Belief:
    return relax(belief, prior, CARRY_OVER_FADE)


def summarize(belief: Belief) -> dict:
    """Collapse the belief into the competing explanations shown to the student."""
    top, top_p = None, 0.0
    for h, p in belief.items():
        if h in ("understands", "unknown", "calculation"):
            continue
        if p > top_p:
            top, top_p = h, p
    unexplained = belief.get("unknown", 0.0)
    calculation = belief.get("calculation", 0.0)
    # another misconception this question does not trigger still makes this error a slip
    return {"misconception": top_p, "unexplained": unexplained, "calculation": calculation, "slip": max(0.0, 1 - top_p - unexplained - calculation), "top_misconception": top}


def verdict_of(summary: dict, threshold: float = 0.7) -> dict:
    """A label is stated only when its probability is strictly above the threshold."""
    calculation = summary.get("calculation", 0.0)
    if summary["misconception"] > threshold:
        return {"kind": "misconception", "confidence": summary["misconception"], "misconception": summary["top_misconception"]}
    if summary["slip"] > threshold:
        return {"kind": "careless_slip", "confidence": summary["slip"], "misconception": None}
    if summary["unexplained"] > threshold:
        return {"kind": "gap_in_understanding", "confidence": summary["unexplained"], "misconception": None}
    if calculation > threshold:
        return {"kind": "calculation_error", "confidence": calculation, "misconception": None}
    # Both careless slips and calculation errors mean the concept itself is sound. When that is clear but the evidence
    # splits between the two, the more likely of them is named, with the confidence that it was not a conceptual error.
    execution = summary["slip"] + calculation
    if execution > threshold:
        kind = "calculation_error" if calculation > summary["slip"] else "careless_slip"
        return {"kind": kind, "confidence": execution, "misconception": None}
    return {
        "kind": "inconclusive",
        "confidence": max(summary["misconception"], summary["slip"], summary["unexplained"], calculation),
        "misconception": summary["top_misconception"],
    }


def understanding(belief: Belief) -> float:
    """How likely it is that the student understands the concept: a careless slip or an arithmetic error does not count against it."""
    return belief.get("understands", 0.0) + belief.get("calculation", 0.0)


def leaning_of(summary: dict) -> str:
    """The category with the most weight, whether or not it passes the threshold."""
    return max(
        (("misconception", summary["misconception"]), ("careless_slip", summary["slip"]), ("gap_in_understanding", summary["unexplained"]), ("calculation_error", summary.get("calculation", 0.0))),
        key=lambda kv: kv[1],
    )[0]


def expected_info_gain(belief: Belief, question: dict) -> float:
    """Bits by which the answer is expected to reduce uncertainty. Zero when every hypothesis predicts the same answer."""
    hyps = list(belief)
    gain = 0.0
    for o in question["options"]:
        per = [likelihood(question, o["id"], h) for h in hyps]
        marginal = sum(belief[h] * p for h, p in zip(hyps, per))
        for h, p in zip(hyps, per):
            if belief[h] > 0 and p > 0:
                gain += belief[h] * p * math.log2(p / marginal)
    return max(0.0, gain)


def select_follow_up(belief: Belief, probes: list[dict], exclude: list[str]) -> tuple[dict, float] | None:
    """The unused probe whose answer best separates the current hypotheses."""
    best = None
    for q in probes:
        if q["id"] in exclude:
            continue
        gain = expected_info_gain(belief, q)
        if best is None or gain > best[1]:
            best = (q, gain)
    return best


def predict(question: dict, hyp: str) -> dict:
    """What a hypothesis expects the student to answer."""
    best = {"option_id": question["options"][0]["id"], "probability": 0.0}
    for o in question["options"]:
        p = likelihood(question, o["id"], hyp)
        if p > best["probability"]:
            best = {"option_id": o["id"], "probability": p}
    return best


# ───────────────────────── the student's own explanation ─────────────────────────

MISREAD_CUES = [r"mis-?read", r"did\s?n[o']t\s+(see|notice|read)", r"read\s+it\s+wrong", r"thought\s+(it|the\s+question)\s+(said|asked)", r"misunderstood\s+the\s+question"]
CALC_CUES = [r"calculat", r"arithmetic", r"(added|multiplied|subtracted|divided)\s+(it\s+)?wrong", r"wrong\s+(sum|number|answer\s+for\s+the\s+sum)", r"(sum|working|maths?|numbers?)\s+(was\s+|were\s+)?wrong", r"worked\s+(it\s+|the\s+\w+\s+)?out\s+wrong", r"miscount", r"times\s+tables?"]
SLIP_CUES = [r"rush(ed|ing)?", r"careless", r"typo", r"mis-?click", r"(by|silly)\s+mistake", r"forgot\s+to", r"too\s+(fast|quick)", r"did\s?n[o']t\s+check", r"wrong\s+(button|option|one)", r"i\s+know\s+(how|it|this)"]
UNKNOWN_CUES = [r"guess(ed|ing)?", r"no\s+idea", r"(do\s?n[o']t|did\s?n[o']t)\s+(know|understand)", r"not\s+sure", r"confus(ed|ing)"]


def _first(patterns: list[str], text: str) -> str | None:
    for p in patterns:
        try:
            hit = re.search(p, text, re.IGNORECASE)
        except re.error:
            continue
        if hit:
            return hit.group(0)
    return None


def analyze_reasoning(text: str, misconceptions: list[dict]) -> tuple[list[dict], str | None]:
    """
    Phrase matching over the student's explanation. Deliberately weak evidence
    (small likelihood ratios): what a student says is a hint, the follow-up is the test.
    Returns the evidence and, when the words point to one, the kind of slip.
    """
    evidence: list[dict] = []
    if not text or not text.strip():
        return evidence, None
    for m in misconceptions:
        hit = _first(m.get("indicators", []), text)
        if hit:
            evidence.append({"hyp": m["id"], "ratio": 3.0, "matched": hit})
    slip_kind = None
    misread, calc = _first(MISREAD_CUES, text), _first(CALC_CUES, text)
    if calc:
        evidence.append({"hyp": "calculation", "ratio": 2.0, "matched": calc})
        slip_kind = "CALCULATION_ERROR"
    slip = misread or (None if calc else _first(SLIP_CUES, text))
    if slip:
        evidence.append({"hyp": "understands", "ratio": 2.0, "matched": slip})
        slip_kind = "MISINTERPRETATION" if misread else None
    unknown = _first(UNKNOWN_CUES, text)
    if unknown:
        evidence.append({"hyp": "unknown", "ratio": 2.5, "matched": unknown})
    return evidence, slip_kind


def apply_reasoning(belief: Belief, evidence: list[dict]) -> Belief:
    nxt = dict(belief)
    for e in evidence:
        if e["hyp"] in nxt:
            # explanations never count for more than a light nudge, whoever analysed them
            nxt[e["hyp"]] *= min(max(float(e["ratio"]), 1 / 3), 3.0)
    return normalize(nxt)


def understanding_after_retry(answers: list[tuple[dict, str]], misconception: str | None) -> float:
    """
    After targeted help the student may have changed, so understanding is re-estimated
    from the retry answers alone, from an even prior between "now understands" and
    "still holds the same confusion".
    """
    understands, confused = 0.5, 0.5
    rival = misconception or "unknown"
    for question, selected in answers:
        understands *= likelihood(question, selected, "understands")
        confused *= likelihood(question, selected, rival)
    return understands / (understands + confused)
