"""The diagnostic engine on its own: no database, no API."""
import pytest

from app.engine import bayes
from app.engine.bank import correct_option, seed_bank
from app.engine.simulation import simulate

bank = seed_bank()
f1 = bank.by_id["f1"]
prior = bank.prior("fractions")


def test_bank_is_small_and_mapped():
    main = [q for q in bank.questions if q["role"] == "main"]
    assert 10 <= len(main) <= 20
    assert {q["topic"] for q in bank.questions} == {"fractions", "algebra"}
    # every misconception has at least one wrong option that it explains
    for m in bank.misconceptions:
        assert any(o.get("misconception") == m["id"] for q in bank.questions for o in q["options"]), m["id"]


@pytest.mark.parametrize("hyp", ["understands", "unknown", "F_ADD_ACROSS", "F_DIV_NO_FLIP"])
def test_likelihood_is_a_distribution(hyp):
    for q in bank.questions:
        assert sum(bayes.likelihood(q, o["id"], hyp) for o in q["options"]) == pytest.approx(1)


def test_one_wrong_answer_is_not_a_diagnosis():
    """Wrong answer ≠ misconception: the misconception-shaped option alone stays below the threshold."""
    after = bayes.summarize(bayes.update(prior, f1, "A"))
    assert bayes.verdict_of(after)["kind"] == "inconclusive"
    assert after["misconception"] < 0.7 and after["slip"] < 0.7


def test_threshold_is_strictly_greater_than_70():
    assert bayes.verdict_of({"misconception": 0.70, "slip": 0.25, "unexplained": 0.05, "top_misconception": "X"})["kind"] == "inconclusive"
    assert bayes.verdict_of({"misconception": 0.701, "slip": 0.25, "unexplained": 0.049, "top_misconception": "X"})["kind"] == "misconception"
    # 50% is nowhere near enough
    assert bayes.verdict_of({"misconception": 0.55, "slip": 0.40, "unexplained": 0.05, "top_misconception": "X"})["kind"] == "inconclusive"


def _run(answer):
    belief = bayes.update(prior, f1, "A")
    probe, gain = bayes.select_follow_up(belief, bank.probes("fractions"), ["f1"])
    return probe, gain, bayes.summarize(bayes.update(belief, probe, answer(probe)))


def test_follow_up_discriminates_and_confirms_a_misconception():
    probe, gain, after = _run(lambda p: next(o for o in p["options"] if o.get("misconception") == "F_ADD_ACROSS")["id"])
    assert probe["targets"] == "F_ADD_ACROSS" and gain > 0.3
    # the two explanations predict different answers to it
    assert bayes.predict(probe, "F_ADD_ACROSS")["option_id"] != bayes.predict(probe, "understands")["option_id"]
    assert bayes.verdict_of(after) == {"kind": "misconception", "confidence": pytest.approx(after["misconception"]), "misconception": "F_ADD_ACROSS"}


def test_follow_up_clears_a_careless_slip():
    _, _, after = _run(lambda p: correct_option(p)["id"])
    assert bayes.verdict_of(after)["kind"] == "careless_slip"
    assert after["misconception"] < 0.3


def test_reasoning_is_light_evidence_and_names_the_slip():
    ms = bank.misconceptions_for("fractions")
    ev, kind = bayes.analyze_reasoning("I misread the question", ms)
    assert kind == "MISINTERPRETATION" and ev[0]["hyp"] == "understands"
    assert bayes.analyze_reasoning("I calculated it wrong", ms)[1] == "CALCULATION_ERROR"
    ev, _ = bayes.analyze_reasoning("I added the tops and then added the bottoms", ms)
    assert ev[0]["hyp"] == "F_ADD_ACROSS"
    # words alone never push a hypothesis over the line
    nudged = bayes.summarize(bayes.apply_reasoning(bayes.update(prior, f1, "A"), ev))
    assert bayes.verdict_of(nudged)["kind"] in ("inconclusive", "misconception") and nudged["misconception"] < 0.9


def test_retry_understanding():
    probe = next(p for p in bank.probes("fractions") if p["targets"] == "F_ADD_ACROSS")
    right = bayes.understanding_after_retry([(probe, correct_option(probe)["id"])], "F_ADD_ACROSS")
    wrong = bayes.understanding_after_retry([(probe, next(o for o in probe["options"] if o.get("misconception") == "F_ADD_ACROSS")["id"])], "F_ADD_ACROSS")
    assert right > 0.7 > wrong


