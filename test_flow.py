"""Auth, isolation, the answer → diagnosis → correction flow, and rewards, through the HTTP API."""


def pattern_of(misconception):
    """Answers follow-ups the way a student holding that misconception would."""
    from app.engine.bank import seed_bank

    def respond(f):
        probe = seed_bank().by_id[f["question_id"]]
        hit = next((o for o in probe["options"] if o.get("misconception") == misconception), None)
        return (hit or next(o for o in probe["options"] if o["correct"]))["id"]

    return respond


def correctly(f):
    from app.engine.bank import correct_option, seed_bank

    return correct_option(seed_bank().by_id[f["question_id"]])["id"]


# ───────────────────────── auth and isolation ─────────────────────────


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "database": "connected"}


def test_register_login_me(client, student):
    assert client.post("/api/auth/register", json={"email": student.email, "password": "squeak123"}).json()["error"]["code"] == "EMAIL_TAKEN"
    bad = client.post("/api/auth/login", json={"email": student.email, "password": "wrong"})
    assert bad.status_code == 401 and bad.json() == {"success": False, "error": {"code": "INVALID_CREDENTIALS", "message": bad.json()["error"]["message"]}}
    good = client.post("/api/auth/login", json={"email": student.email.upper(), "password": "squeak123"})
    assert good.status_code == 200 and good.json()["data"]["user"]["email"] == student.email
    assert student.data(student.get("/api/auth/me"))["email"] == student.email


def test_protected_routes_need_a_token(client):
    for path in ("/api/dashboard", "/api/profile", "/api/mistakes", "/api/auth/me", "/api/study-materials"):
        r = client.get(path)
        assert r.status_code == 401 and r.json()["error"]["code"] == "UNAUTHORIZED"
    assert client.get("/api/dashboard", headers={"Authorization": "Bearer nonsense"}).status_code == 401


