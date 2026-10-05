"""Password reset by email, the folder hierarchy with confidence and weakness, recurring mistakes, and the notes generator."""
import re

import pytest

from app.core.config import get_settings
from app.engine.bank import seed_bank
from app.services import email_service
from tests.conftest import chat
from tests.test_materials_and_ai import NOTES, ONE_WORD, generate

BLANK_JUDGE = chat({"classification": "misconception", "feedback": "Not this one.", "confidence": 80})


def put(student, name="notes.txt", data=NOTES[1], mime="text/plain", **form):
    r = student.client.post("/api/study-materials/upload", headers=student.headers, files={"file": (name, data, mime)}, data=form)
    return student.data(r)


def tree(student):
    return student.data(student.get("/api/folders"))


def folder(student, name):
    return next(f for f in tree(student)["folders"] if f["name"] == name)


# ───────────────────────── forgot password ─────────────────────────


@pytest.fixture
def outbox(monkeypatch):
    s = get_settings()
    for k, v in {"smtp_host": "smtp.test", "smtp_user": "hamstar@test.dev", "smtp_password": "app-password"}.items():
        monkeypatch.setattr(s, k, v)
    sent = []
    monkeypatch.setattr(email_service, "send", lambda to, subject, text, html=None: sent.append({"to": to, "subject": subject, "text": text, "html": html}))
    return sent


def test_reset_needs_email_to_be_configured(student):
    r = student.client.post("/api/auth/forgot-password", json={"email": student.email})
    assert r.status_code == 503 and r.json()["error"]["code"] == "EMAIL_NOT_CONFIGURED"