def test_simulation_metrics_are_computed_not_fixed():
    a, b = simulate(bank, 300, 7, "targeted"), simulate(bank, 300, 8, "targeted")
    assert a["precision"] != b["precision"] or a["recall"] != b["recall"]
    assert a["precision"] > 0.8 and a["recall"] > 0.75
    assert a["slip_false_positive_rate"] < 0.1
    assert a["f1"] == pytest.approx(2 * a["precision"] * a["recall"] / (a["precision"] + a["recall"]))
    assert a["calibration"]["expected_calibration_error"] < 0.1
    d = a["followup_discrimination"]
    assert d["pattern_repeated_by_misconception_students"] > d["pattern_repeated_by_slip_students"] + 0.5
    # the targeted follow-up is what earns the result
    none = simulate(bank, 300, 7, "none")
    assert none["recall"] < a["recall"] and none["decided_rate"] < a["decided_rate"]


# ───────────────────────── the four categories ─────────────────────────


def _investigate(first: str, respond):
    """One wrong answer to f1, then up to three follow-ups chosen by the engine and answered by `respond`."""
    belief, used = bayes.update(prior, f1, first), ["f1"]
    for _ in range(bayes.MAX_FOLLOW_UPS):
        if len(used) > 1 and bayes.verdict_of(bayes.summarize(belief))["kind"] != "inconclusive":
            break
        probe, _ = bayes.select_follow_up(belief, bank.probes("fractions"), used)
        used.append(probe["id"])
        belief = bayes.update(belief, probe, respond(probe))
    return bayes.verdict_of(bayes.summarize(belief))


def near_miss(q):
    """Shaky arithmetic: the likeliest slip on a question with a sum to do, never the faulty rule's answer."""
    slips = [o for o in q["options"] if not o["correct"] and not o.get("misconception")]
    return max(slips, key=lambda o: o["slip_weight"])["id"] if bayes.computational(q) and slips else correct_option(q)["id"]


def test_every_category_has_a_prior_and_the_prior_is_a_distribution():
    assert {"understands", "unknown", "calculation"} <= set(prior) and abs(sum(prior.values()) - 1) < 1e-9
    assert bayes.CATEGORIES == {"misconception": "MISCONCEPTION", "careless_slip": "CARELESS_SLIP", "gap_in_understanding": "GAP_IN_UNDERSTANDING", "calculation_error": "CALCULATION_ERROR"}
    for q in bank.questions:
        for h in prior:
            assert abs(sum(bayes.likelihood(q, o["id"], h) for o in q["options"]) - 1) < 1e-9, (q["id"], h)


def test_repeated_arithmetic_near_misses_are_a_calculation_error():
    first = near_miss(f1)
    assert first == "D"  # 2/4: the right method, a wrong sum
    v = _investigate(first, near_miss)
    assert v["kind"] == "calculation_error" and v["confidence"] > 0.7


def test_answers_that_fit_no_pattern_are_a_gap_in_understanding():
    def lost(q):
        # wrong, but never the near miss and never the faulty rule's answer: no method behind it
        wrong = [o for o in q["options"] if not o["correct"] and not o.get("misconception")]
        return min(wrong, key=lambda o: o["slip_weight"])["id"] if wrong else correct_option(q)["id"]

    v = _investigate("C", lost)
    assert v["kind"] == "gap_in_understanding" and v["confidence"] > 0.7


def test_a_calculation_error_does_not_count_against_understanding_the_concept():
    belief = bayes.update(prior, f1, "D")
    assert bayes.understanding(belief) == pytest.approx(belief["understands"] + belief["calculation"])
    # a misconception's answer is not something an arithmetic slip produces
    assert bayes.likelihood(f1, "A", "calculation") < 0.01 < bayes.likelihood(f1, "D", "calculation")


def test_old_stored_names_still_read_as_the_new_categories():
    assert bayes.canonical_kind("slip") == "careless_slip" and bayes.canonical_kind("unknown") == "gap_in_understanding"
    assert bayes.canonical_kind("calculation_error") == "calculation_error" and bayes.canonical_kind(None) == "inconclusive"
    # beliefs saved before the calculation hypothesis existed gain it when they are carried over
    old = {k: v for k, v in prior.items() if k != "calculation"}
    assert "calculation" in bayes.carry_over(old, prior)