def test_validation_errors_use_the_envelope(client, student):
    r = client.post("/api/auth/register", json={"email": "nope", "password": "x"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    assert student.post("/api/attempts/evaluate", {"question_id": "does-not-exist", "selected_option": "A"}).json()["error"]["code"] == "QUESTION_NOT_FOUND"
    assert student.post("/api/attempts/evaluate", {"question_id": "f1", "selected_option": "Z"}).json()["error"]["code"] == "INVALID_OPTION"


def test_one_student_cannot_see_anothers_records(student, other):
    sid = student.answer("f1", "A")["diagnostic"]["session_id"]
    student.diagnose(sid, correctly)
    for path in (f"/api/diagnostics/{sid}", f"/api/mistakes/{sid}"):
        r = other.get(path)
        assert r.status_code == 403 and r.json()["error"]["code"] == "FORBIDDEN"
    assert other.post(f"/api/mistakes/{sid}/retry").status_code == 403
    assert other.data(other.get("/api/mistakes"))["mistakes"] == []
    assert other.data(other.get("/api/dashboard"))["stats"]["answered"] == 0


# ───────────────────────── correct answers and rewards ─────────────────────────


def test_question_is_served_without_its_answer(student):
    q = student.data(student.get("/api/questions/next?topic=fractions"))
    assert q["number"] == 1 and q["total"] == 8
    assert all(set(o) == {"id", "text"} for o in q["question"]["options"])


def test_correct_mcq_gives_one_tiara_and_no_diagnosis(student):
    r = student.answer("f1", "B")
    assert r["is_correct"] and r["marks_awarded"] == 1 and r["tiara_awarded"] == 1 and r["new_tiara_count"] == 1 and r["streak_updated"]
    assert r["diagnostic"] is None
    assert any(o["correct"] for o in r["question"]["options"])
    assert student.data(student.get("/api/mistakes"))["mistakes"] == []


def test_repeated_submission_is_not_rewarded_twice(student):
    first = student.answer("f1", "B", client_key="same-click")
    again = student.answer("f1", "B", client_key="same-click")
    assert first["tiara_awarded"] == 1 and again["tiara_awarded"] == 0 and again["duplicate"]
    assert again["attempt_id"] == first["attempt_id"] and again["new_tiara_count"] == 1
    d = student.data(student.get("/api/dashboard"))
    assert d["tiara"]["count"] == 1 and d["stats"]["answered"] == 1 and d["streak"]["current"] == 1


def test_skip_earns_nothing_and_breaks_both_runs(student):
    student.answer("f1", "B")
    r = student.data(student.post("/api/attempts", {"question_id": "f2"}))
    assert r["skipped"]
    d = student.data(student.get("/api/dashboard"))
    assert d["tiara"]["count"] == 1 and d["streak"] == {"current": 0, "longest": 1, "no_skip": 0}
    assert d["stats"]["skipped"] == 1 and d["recent_mistakes"] == []
    # and the folder has moved on past the skipped question
    assert student.data(student.get("/api/questions/next?topic=fractions"))["number"] == 3


def test_wrong_answer_does_not_get_a_tiara_and_resets_the_streak(student):
    student.answer("f1", "B")
    r = student.answer("f2", "A")
    assert not r["is_correct"] and r["tiara_awarded"] == 0 and r["current_streak"] == 0 and r["new_tiara_count"] == 1


def test_badges_and_certificate_unlock_at_their_targets(student):
    student.set(current_streak=9, noskip_count=24, tiara_count=499)
    r = student.answer("f1", "B")
    assert {"kind": "badge", "badge": "streak"} in r["unlocked"] and {"kind": "badge", "badge": "noskip"} in r["unlocked"] and {"kind": "certificate"} in r["unlocked"]
    p = student.data(student.get("/api/profile"))
    assert p["certificate"]["status"] == "certificate_unlocked" and p["certificate"]["share_token"] and p["tiara"] == 500
    assert {b["id"]: b["unlocked"] for b in p["badges"]} == {"streak": True, "noskip": True, "mistakes": False}
    # nothing is granted a second time
    assert student.answer("f2", "C")["unlocked"] == []


def test_certificate_stays_locked_below_500(student):
    student.set(tiara_count=498)
    student.answer("f1", "B")
    c = student.data(student.get("/api/profile"))["certificate"]
    assert c["status"] == "certificate_locked" and c["to_go"] == 1


# ───────────────────────── wrong answers: the diagnosis ─────────────────────────


def test_wrong_answer_opens_an_investigation_not_a_verdict(student):
    r = student.answer("f1", "A")
    d = r["diagnostic"]
    assert d["status"] == "FOLLOWUP_REQUIRED" and d["diagnosis"] is None and d["followup"]["required"]
    assert d["selected"] == {"id": "A", "text": "2/6"}
    # competing hypotheses, none above the threshold
    assert {h["kind"] for h in d["hypotheses"]} == {"MISCONCEPTION", "CARELESS_SLIP", "GAP_IN_UNDERSTANDING", "CALCULATION_ERROR"}
    assert all(h["confidence"] <= 70 for h in d["hypotheses"])
    # the answer key is not revealed while the follow-up is still a fair test
    assert all("correct" not in o for o in d["question"]["options"])
    assert student.data(student.get("/api/mistakes"))["mistakes"] == []


def test_follow_up_is_chosen_for_a_stated_reason_and_is_stable(student):
    sid = student.answer("f1", "A")["diagnostic"]["session_id"]
    f = student.data(student.post(f"/api/diagnostics/{sid}/followup"))
    assert f["purpose"].startswith("Chosen because the two explanations expect different answers") and f["gain"] > 0.3
    assert f["hypothesis_a"] == "Misconception: Adding across" and f["hypothesis_b"] == "Careless slip"
    assert len(f["options"]) == 4 and f["source"] == "bank"
    assert student.data(student.post(f"/api/diagnostics/{sid}/followup"))["followup_id"] == f["followup_id"]


def test_evaluating_without_a_follow_up_is_refused(student):
    sid = student.answer("f1", "A")["diagnostic"]["session_id"]
    assert student.post(f"/api/diagnostics/{sid}/evaluate-followup", {"answer": "A"}).json()["error"]["code"] == "FOLLOWUP_NOT_REQUESTED"


def test_misconception_is_confirmed_only_after_the_follow_up(student):
    start = student.answer("f1", "A")["diagnostic"]
    view = student.diagnose(start["session_id"], pattern_of("F_ADD_ACROSS"))
    dx = view["diagnosis"]
    assert dx["primary"] == "MISCONCEPTION" and dx["status"] == "SUPPORTED" and dx["confidence"] > 70
    assert dx["misconception"]["id"] == "F_ADD_ACROSS" and dx["band"] in ("Supported", "Strongly supported")
    assert view["summary"]["misconception"] > start["summary"]["misconception"]  # confidence moved with the evidence
    assert any("same pattern appeared again" in e for e in view["evidence"])
    assert view["feedback"] and not view["corrected"]
    m = student.data(student.get("/api/mistakes"))["mistakes"][0]
    assert m["status"] == "MISCONCEPTION_IDENTIFIED" and m["selected"]["text"] == "2/6" and m["followup_question"] and m["retry_status"] == "NOT_ATTEMPTED"
    assert student.data(student.get("/api/dashboard"))["stats"]["mistakes_corrected"] == 0


def test_careless_slip_is_not_called_a_misconception(student):
    view = student.diagnose(student.answer("f1", "A")["diagnostic"]["session_id"], correctly)
    assert view["diagnosis"]["primary"] == "CARELESS_SLIP" and view["diagnosis"]["confidence"] > 70 and view["diagnosis"]["misconception"] is None
    assert view["mistake_status"] == "SLIP_IDENTIFIED" and view["corrected"]


def test_calculation_error_and_misinterpretation_are_told_apart_by_the_students_words(student):
    a = student.answer("f1", "D", reasoning="I calculated it wrong in my head")["diagnostic"]
    assert a["reasoning_evidence"][0]["hypothesis"] == "calculation"
    assert student.diagnose(a["session_id"], correctly)["diagnosis"]["primary"] == "CALCULATION_ERROR"

    b = student.answer("f2", "A")["diagnostic"]
    with_words = student.data(student.post(f"/api/diagnostics/{b['session_id']}/reasoning", {"reasoning": "I misread the question, I thought it asked for the smaller one"}))
    assert with_words["summary"]["slip"] > b["summary"]["slip"]
    # a misreading is a careless slip, and the message says it was misread
    misread = student.diagnose(b["session_id"], correctly)
    assert misread["diagnosis"]["primary"] == "CARELESS_SLIP" and "misread" in misread["feedback"]


def test_unclear_evidence_is_reported_as_uncertain(student):
    """A student who is simply lost gives answers that fit no pattern: no label is forced."""
    from app.engine.bank import seed_bank

    def lost(f):
        probe = seed_bank().by_id[f["question_id"]]
        return next(o for o in probe["options"] if not o["correct"] and not o.get("misconception"))["id"]

    view = student.diagnose(student.answer("f5", "B")["diagnostic"]["session_id"], lost)
    dx = view["diagnosis"]
    assert dx["primary"] != "MISCONCEPTION"
    assert (dx["status"] == "UNCERTAIN" and dx["primary"] is None) or dx["primary"] == "GAP_IN_UNDERSTANDING"


def test_a_closed_diagnosis_cannot_be_reopened(student):
    sid = student.answer("f1", "A")["diagnostic"]["session_id"]
    student.diagnose(sid, correctly)
    assert student.post(f"/api/diagnostics/{sid}/followup").json()["error"]["code"] == "DIAGNOSTIC_CLOSED"


# ───────────────────────── correction ─────────────────────────


def _misconception_mistake(student):
    sid = student.answer("f1", "A")["diagnostic"]["session_id"]
    student.diagnose(sid, pattern_of("F_ADD_ACROSS"))
    return sid


def test_mistake_is_corrected_only_by_a_passed_retest(student):
    sid = _misconception_mistake(student)
    step = student.data(student.post(f"/api/mistakes/{sid}/retry"))
    assert step["help"]["kind"] == "targeted" and step["help"]["misconception"]["name"] == "Adding across" and len(step["help"]["misconception"]["explanation"]) >= 2
    assert all(set(o) == {"id", "text"} for o in step["question"]["options"])

    # getting the retest wrong the same way does not count
    wrong = pattern_of("F_ADD_ACROSS")({"question_id": step["question"]["id"]})
    r = student.data(student.post(f"/api/mistakes/{sid}/retry/evaluate", {"question_id": step["question"]["id"], "selected_option": wrong}))
    assert not r["corrected"] and r["understanding"] <= 70 and r["mistake_status"] == "MISCONCEPTION_IDENTIFIED" and r["can_retry_again"]
    assert student.data(student.get("/api/dashboard"))["stats"]["mistakes_corrected"] == 0

    step = student.data(student.post(f"/api/mistakes/{sid}/retry"))
    right = correctly({"question_id": step["question"]["id"]})
    r = student.data(student.post(f"/api/mistakes/{sid}/retry/evaluate", {"question_id": step["question"]["id"], "selected_option": right}))
    assert r["corrected"] and r["understanding"] > 70 and r["mistake_status"] == "CORRECTED"
    m = student.data(student.get(f"/api/mistakes/{sid}"))
    assert m["status"] == "CORRECTED" and m["what_was_learned"] and m["retry_status"] == "PASSED"
    assert student.data(student.get("/api/dashboard"))["stats"]["mistakes_corrected"] == 1


def test_fiftieth_corrected_mistake_unlocks_mistake_master_once(student):
    student.set(mistakes_corrected=49)
    sid = _misconception_mistake(student)
    step = student.data(student.post(f"/api/mistakes/{sid}/retry"))
    body = {"question_id": step["question"]["id"], "selected_option": correctly({"question_id": step["question"]["id"]})}
    r = student.data(student.post(f"/api/mistakes/{sid}/retry/evaluate", body))
    assert {"kind": "badge", "badge": "mistakes"} in r["unlocked"]
    # practising it again later does not count as a second correction
    step = student.data(student.post(f"/api/mistakes/{sid}/retry"))
    student.post(f"/api/mistakes/{sid}/retry/evaluate", {"question_id": step["question"]["id"], "selected_option": correctly({"question_id": step["question"]["id"]})})
    assert student.data(student.get("/api/dashboard"))["stats"]["mistakes_corrected"] == 50


# ───────────────────────── personalisation, dashboard, evaluation lab ─────────────────────────


def test_past_mistakes_drive_the_recommendations(student):
    before = student.data(student.get("/api/learning/recommendations"))
    assert before["weak_areas"] == []
    _misconception_mistake(student)
    after = student.data(student.get("/api/learning/recommendations"))
    assert after["weak_areas"][0]["id"] == "F_ADD_ACROSS" and after["weak_areas"][0]["open_mistakes"] == 1
    assert after["recommended_topics"][0]["id"] == "fractions" and "Adding across" in after["reason"]
    assert after["recommended_questions"] and all(q["question_id"] != "f1" for q in after["recommended_questions"])
    assert student.data(student.get("/api/mistakes"))["retry_order"]


def test_dashboard_and_demo_history(student):
    student.data(student.post("/api/demo", {"action": "load"}))
    d = student.data(student.get("/api/dashboard"))
    assert d["tiara"] == {"count": 342, "target": 500, "to_go": 158, "rule": "1 correct question = 1 Tiara"}
    assert d["stats"]["answered"] == 421 and d["streak"]["longest"] == 14
    assert len(d["recent_mistakes"]) == 4 and d["recent_activity"] and len(d["progress"]["topics"]) == 2
    statuses = {m["status"] for m in student.data(student.get("/api/mistakes"))["mistakes"]}
    assert {"SLIP_IDENTIFIED", "CORRECTED", "MISCONCEPTION_IDENTIFIED"} <= statuses
    assert student.data(student.post("/api/demo", {"action": "add_tiara", "amount": 200}))["unlocked"] == [{"kind": "certificate"}]
    student.data(student.post("/api/demo", {"action": "reset"}))
    assert student.data(student.get("/api/dashboard"))["tiara"]["count"] == 0


def test_profile_can_be_customised(student):
    p = student.data(student.client.patch("/api/profile", headers=student.headers, json={"name": "Kruthika", "avatar": "royal"}))
    assert p["user"]["name"] == "Kruthika" and p["user"]["avatar"] == "royal"
    assert student.client.patch("/api/profile", headers=student.headers, json={"avatar": "dragon"}).status_code == 422


def test_evaluation_lab(student):
    assert student.data(student.get("/api/evaluation/results")) is None
    r = student.data(student.post("/api/evaluation/run", {"students": 300, "seed": 7}))
    assert 0.8 < r["precision"] <= 1 and 0.75 < r["recall"] <= 1 and 0 <= r["slip_false_positive_rate"] < 0.1 and 0.8 < r["f1"] <= 1
    assert r["calibration"]["bins"] and r["followup_discrimination"]["separation"] > 0.5
    assert [p["policy"] for p in r["policies"]] == ["targeted", "random", "none"]
    cases = {c["name"]: c for c in r["cases"]}
    assert [cases[f"Student {x}"]["diagnosis"] for x in "ABCDE"] == ["MISCONCEPTION", "CARELESS_SLIP", "CALCULATION_ERROR", "CARELESS_SLIP", None]
    assert all(c["outcome_correct"] for c in r["cases"]) and all(c["confidence"] > 70 for c in r["cases"])
    assert student.data(student.get("/api/evaluation/results"))["id"] == r["id"]
    other_seed = student.data(student.post("/api/evaluation/run", {"students": 300, "seed": 11}))
    assert (other_seed["precision"], other_seed["recall"]) != (r["precision"], r["recall"])


# ───────────────────────── after a wrong answer: the correct answer, explained ─────────────────────────


def test_wrong_answer_is_followed_by_the_correct_answer_and_an_explanation(student):
    r = student.answer("f1", "A")
    sid = r["diagnostic"]["session_id"]
    first = student.data(student.post(f"/api/diagnostics/{sid}/explain", {"level": 0}))
    assert first["correct_answer"] == {"id": "B", "text": "3/4"} and "3/4" in first["explanation"] and not first["simpler"]
    # it teaches the answer; it does not talk about the student's own choice
    assert "2/6" not in first["explanation"] and "you chose" not in first["explanation"].lower()
    again = student.data(student.post(f"/api/diagnostics/{sid}/explain", {"level": 1}))
    assert again["simpler"] and again["explanation"] != first["explanation"] and "For example" in again["explanation"]
    # the same explanation is available by attempt, for any question type
    assert student.data(student.post(f"/api/attempts/{r['attempt_id']}/explain", {"level": 0}))["correct_answer"]["text"] == "3/4"


def test_understood_leads_to_a_follow_up_on_the_same_idea_which_can_then_be_explained(student):
    sid = student.answer("f1", "A")["diagnostic"]["session_id"]
    f = student.data(student.post(f"/api/diagnostics/{sid}/followup"))
    assert f["question_id"] != "f1"
    # a question that has not been answered yet cannot be explained (that would give the answer away)
    assert student.post(f"/api/diagnostics/{sid}/explain", {"question_id": f["question_id"]}).json()["error"]["code"] == "INVALID_QUESTION"
    view = student.data(student.post(f"/api/diagnostics/{sid}/evaluate-followup", {"answer": pattern_of("F_ADD_ACROSS")(f)}))
    step = view["steps"][-1]
    assert not step["is_correct"] and any(o["correct"] for o in step["question"]["options"]) and step["question"]["solution"]
    assert student.data(student.post(f"/api/diagnostics/{sid}/explain", {"question_id": f["question_id"]}))["explanation"]


def test_explanations_belong_to_their_owner(student, other):
    r = student.answer("f1", "A")
    assert other.post(f"/api/diagnostics/{r['diagnostic']['session_id']}/explain", {}).status_code == 403
    assert other.post(f"/api/attempts/{r['attempt_id']}/explain", {}).json()["error"]["code"] == "ATTEMPT_NOT_FOUND"


def test_explain_again_uses_groq_for_a_simpler_version(student, fake_ai):
    from tests.conftest import chat

    seen = []

    def reply(prompt):
        seen.append(prompt)
        return chat({"explanation": "Think of a pizza cut into quarters: two quarters and one more quarter make three quarters."})

    fake_ai["replies"]["Explain the correct answer to them"] = reply
    fake_ai["replies"]["explained their thinking"] = chat({"signals": []})
    sid = student.answer("f1", "A")["diagnostic"]["session_id"]
    out = student.data(student.post(f"/api/diagnostics/{sid}/explain", {"level": 1}))
    assert out["source"] == "groq" and "pizza" in out["explanation"]
    assert "analogy or real-life example" in seen[0] and "Do NOT discuss the student's own answer" in seen[0]


def test_mistake_type_is_shown_with_the_first_explanation_only_for_the_original_answer(student):
    r = student.answer("f1", "A")  # the option a misconception produces
    sid = r["diagnostic"]["session_id"]
    e = student.data(student.post(f"/api/diagnostics/{sid}/explain", {"level": 0}))
    assert e["mistake_type"]["kind"] == "MISCONCEPTION" and e["mistake_type"]["label"] == "Misconception" and e["mistake_type"]["message"].startswith("Looks like this was a")
    slip = student.answer("f2", "B")  # a wrong option that matches no misconception
    kind = student.data(student.post(f"/api/attempts/{slip['attempt_id']}/explain", {}))["mistake_type"]["kind"]
    assert kind in ("CARELESS_SLIP", "GAP_IN_UNDERSTANDING", "CALCULATION_ERROR")
    # a follow-up question's explanation carries no label: that belongs to the original answer
    f = student.data(student.post(f"/api/diagnostics/{sid}/followup"))
    student.post(f"/api/diagnostics/{sid}/evaluate-followup", {"answer": pattern_of("F_ADD_ACROSS")(f)})
    assert student.data(student.post(f"/api/diagnostics/{sid}/explain", {"question_id": f["question_id"]}))["mistake_type"] is None
    # a correct answer has no mistake type
    ok_ = student.answer("f3", "A")
    assert student.data(student.post(f"/api/attempts/{ok_['attempt_id']}/explain", {}))["mistake_type"] is None
