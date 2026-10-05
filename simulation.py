"""
Simulated students with an injected cause, used to measure the diagnostic engine.
Every figure the Evaluation Lab shows is computed here from simulated answers.

The simulated students deliberately do NOT follow the engine's assumptions exactly:
each has their own slip rate and their own consistency in applying a misconception,
so calibration is a real test rather than a tautology.
"""
from collections.abc import Callable

from . import bayes
from .bank import Bank, correct_option

Rng = Callable[[], float]
BIN_EDGES = [0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0001]


def mulberry32(seed: int) -> Rng:
    a = seed & 0xFFFFFFFF

    def imul(x: int, y: int) -> int:
        return (x * y) & 0xFFFFFFFF

    def rng() -> float:
        nonlocal a
        a = (a + 0x6D2B79F5) & 0xFFFFFFFF
        t = a
        t = imul(t ^ (t >> 15), t | 1)
        t ^= (t + imul(t ^ (t >> 7), t | 61)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    return rng


def run_episode(bank: Bank, belief_before: dict, question: dict, selected: str, answer: Callable[[dict], str], policy: str = "targeted", rng: Rng | None = None, threshold: float = 0.7) -> dict:
    """One diagnosis: wrong answer → follow-up(s) → verdict. `answer` supplies the reply to each follow-up."""
    belief = bayes.update(belief_before, question, selected)
    initial = bayes.summarize(belief)
    steps: list[dict] = []
    used = [question["id"]]

    while policy != "none" and len(steps) < bayes.MAX_FOLLOW_UPS:
        if steps and bayes.verdict_of(bayes.summarize(belief), threshold)["kind"] != "inconclusive":
            break
        nxt, gain = None, 0.0
        if policy == "targeted":
            choice = bayes.select_follow_up(belief, bank.probes(question["topic"]), used)
            if choice:
                nxt, gain = choice
        else:
            pool = [q for q in bank.questions if q["topic"] == question["topic"] and q["id"] not in used]
            if pool and rng:
                nxt = pool[int(rng() * len(pool))]
                gain = bayes.expected_info_gain(belief, nxt)
        if not nxt:
            break
        before = bayes.summarize(belief)
        picked = answer(nxt)
        belief = bayes.update(belief, nxt, picked)
        steps.append({"question_id": nxt["id"], "selected": picked, "before": before, "after": bayes.summarize(belief), "gain": gain})
        used.append(nxt["id"])

    final = bayes.summarize(belief)
    return {"question_id": question["id"], "selected": selected, "prior": bayes.summarize(belief_before), "initial": initial, "steps": steps, "final": final, "verdict": bayes.verdict_of(final, threshold), "belief": belief}


def _pick_weighted(items: list[dict], rng: Rng) -> dict:
    total = sum(o["slip_weight"] for o in items)
    r = rng() * total
    for o in items:
        r -= o["slip_weight"]
        if r <= 0:
            return o
    return items[-1]


def respond(student: dict, question: dict, rng: Rng) -> tuple[str, str | None]:
    """How a simulated student answers, using their own parameters. Returns (option id, cause of a wrong answer)."""
    correct = correct_option(question)
    wrong = [o for o in question["options"] if not o["correct"]]

    if student["kind"] == "gap":
        if rng() < student["guess_correct"]:
            return correct["id"], None
        return wrong[int(rng() * len(wrong))]["id"], "gap"

    if student["kind"] == "misconception":
        predicted = [o for o in wrong if o.get("misconception") == student["misconception"]]
        if predicted:
            if rng() < student["consistency"]:
                return predicted[int(rng() * len(predicted))]["id"], "misconception"
            if rng() < 0.5:
                return correct["id"], None
            others = [o for o in wrong if o.get("misconception") != student["misconception"]]
            pool = others or wrong
            return pool[int(rng() * len(pool))]["id"], "misconception"

    # the concept is sound for this question: any error is an injected slip
    slip_rate = student["slip_rate"] * 0.5 if question["role"] == "probe" else student["slip_rate"]
    if rng() >= slip_rate:
        return correct["id"], None
    return _pick_weighted(wrong, rng)["id"], "slip"


def _make_student(bank: Bank, i: int, rng: Rng) -> dict:
    topics = [t["id"] for t in bank.topics]
    topic = topics[0] if rng() < 0.5 else topics[-1]
    r = rng()
    kind = "misconception" if r < 0.45 else "slip" if r < 0.9 else "gap"
    ms = bank.misconceptions_for(topic)
    return {
        "id": i,
        "kind": kind,
        "topic": topic,
        "misconception": ms[int(rng() * len(ms))]["id"] if kind == "misconception" else None,
        "slip_rate": 0.05 + rng() * 0.2,
        "consistency": 0.65 + rng() * 0.3,
        "guess_correct": 0.25 + rng() * 0.25,
    }


def _shuffled(items: list, rng: Rng) -> list:
    a = list(items)
    for i in range(len(a) - 1, 0, -1):
        j = int(rng() * (i + 1))
        a[i], a[j] = a[j], a[i]
    return a


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def simulate(bank: Bank, n_students: int, seed: int, policy: str, threshold: float = 0.7) -> dict:
    episodes: list[dict] = []
    by_mis, by_slip = {"k": 0, "n": 0}, {"k": 0, "n": 0}

    for i in range(n_students):
        # one generator per student, so every policy sees the same students making the same first mistake
        rng = mulberry32(seed * 100003 + i * 7919)
        student = _make_student(bank, i, rng)
        prior = bank.prior(student["topic"])
        belief = dict(prior)

        for question in _shuffled(bank.main(student["topic"]), rng):
            selected, cause = respond(student, question, rng)
            belief = bayes.carry_over(belief, prior)
            if cause is None:
                belief = bayes.update(belief, question, selected)
                continue
            trace = run_episode(bank, belief, question, selected, lambda fq: respond(student, fq, rng)[0], policy, rng, threshold)
            final, verdict = trace["final"], trace["verdict"]
            leaning = bayes.leaning_of(final)

            def matches(label: str, m: str | None) -> bool:
                # a simulated "slip" is an execution error: careless or in the arithmetic, never a wrong idea
                return (label == "misconception" and cause == "misconception" and m == student["misconception"]) or (label in ("careless_slip", "calculation_error") and cause == "slip") or (label == "gap_in_understanding" and cause == "gap")

            episodes.append({
                "cause": cause,
                "verdict": verdict["kind"],
                "confidence": verdict["confidence"],
                "steps": trace["steps"],
                "leaning_confidence": max(final["misconception"], final["slip"], final["unexplained"], final.get("calculation", 0.0)),
                "leaning_correct": matches(leaning, final["top_misconception"]),
                "verdict_correct": matches(verdict["kind"], verdict["misconception"]),
            })

            if trace["steps"]:
                first = trace["steps"][0]
                probe = bank.by_id[first["question_id"]]
                target = first["before"]["top_misconception"]
                pattern = next((o for o in probe["options"] if o.get("misconception") and o["misconception"] == target), None)
                if pattern:
                    bucket = by_mis if cause == "misconception" and student["misconception"] == target else by_slip if cause == "slip" else None
                    if bucket is not None:
                        bucket["n"] += 1
                        bucket["k"] += first["selected"] == pattern["id"]
            break  # one diagnosis per student: their first wrong answer

    def of(kind: str) -> list[dict]:
        return [e for e in episodes if e["cause"] == kind]

    predicted = [e for e in episodes if e["verdict"] == "misconception"]
    tp = sum(e["verdict_correct"] for e in predicted)
    decided = [e for e in episodes if e["verdict"] != "inconclusive"]
    slips, miscs = of("slip"), of("misconception")
    overdiagnosed = sum(e["verdict"] == "misconception" for e in slips)
    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(miscs) if miscs else 0.0

    bins, ece = [], 0.0
    for lo, hi in zip(BIN_EDGES, BIN_EDGES[1:]):
        inside = [e for e in episodes if lo <= e["leaning_confidence"] < hi]
        b = {"from": lo, "to": min(1.0, hi), "n": len(inside), "mean_confidence": _mean([e["leaning_confidence"] for e in inside]), "accuracy": _mean([1.0 if e["leaning_correct"] else 0.0 for e in inside])}
        bins.append(b)
        if episodes:
            ece += len(inside) / len(episodes) * abs(b["mean_confidence"] - b["accuracy"])

    confusion = {k: {"misconception": 0, "careless_slip": 0, "gap_in_understanding": 0, "calculation_error": 0, "inconclusive": 0} for k in ("misconception", "slip", "gap")}
    for e in episodes:
        confusion[e["cause"]][e["verdict"]] += 1

    all_steps = [s for e in episodes for s in e["steps"]]
    rate = lambda b: b["k"] / b["n"] if b["n"] else 0.0  # noqa: E731
    return {
        "policy": policy,
        "students": n_students,
        "episodes": len(episodes),
        "misconception_cases": len(miscs),
        "slip_cases": len(slips),
        "gap_cases": len(of("gap")),
        "true_positives": tp,
        "predicted_misconception": len(predicted),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "slips_overdiagnosed": overdiagnosed,
        "slip_false_positive_rate": overdiagnosed / len(slips) if slips else 0.0,
        "decided_rate": len(decided) / len(episodes) if episodes else 0.0,
        "accuracy_when_decided": _mean([1.0 if e["verdict_correct"] else 0.0 for e in decided]),
        "avg_follow_ups": _mean([float(len(e["steps"])) for e in episodes]),
        "avg_gain": _mean([s["gain"] for s in all_steps]),
        "calibration": {"expected_calibration_error": ece, "bins": bins},
        "followup_discrimination": {
            "pattern_repeated_by_misconception_students": rate(by_mis),
            "pattern_repeated_by_slip_students": rate(by_slip),
            "misconception_students": by_mis["n"],
            "slip_students": by_slip["n"],
            "separation": rate(by_mis) - rate(by_slip),
        },
        "confusion": confusion,
    }