def test_forgot_password_emails_a_code_that_sets_a_new_password_once(student, outbox):
    c = student.client
    # an unknown Study ID gets the same reply, and no email
    unknown = c.post("/api/auth/forgot-password", json={"email": "nobody@test.dev"}).json()
    known = c.post("/api/auth/forgot-password", json={"email": f"  {student.email.upper()} "}).json()
    assert unknown == known and known["data"]["sent"] and len(outbox) == 1
    mail = outbox[0]
    code = re.search(r"\b(\d{6})\b", mail["text"]).group(1)
    assert mail["to"] == student.email and code in mail["html"] and f"#/login?reset={student.email}&code={code}" in mail["text"]
    # asking again straight away does not send a second email
    c.post("/api/auth/forgot-password", json={"email": student.email})
    assert len(outbox) == 1

    wrong = "000000" if code != "000000" else "111111"
    bad = c.post("/api/auth/reset-password", json={"email": student.email, "code": wrong, "password": "new-squeak-1"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "INVALID_RESET_CODE"
    assert c.post("/api/auth/reset-password", json={"email": student.email, "code": code, "password": "short"}).status_code == 422

    done = c.post("/api/auth/reset-password", json={"email": student.email, "code": f" {code[:3]} {code[3:]} ", "password": "new-squeak-1"})
    assert done.status_code == 200 and done.json()["data"]["token"]
    assert c.post("/api/auth/login", json={"email": student.email, "password": "squeak123"}).status_code == 401
    assert c.post("/api/auth/login", json={"email": student.email, "password": "new-squeak-1"}).status_code == 200
    # the code is spent
    assert c.post("/api/auth/reset-password", json={"email": student.email, "code": code, "password": "another-one"}).status_code == 400


def test_too_many_wrong_codes_spend_the_reset(student, outbox):
    c = student.client
    c.post("/api/auth/forgot-password", json={"email": student.email})
    code = re.search(r"\b(\d{6})\b", outbox[0]["text"]).group(1)
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        assert c.post("/api/auth/reset-password", json={"email": student.email, "code": wrong, "password": "new-squeak-1"}).status_code == 400
    assert c.post("/api/auth/reset-password", json={"email": student.email, "code": code, "password": "new-squeak-1"}).status_code == 400


# ───────────────────────── parent folders and subfolders ─────────────────────────


def test_starter_folders_sit_under_maths(student):
    t = tree(student)
    maths = next(f for f in t["folders"] if f["name"] == "Maths")
    assert sorted(s["name"] for s in maths["subfolders"]) == ["Algebra", "Fractions"]
    doc = maths["subfolders"][0]["documents"][0]
    assert doc["kind"] == "starter" and doc["confidence"] > 0 and doc["answered"] == 0 and not doc["weak"]
    # the same number the dashboard has always shown for an account with no answers
    d = student.data(student.get("/api/dashboard"))
    assert d["folders"]["total_confidence"] == d["progress"]["total_confidence"]
    assert {"Maths", "Science", "Computer Science"} <= {s["name"] for s in t["suggestions"]}


def test_uploads_are_filed_under_parent_and_subfolder(student):
    physics = put(student, subject="Physics")
    assert physics["parent"] == "Science" and physics["subject"] == "Physics" and physics["subject_detected"]
    again = put(student, name="more.txt", subject="physics ")
    # several documents share one subfolder
    science = folder(student, "Science")
    sub = next(s for s in science["subfolders"] if s["name"].lower() == "physics")
    assert sub["document_count"] >= 1 and science["document_count"] == 2 and again["parent"] == "Science"

    oop = put(student, name="oop.txt", data=b"Object-oriented programming: a class is a blueprint, inheritance lets a subclass extend it, and polymorphism lets one interface have many forms.")
    assert oop["parent"] == "Computer Science" and oop["subject"] == "Object-Oriented Programming"
    # a parent the student makes up, with a subfolder of their own
    own = put(student, name="x.txt", subject="Carnatic Ragas", parent="Music")
    assert own["parent"] == "Music" and folder(student, "Music")["subfolders"][0]["name"] == "Carnatic Ragas"


def test_broad_subject_names_only_the_parent_and_the_student_picks_the_subfolder(student):
    m = put(student, name="x.txt", data=b"Some thoughts with nothing in particular to say about any subject at all.", subject="Mathematics")
    assert m["parent"] == "Maths" and not m["subject_detected"] and m["subject"] == "General"
    moved = student.data(student.client.patch(f"/api/study-materials/{m['id']}", headers=student.headers, json={"subject": "Calculus"}))
    assert moved["parent"] == "Maths" and moved["subject"] == "Calculus" and moved["subject_detected"]
    assert "Calculus" in [s["name"] for s in folder(student, "Maths")["subfolders"]]
    moved = student.data(student.client.patch(f"/api/study-materials/{m['id']}", headers=student.headers, json={"subject": "Thermodynamics", "parent": "science"}))
    assert moved["parent"] == "Science"


def test_undetected_document_waits_in_other_general(student):
    m = put(student, name="x.txt", data=b"Some thoughts with nothing in particular to say about any subject at all.")
    assert not m["subject_detected"] and m["parent"] == "Other"
    assert folder(student, "Other")["subfolders"][0]["name"] == "General"


# ───────────────────────── confidence for every folder ─────────────────────────


def test_every_document_and_folder_has_a_confidence_that_moves_with_each_answer(student, fake_ai):
    fake_ai["replies"]["filled in a blank"] = BLANK_JUDGE
    m = put(student, subject="Biology")
    second = {**ONE_WORD, "question": "Which gas do plants take in?", "expected_answer": "carbon dioxide", "accepted_answers": ["co2"]}
    fake_ai["replies"]["You write exam questions"] = chat({"questions": [ONE_WORD, second]})
    qs = student.data(generate(student, m["id"], "ONE_WORD", 1, n=2))["questions"]

    def doc():
        return folder(student, "Science")["subfolders"][0]["documents"][0]

    start = doc()
    assert start["confidence"] == 50 and start["score"] is None and start["question_count"] == 2
    student.post("/api/attempts/evaluate", {"question_id": qs[0]["id"], "answer": "chlorophyll"})
    up = doc()
    assert up["confidence"] > 50 and up["score"] == 100 and up["answered"] == 1 and up["correct"] == 1
    student.post("/api/attempts/evaluate", {"question_id": qs[1]["id"], "answer": "oxygen"})
    down = doc()
    assert down["confidence"] < up["confidence"] and down["score"] == 50
    science = folder(student, "Science")
    assert science["confidence"] == science["subfolders"][0]["confidence"] == down["confidence"]


def test_detailed_answers_weigh_more_than_one_mark_answers():
    from app.services.folder_service import _confidence, TYPE_WEIGHT

    assert TYPE_WEIGHT["LONG_ANSWER"] > TYPE_WEIGHT["SHORT_ANSWER"] > TYPE_WEIGHT["MCQ"] == TYPE_WEIGHT["ONE_WORD"]
    # one detailed answer right moves confidence further than one one-mark answer right
    assert _confidence(TYPE_WEIGHT["LONG_ANSWER"], TYPE_WEIGHT["LONG_ANSWER"]) > _confidence(1, 1) > 50


# ───────────────────────── recurring mistakes ─────────────────────────


def adding_across():
    """Fractions questions with an option that comes from adding across, and that option."""
    out = []
    for q in seed_bank().questions:
        o = next((o for o in q["options"] if o.get("misconception") == "F_ADD_ACROSS"), None)
        if o and q["role"] == "main":
            out.append((q, o["id"]))
    return out


def test_the_same_concept_going_wrong_twice_is_flagged_and_drilled_until_fixed(student):
    (q1, o1), (q2, o2) = adding_across()[:2]
    first = student.answer(q1["id"], o1)
    assert first["recurring"] is None
    assert student.data(student.get("/api/recurring-mistakes")) == {"recurring": [], "patterns": [], "logged": 1}

    second = student.answer(q2["id"], o2)
    assert second["recurring"]["count"] == 2 and second["recurring"]["message"] == "You keep making this mistake in Adding across — let's fix this!"
    s = student.data(student.get("/api/recurring-mistakes"))
    r = s["recurring"][0]
    assert r["concept"] == "Adding across" and r["count"] == 2 and r["folder"] == "Fractions" and r["parent"] == "Maths" and r["documents"] == ["fractions"]
    assert r["mistake_type"]["kind"] == "MISCONCEPTION" and s["patterns"][0] == {"kind": "MISCONCEPTION", "label": "Misconception", "about": "The idea itself needs another look.", "count": 2}
    assert student.data(student.get("/api/dashboard"))["recurring"]["recurring"][0]["concept"] == "Adding across"

    drill = student.data(student.get("/api/practice?concept=adding%20across"))
    assert drill["kind"] == "concept" and drill["title"] == "Adding across" and 2 <= len(drill["questions"]) <= 5
    assert all("correct" not in o for q in drill["questions"] for o in q["options"])
    # drill answers count, but the folder stays where the student left it
    position = student.data(student.get("/api/questions/next?topic=fractions"))["number"]
    bank = seed_bank().by_id
    for q in drill["questions"][:2]:
        right = next(o["id"] for o in bank[q["id"]]["options"] if o["correct"])
        assert student.answer(q["id"], right, practice=True)["is_correct"]
    assert student.data(student.get("/api/questions/next?topic=fractions"))["number"] == position
    # two correct answers on the concept put it right
    assert student.data(student.get("/api/recurring-mistakes"))["recurring"] == []


def test_drill_needs_a_logged_concept_and_practice_needs_a_target(student, other):
    assert student.get("/api/practice?concept=nothing").json()["error"]["code"] == "NOTHING_TO_DRILL"
    assert student.get("/api/practice").json()["error"]["code"] == "INVALID_PRACTICE"
    m = put(student, subject="Biology")
    assert other.get(f"/api/practice?document=material:{m['id']}").json()["error"]["code"] == "STUDY_MATERIAL_NOT_FOUND"


def test_mistakes_in_uploaded_documents_are_logged_by_their_concept(student, fake_ai):
    fake_ai["replies"]["filled in a blank"] = BLANK_JUDGE
    m = put(student, subject="Biology")
    a = {**ONE_WORD, "topic": "Chlorophyll"}
    b = {**ONE_WORD, "question": "What colour is chlorophyll?", "expected_answer": "green", "accepted_answers": [], "topic": "chlorophyll"}
    fake_ai["replies"]["You write exam questions"] = chat({"questions": [a, b]})
    qs = student.data(generate(student, m["id"], "ONE_WORD", 1, n=2))["questions"]
    student.post("/api/attempts/evaluate", {"question_id": qs[0]["id"], "answer": "water"})
    r = student.data(student.post("/api/attempts/evaluate", {"question_id": qs[1]["id"], "answer": "blue"}))
    assert r["recurring"]["concept"].lower() == "chlorophyll" and r["recurring"]["count"] == 2
    rec = student.data(student.get("/api/recurring-mistakes"))["recurring"][0]
    assert rec["folder"] == "Biology" and rec["parent"] == "Science" and rec["documents"] == [f"material:{m['id']}"]
    # the kind of mistake is refined when the answer is explained, and the log follows
    fake_ai["replies"]["Decide which ONE kind of mistake"] = chat({"mistake_type": "careless slip", "reason": "A slip."})
    fake_ai["replies"]["Explain the correct answer to them"] = chat({"key_terms": ["green"], "core_concepts": ["Chlorophyll is green."], "explanation": "Chlorophyll reflects green light, so it looks green.", "remember": "Chloro means green."})
    student.post(f"/api/attempts/{r['attempt_id']}/explain", {"level": 0})
    assert student.data(student.get("/api/recurring-mistakes"))["recurring"][0]["mistake_types"] == {"MISCONCEPTION": 1, "CARELESS_SLIP": 1}


# ───────────────────────── weakness by folder and document ─────────────────────────


def test_weak_documents_are_flagged_sorted_first_and_practised_on_their_own(student, fake_ai):
    fake_ai["replies"]["filled in a blank"] = BLANK_JUDGE
    weak = put(student, name="weak.txt", subject="Biology")
    strong = put(student, name="strong.txt", subject="Biology")
    items = [{**ONE_WORD, "question": f"Question {i} about pigments?", "topic": "Pigments"} for i in range(3)]
    for m in (weak, strong):
        fake_ai["replies"]["You write exam questions"] = chat({"questions": items})
        m["qs"] = student.data(generate(student, m["id"], "ONE_WORD", 1, n=3))["questions"]
    for q in strong["qs"][:2]:
        student.post("/api/attempts/evaluate", {"question_id": q["id"], "answer": "chlorophyll"})
    for q in weak["qs"][:2]:
        student.post("/api/attempts/evaluate", {"question_id": q["id"], "answer": "water"})

    science = folder(student, "Science")
    docs = science["subfolders"][0]["documents"]
    assert [d["material_id"] for d in docs] == [weak["id"], strong["id"]]  # weakest first
    w, s = docs
    assert w["weak"] and w["score"] == 0 and w["vs_average"] == -50 and w["weak_concepts"] == [{"concept": "Pigments", "count": 2}]
    assert not s["weak"] and s["score"] == 100 and s["vs_average"] == 50
    assert tree(student)["average_score"] == 50

    # a focused session on that document only: what went wrong first, then what has not been tried
    p = student.data(student.get(f"/api/practice?document=material:{weak['id']}"))
    got = [q["id"] for q in p["questions"]]
    assert p["kind"] == "document" and set(got[:2]) == {q["id"] for q in weak["qs"][:2]} and got[2] == weak["qs"][2]["id"]


def test_parent_folder_names_its_weakest_subfolder(student):
    (q1, o1), (q2, o2) = adding_across()[:2]
    student.answer(q1["id"], o1)
    student.answer(q2["id"], o2)
    maths = folder(student, "Maths")
    assert maths["weakest"]["subfolder"] == "Fractions" and maths["weakest"]["document"] == "fractions"
    assert maths["subfolders"][0]["name"] == "Fractions" and maths["subfolders"][0]["weak"]
    p = student.data(student.get("/api/practice?document=fractions"))
    assert {q["id"] for q in p["questions"][:2]} == {q1["id"], q2["id"]}


# ───────────────────────── notes generator ─────────────────────────

STRUCTURE = {"title": "Photosynthesis", "headings": [{"heading": "Photosynthesis", "subheadings": ["Inputs", "Outputs"]}], "definitions": [{"term": "Photosynthesis", "definition": "How plants make food from light."}]}
GENERATED = {
    "title": "Photosynthesis", "outline": STRUCTURE["headings"], "definitions": STRUCTURE["definitions"],
    "summary": "Plants turn light, water and carbon dioxide into glucose and oxygen.",
    "keywords": [{"keyword": "Glucose", "meaning": "The sugar a plant makes."}], "key_points": ["Light is needed.", "Oxygen is released."],
    "weightage": {"level": "high", "reason": "It underpins the rest of plant biology."},
    "hierarchy": [{"concept": "Photosynthesis", "children": [{"concept": "Inputs", "details": ["Light → energy", "Water"]}]}],
    "core_concepts": [{"concept": "Energy conversion", "explanation": "Light energy becomes chemical energy."}],
    "potential_questions": [f"Question {i}?" for i in range(12)], "brief_summary": "Plants make food. They need light. They release oxygen.",
}
SECTIONS = ["# Photosynthesis", "## Headings & Subheadings", "### Definitions", "### Summary", "### Must-Know Keywords", "### Key Points", "### Topic Weightage", "### Concept Hierarchy", "### Core Concepts", "### Potential Questions", "### Brief Summary"]


def make_notes(student, name="notes.txt", data=NOTES[1], mime="text/plain"):
    return student.client.post("/api/notes", headers=student.headers, files={"file": (name, data, mime)})


def test_notes_are_read_by_mistral_written_by_groq_and_kept(student, other, fake_ai):
    seen = {}

    def write(prompt):
        seen["prompt"] = prompt
        return chat(GENERATED)

    fake_ai["replies"]["notes app"] = chat(STRUCTURE)
    fake_ai["replies"]["You write revision notes"] = write
    r = make_notes(student)
    assert r.status_code == 201, r.text
    n = r.json()["data"]
    # Mistral read the structure first, and Groq was given it
    assert [c[0] for c in fake_ai["calls"]] == ["mistral", "groq"] and "DEFINITIONS:\n- Photosynthesis: How plants make food from light." in seen["prompt"]
    # always the same sections, in the same order
    md = n["markdown"]
    positions = [md.index(s) for s in SECTIONS]
    assert positions == sorted(positions)
    assert "**High** — It underpins" in md and "    - Light → energy" in md and "10. Question 9?" in md and "11." not in md
    assert n["content"]["brief_summary"] == ["Plants make food.", "They need light.", "They release oxygen."] and n["weightage"] == "High"

    listed = student.data(student.get("/api/notes"))
    assert [x["id"] for x in listed] == [n["id"]] and "markdown" not in listed[0]
    assert student.data(student.get(f"/api/notes/{n['id']}"))["markdown"] == md
    pdf = student.get(f"/api/notes/{n['id']}/pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF") and len(pdf.content) > 1500

    # notes belong to the student who made them
    assert other.get(f"/api/notes/{n['id']}").json()["error"]["code"] == "NOTE_NOT_FOUND"
    assert other.get(f"/api/notes/{n['id']}/pdf").status_code == 404 and student.data(other.get("/api/notes")) == []
    assert student.data(student.client.delete(f"/api/notes/{n['id']}", headers=student.headers)) == {"deleted": n["id"]}
    assert student.data(student.get("/api/notes")) == []


def test_notes_still_get_written_when_mistral_cannot_read_the_structure(student, fake_ai):
    from app.services.ai_client import ProviderError

    def down(_prompt):
        raise ProviderError("mistral", "Document processing failed.")

    fake_ai["replies"]["notes app"] = down
    fake_ai["replies"]["You write revision notes"] = chat(GENERATED)
    assert make_notes(student).status_code == 201


def test_notes_reject_bad_files_and_need_groq(student):
    assert make_notes(student, name="virus.exe").json()["error"]["code"] == "INVALID_FILE_TYPE"
    assert make_notes(student, data=b"too short").json()["error"]["code"] == "DOCUMENT_PROCESSING_FAILED"
    r = make_notes(student)  # no Groq key in this test
    assert r.status_code == 503 and r.json()["error"]["code"] == "AI_PROVIDER_ERROR"


# ───────────────────────── PDF name, renaming, one document at a time ─────────────────────────


def test_pdf_downloads_under_a_hamstar_name(student, fake_ai):
    fake_ai["replies"]["notes app"] = chat(STRUCTURE)
    fake_ai["replies"]["You write revision notes"] = chat({**GENERATED, "title": "Newton's Laws: F = ma!"})
    n = make_notes(student).json()["data"]
    pdf = student.get(f"/api/notes/{n['id']}/pdf")
    assert pdf.headers["content-disposition"] == 'attachment; filename="HamSTAR_Notes_Newton_s_Laws_F_ma.pdf"'
    assert pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF") and b"%%EOF" in pdf.content[-1024:]


def rename(student, **body):
    return student.post("/api/folders/rename", body)


def test_rename_a_subfolder_and_a_parent_folder(student, fake_ai):
    fake_ai["replies"]["filled in a blank"] = BLANK_JUDGE
    a = put(student, name="a.txt", subject="Physics")
    put(student, name="b.txt", subject="Physics")
    put(student, name="c.txt", subject="Chemistry")
    fake_ai["replies"]["You write exam questions"] = chat({"questions": [{**ONE_WORD, "topic": "Light"}]})
    q = student.data(generate(student, a["id"], "ONE_WORD", 1))["questions"][0]
    student.post("/api/attempts/evaluate", {"question_id": q["id"], "answer": "water"})
    student.post("/api/attempts/evaluate", {"question_id": q["id"], "answer": "sand"})

    r = student.data(rename(student, parent="science", subfolder="physics", name="  Mechanics  "))
    science = next(f for f in r["folders"] if f["name"] == "Science")
    assert r["moved"] == 2 and sorted(s["name"] for s in science["subfolders"]) == ["Chemistry", "Mechanics"]
    mech = next(s for s in science["subfolders"] if s["name"] == "Mechanics")
    assert mech["document_count"] == 2
    # the questions and the mistake log follow the new name
    assert student.data(student.get(f"/api/questions/{q['id']}"))["topic"] == "Mechanics"
    assert student.data(student.get("/api/recurring-mistakes"))["recurring"][0]["folder"] == "Mechanics"

    r = student.data(rename(student, parent="Science", name="Natural Sciences"))
    names = [f["name"] for f in r["folders"]]
    assert r["moved"] == 3 and "Natural Sciences" in names and "Science" not in names
    assert student.data(student.get("/api/recurring-mistakes"))["recurring"][0]["parent"] == "Natural Sciences"
    # a subfolder keeps its parent even when its new name sounds like another subject
    student.data(rename(student, parent="Natural Sciences", subfolder="Chemistry", name="Algebra of atoms"))
    assert "Algebra of atoms" in [s["name"] for s in folder(student, "Natural Sciences")["subfolders"]]


def test_starter_folders_can_be_renamed_too(student, other):
    r = student.data(rename(student, parent="Maths", subfolder="Fractions", name="Fraction Fun"))
    maths = next(f for f in r["folders"] if f["name"] == "Maths")
    assert r["moved"] == 1 and sorted(s["name"] for s in maths["subfolders"]) == ["Algebra", "Fraction Fun"]
    doc = next(s for s in maths["subfolders"] if s["name"] == "Fraction Fun")["documents"][0]
    assert doc["id"] == "fractions" and doc["kind"] == "starter"
    # it is still the same set of questions, and mistakes in it are logged under the new name
    assert student.data(student.get("/api/questions/next?topic=fractions"))["total"] == doc["question_count"]
    (q1, o1), (q2, o2) = adding_across()[:2]
    student.answer(q1["id"], o1)
    student.answer(q2["id"], o2)
    assert student.data(student.get("/api/recurring-mistakes"))["recurring"][0]["folder"] == "Fraction Fun"

    student.data(rename(student, parent="Maths", name="Number Nook"))
    nook = folder(student, "Number Nook")
    assert sorted(s["name"] for s in nook["subfolders"]) == ["Algebra", "Fraction Fun"]
    # one student's names are their own
    assert [f["name"] for f in tree(other)["folders"]] == ["Maths"]


def test_rename_needs_a_real_folder_and_a_name(student):
    assert rename(student, parent="Nowhere", name="X").json()["error"]["code"] == "FOLDER_NOT_FOUND"
    assert rename(student, parent="Maths", subfolder="Nope", name="X").json()["error"]["code"] == "FOLDER_NOT_FOUND"
    assert rename(student, parent="Maths", name="  .  ").json()["error"]["code"] == "INVALID_FOLDER_NAME"


def test_questions_come_only_from_the_document_being_worked_on(student, fake_ai):
    light = put(student, name="light.txt", data=b"Optics notes. A prism splits white light into a spectrum of colours by refraction.", subject="Physics")
    sound = put(student, name="sound.txt", data=b"Acoustics notes. Sound is a longitudinal wave and cannot travel through a vacuum.", subject="Physics")
    prompts = []

    def write(prompt):
        prompts.append(prompt)
        about = "prism" if "prism" in prompt else "vacuum"
        return chat({"questions": [{**ONE_WORD, "question": f"A question about the {about}?", "topic": about}]})

    fake_ai["replies"]["You write exam questions"] = write
    q_light = student.data(generate(student, light["id"], "ONE_WORD", 1))["questions"][0]
    q_sound = student.data(generate(student, sound["id"], "ONE_WORD", 1))["questions"][0]
    # both sit in the same subfolder, yet each prompt carried only its own document
    assert "prism" in prompts[0] and "vacuum" not in prompts[0] and "vacuum" in prompts[1] and "prism" not in prompts[1]
    assert "Write questions only from this document" in prompts[0]

    a = student.data(student.get(f"/api/questions/next?material_id={light['id']}&question_type=ONE_WORD"))
    b = student.data(student.get(f"/api/questions/next?material_id={sound['id']}&question_type=ONE_WORD"))
    assert a["total"] == 1 and a["question"]["id"] == q_light["id"] and a["document"] == {"id": f"material:{light['id']}", "title": light["title"], "file_name": "light.txt"}
    assert b["total"] == 1 and b["question"]["id"] == q_sound["id"] and b["document"]["file_name"] == "sound.txt"
    # switching document switches the set: each has its own position
    student.post("/api/attempts/evaluate", {"question_id": q_light["id"], "answer": "chlorophyll"})
    assert student.data(student.get(f"/api/questions/next?material_id={light['id']}&question_type=ONE_WORD"))["completed"]
    assert not student.data(student.get(f"/api/questions/next?material_id={sound['id']}&question_type=ONE_WORD"))["completed"]
    assert student.data(student.get("/api/questions/next?topic=fractions"))["document"]["id"] == "fractions"
