"""Uploads, Mistral question generation and Groq evaluation, all with the providers faked."""
import pytest

from tests.conftest import chat

NOTES = ("notes.txt", b"# Photosynthesis\nPlants turn light, water and carbon dioxide into glucose and oxygen.\n", "text/plain")

MCQ = {"question": "What gas do plants release in photosynthesis?", "options": ["A. Oxygen", "B) Carbon dioxide", "Nitrogen", "Hydrogen"], "correct_option": "A",
       "explanation": "Oxygen is released as a by-product.", "wrong_option_diagnosis": {"B": "Confuses the gas taken in with the gas released."}, "topic": "Photosynthesis", "difficulty": "medium"}
BLANK = {"question": "Plants make ____ from light.", "expected_answer": "glucose", "accepted_answers": ["sugar"], "explanation": "Glucose is the sugar made."}
WRITTEN = {"question": "Explain photosynthesis.", "model_answer": "Plants use light to turn water and carbon dioxide into glucose and oxygen.", "rubric": [{"point": "inputs", "marks": 2}, {"point": "outputs", "marks": 2}], "expected_concepts": ["light", "glucose"]}


def upload(student, name=NOTES[0], data=NOTES[1], mime=NOTES[2]):
    return student.client.post("/api/study-materials/upload", headers=student.headers, files={"file": (name, data, mime)})


def generate(student, material_id, question_type, marks, n=1):
    return student.post("/api/questions/generate", {"study_material_id": material_id, "question_type": question_type, "marks": marks, "number_of_questions": n, "topic": "Photosynthesis"})


# ───────────────────────── uploads ─────────────────────────


def test_plain_notes_are_read_without_any_ai(student):
    m = student.data(upload(student))
    assert m["processing_status"] == "PROCESSED" and m["has_text"] and m["concepts"] == ["Photosynthesis"] and m["file_type"] == "notes"
    assert [x["id"] for x in student.data(student.get("/api/study-materials"))] == [m["id"]]
    assert student.data(student.client.delete(f"/api/study-materials/{m['id']}", headers=student.headers)) == {"deleted": m["id"]}
    assert student.get(f"/api/study-materials/{m['id']}").json()["error"]["code"] == "STUDY_MATERIAL_NOT_FOUND"


def test_upload_is_validated(student):
    assert upload(student, "run.exe", b"MZ", "application/octet-stream").json()["error"]["code"] == "INVALID_FILE_TYPE"
    assert upload(student, "fake.pdf", b"not a pdf", "application/pdf").json()["error"]["code"] == "INVALID_FILE_TYPE"
    assert upload(student, "notes.txt", b"x", "application/pdf").json()["error"]["code"] == "INVALID_FILE_TYPE"
    assert upload(student, "big.txt", b"x" * (1024 * 1024 + 1), "text/plain").json()["error"]["code"] == "FILE_TOO_LARGE"


def test_filename_cannot_escape_the_upload_folder(student):
    import os

    from app.core.config import get_settings

    m = student.data(upload(student, "../../../evil.txt", b"fractions and denominators", "text/plain"))
    assert m["file_name"] == "evil.txt" and m["topic"] == "fractions"
    root = os.path.realpath(get_settings().upload_dir)
    stored = [os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs]
    assert stored and all(os.path.realpath(p).startswith(root) and "evil" not in p for p in stored)


def _office(inner_name, xml):
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(inner_name, xml)
    return buf.getvalue()


def _text_pdf(text: str) -> bytes:
    """A minimal but well-formed one-page PDF with a real text layer."""
    stream = f"BT /F1 18 Tf 20 60 Td ({text}) Tj ET".encode()
    objects = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 400 120]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length " + str(len(stream)).encode() + b">>stream\n" + stream + b"\nendstream",
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for n, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj".encode() + body + b"endobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n" + b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    return out + f"trailer<</Size {len(objects) + 1}/Root 1 0 R>>\nstartxref\n{xref}\n%%EOF".encode()


TEXT_PDF = _text_pdf("Fractions have a numerator and a denominator")


def test_scanned_pdf_without_ocr_is_kept_but_marked_failed(student):
    m = student.data(upload(student, "book.pdf", b"%PDF-1.4 ...", "application/pdf"))
    assert m["processing_status"] == "FAILED" and "scanned" in m["processing_error"] and "MISTRAL_API_KEY" in m["processing_error"]
    assert generate(student, m["id"], "MCQ", 1).json()["error"]["code"] == "DOCUMENT_PROCESSING_FAILED"


def test_text_pdf_word_and_powerpoint_are_read_locally(student):
    pdf = student.data(upload(student, "fractions.pdf", TEXT_PDF, "application/pdf"))
    assert pdf["processing_status"] == "PROCESSED" and pdf["topic"] == "fractions"
    docx = _office("word/document.xml", "<w:document><w:p><w:r><w:t>Expand the </w:t></w:r><w:r><w:t xml:space=\"preserve\">bracket &amp; simplify</w:t></w:r></w:p></w:document>")
    d = student.data(upload(student, "algebra.docx", docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))
    assert d["processing_status"] == "PROCESSED" and d["topic"] == "algebra"
    pptx = _office("ppt/slides/slide1.xml", "<p:sld><a:p><a:r><a:t>Numerator and denominator</a:t></a:r></a:p></p:sld>")
    assert student.data(upload(student, "deck.pptx", pptx, "application/vnd.openxmlformats-officedocument.presentationml.presentation"))["processing_status"] == "PROCESSED"
    assert upload(student, "bad.docx", b"PK not really a zip", "application/octet-stream").json()["data"]["processing_status"] == "FAILED"


def test_pdf_is_read_with_mistral_ocr(student, fake_ai):
    fake_ai["replies"]["From the material below"] = chat({"title": "Plant biology", "concepts": ["Photosynthesis", "Chlorophyll"], "sections": [{"heading": "Intro", "summary": "How plants make food."}]})
    m = student.data(upload(student, "book.pdf", b"%PDF-1.4 ...", "application/pdf"))
    assert m["processing_status"] == "PROCESSED" and m["title"] == "Plant biology" and m["concepts"] == ["Photosynthesis", "Chlorophyll"]
    assert ("mistral", "/ocr") in fake_ai["calls"]


def test_when_ocr_is_not_on_the_plan_pdfs_and_images_are_still_read(student, fake_ai):
    from app.services.ai_client import ProviderError
    from app.services.mistral_service import get_mistral

    real = get_mistral()._post

    def no_ocr(path, payload):
        if path == "/ocr":
            raise ProviderError("mistral", "Document processing failed. Please try again in a moment.")
        return real(path, payload)

    get_mistral()._post = no_ocr  # undone by the fake_ai fixture's monkeypatch
    fake_ai["replies"]["Transcribe all the text"] = chat("Equivalent fractions: 2/4 = 1/2")
    assert student.data(upload(student, "fractions.pdf", TEXT_PDF, "application/pdf"))["processing_status"] == "PROCESSED"
    img = student.data(upload(student, "board.png", b"\x89PNG\r\n\x1a\n....", "image/png"))
    assert img["processing_status"] == "PROCESSED" and img["topic"] == "fractions"


def test_materials_are_private(student, other):
    m = student.data(upload(student))
    assert other.get(f"/api/study-materials/{m['id']}").status_code == 403
    assert generate(other, m["id"], "MCQ", 1).status_code == 403


# ───────────────────────── generation ─────────────────────────


@pytest.mark.parametrize("question_type,marks,code", [("MCQ", 5, "INVALID_MARKS"), ("SHORT_ANSWER", 2, "INVALID_MARKS"), ("LONG_ANSWER", 1, "INVALID_MARKS"), ("FILL_BLANK", 3, "INVALID_MARKS"), ("ESSAY", 5, "INVALID_QUESTION_TYPE")])
def test_mark_rules_are_enforced(student, question_type, marks, code):
    m = student.data(upload(student))
    r = generate(student, m["id"], question_type, marks)
    assert r.status_code == 422 and r.json()["error"]["code"] == code


@pytest.mark.parametrize("question_type,marks,item", [("MCQ", 1, MCQ), ("FILL_BLANK", 2, BLANK), ("SHORT_ANSWER", 6, WRITTEN), ("LONG_ANSWER", 15, {**WRITTEN, "key_points": ["light"]})])
def test_each_question_type_is_generated_and_stored(student, fake_ai, question_type, marks, item):
    m = student.data(upload(student))
    fake_ai["replies"]["You write exam questions"] = chat({"questions": [item, item, {"question": "broken"}]})
    out = student.data(generate(student, m["id"], question_type, marks, 3))
    # the duplicate and the malformed item are dropped
    assert len(out["questions"]) == 1
    q = out["questions"][0]
    assert q["type"] == question_type and q["marks"] == marks and "correct" not in str(q)
    assert student.data(student.get(f"/api/questions/{q['id']}"))["prompt"] == item["question"]
    assert student.data(student.get(f"/api/study-materials/{m['id']}"))["question_count"] == 1


def test_unusable_ai_output_is_a_controlled_error(student, fake_ai):
    m = student.data(upload(student))
    fake_ai["replies"]["You write exam questions"] = chat("Sure! Here are your questions: ...")
    r = generate(student, m["id"], "MCQ", 1)
    assert r.status_code == 503 and r.json()["error"]["code"] == "QUESTION_GENERATION_FAILED"
    assert student.data(student.get(f"/api/study-materials/{m['id']}"))["question_count"] == 0


def test_json_wrapped_in_a_code_fence_is_recovered(student, fake_ai):
    import json

    m = student.data(upload(student))
    fake_ai["replies"]["You write exam questions"] = chat("```json\n" + json.dumps({"questions": [MCQ]}) + "\n```")
    assert len(student.data(generate(student, m["id"], "MCQ", 1))["questions"]) == 1


# ───────────────────────── evaluation of generated questions ─────────────────────────


def _one(student, fake_ai, question_type, marks, item):
    m = student.data(upload(student))
    fake_ai["replies"]["You write exam questions"] = chat({"questions": [item]})
    return student.data(generate(student, m["id"], question_type, marks))["questions"][0]["id"], m["id"]


def test_generated_mcq_wrong_answer_gets_a_groq_written_follow_up(student, fake_ai):
    qid, material_id = _one(student, fake_ai, "MCQ", 1, MCQ)
    assert student.data(student.get(f"/api/questions/next?material_id={material_id}"))["question"]["id"] == qid
    fake_ai["replies"]["Two explanations compete"] = chat({"question": "Which gas do leaves give off in daylight?", "options": ["Carbon dioxide", "Oxygen", "Helium", "Methane"], "correct_option": "B", "misconception_option": "A", "purpose": "Shows whether intake and output are confused.", "explanation": "Oxygen."})
    fake_ai["replies"]["Write feedback for a student"] = chat({"feedback": "You are mixing up the gas taken in with the gas given off."})

    fake_ai["replies"]["explained their thinking"] = lambda prompt: chat({"signals": [{"hypothesis": next(w for w in prompt.split() if w.startswith("GEN:")).rstrip(":"), "strength": "strong", "quote": "plants take in oxygen"}]})
    d = student.answer(qid, "B", reasoning="I thought plants take in oxygen")["diagnostic"]
    assert d["diagnosis"] is None and d["status"] == "FOLLOWUP_REQUIRED"
    # however strongly the student's words point one way, nothing passes 70% before the follow-up
    assert d["reasoning_evidence"] and all(h["confidence"] <= 70 for h in d["hypotheses"])
    assert d["reasoning_evidence"][0]["label"] == "the rule “Confuses the gas taken in with the gas released”"
    f = student.data(student.post(f"/api/diagnostics/{d['session_id']}/followup"))
    assert f["source"] == "groq" and f["question"].startswith("Which gas do leaves")
    view = student.data(student.post(f"/api/diagnostics/{d['session_id']}/evaluate-followup", {"answer": "A"}))
    assert view["diagnosis"]["primary"] == "MISCONCEPTION" and view["diagnosis"]["confidence"] > 70
    assert view["feedback"].startswith("You are mixing up")


def test_groq_reads_the_students_reasoning(student, fake_ai):
    fake_ai["replies"]["explained their thinking"] = chat({"signals": [{"hypothesis": "F_ADD_ACROSS", "strength": "strong", "quote": "added top and bottom"}, {"hypothesis": "NOT_A_REAL_ONE", "strength": "strong", "quote": "x"}], "slip_kind": None, "explanation": "Sounds like adding across."})
    d = student.answer("f1", "A", reasoning="I added top and bottom")["diagnostic"]
    assert [e["hypothesis"] for e in d["reasoning_evidence"]] == ["F_ADD_ACROSS"]  # unknown hypotheses are ignored
    # even a "strong" signal is light evidence: still no diagnosis without the follow-up
    assert d["diagnosis"] is None and d["followup"]["required"]


def test_reasoning_falls_back_to_phrase_matching_when_groq_fails(student, fake_ai):
    from app.services.ai_client import ProviderError

    def boom(_prompt):
        raise ProviderError("groq", "Answer evaluation is temporarily unavailable.")

    fake_ai["replies"]["explained their thinking"] = boom
    d = student.answer("f1", "A", reasoning="I added the tops and then added the bottoms")["diagnostic"]
    assert d["reasoning_evidence"][0]["hypothesis"] == "F_ADD_ACROSS"


def test_fill_in_the_blank(student, fake_ai):
    qid, _ = _one(student, fake_ai, "FILL_BLANK", 2, BLANK)
    right = student.data(student.post("/api/attempts/evaluate", {"question_id": qid, "answer": "  Sugar. "}))
    assert right["is_correct"] and right["classification"] == "CORRECT" and right["marks_awarded"] == 2 and right["tiara_awarded"] == 1

    fake_ai["replies"]["filled in a blank"] = chat({"classification": "misconception", "feedback": "Oxygen is a by-product, not the food.", "confidence": 80})
    wrong = student.data(student.post("/api/attempts/evaluate", {"question_id": qid, "answer": "oxygen"}))
    assert not wrong["is_correct"] and wrong["classification"] == "MISCONCEPTION" and wrong["marks_awarded"] == 0 and wrong["tiara_awarded"] == 0


@pytest.mark.parametrize("question_type,marks,awarded,correct", [("SHORT_ANSWER", 8, 6, True), ("LONG_ANSWER", 20, 14, False)])
def test_written_answers_are_marked_by_groq_against_the_rubric(student, fake_ai, question_type, marks, awarded, correct):
    qid, _ = _one(student, fake_ai, question_type, marks, WRITTEN)
    fake_ai["replies"]["You mark a student's written answer"] = chat({"marks_awarded": awarded, "missing_concepts": ["oxygen"], "misconceptions": [], "feedback": "Good on inputs.", "evidence": ["names light"], "confidence": 81})
    r = student.data(student.post("/api/attempts/evaluate", {"question_id": qid, "answer": "Plants use light to make glucose."}))
    assert r["marks_awarded"] == awarded and r["total_marks"] == marks and r["percentage"] == awarded / marks * 100
    # 70% exactly is not enough; the bar is MORE than 70
    assert r["is_correct"] is correct and r["tiara_awarded"] == (1 if correct else 0)
    assert r["missing_concepts"] == ["oxygen"] and r["confidence"] == 81


def test_written_answer_when_groq_is_down_is_a_clean_error(student, fake_ai):
    from app.services.ai_client import ProviderError

    def down(_prompt):
        raise ProviderError("groq", "Answer evaluation is temporarily unavailable.")

    qid, _ = _one(student, fake_ai, "SHORT_ANSWER", 6, WRITTEN)
    fake_ai["replies"]["You mark a student's written answer"] = down
    r = student.post("/api/attempts/evaluate", {"question_id": qid, "answer": "Plants use light."})
    assert r.status_code == 503 and r.json()["error"] == {"code": "AI_PROVIDER_ERROR", "message": "Answer evaluation is temporarily unavailable."}
    # nothing was recorded or rewarded for an answer that could not be marked
    assert student.data(student.get("/api/dashboard"))["stats"]["answered"] == 0


# ───────────────────────── any subject is accepted ─────────────────────────

OOP = b"Object-oriented programming: a class is a blueprint, inheritance lets a subclass extend it, and polymorphism lets one interface have many forms."


def test_subject_is_detected_for_subjects_outside_the_starter_bank(student):
    m = student.data(upload(student, "week3.txt", OOP, "text/plain"))
    assert m["processing_status"] == "PROCESSED" and m["subject"] == "Object-Oriented Programming" and m["subject_detected"]
    assert m["topic"] is None  # not one of the starter folders, and that is fine
    physics = student.data(upload(student, "notes.txt", b"Newton's second law: force equals mass times acceleration. Momentum is mass times velocity.", "text/plain"))
    assert physics["subject"] == "Physics"


def test_undetected_subject_falls_back_to_general_and_can_be_set_by_hand(student, fake_ai):
    m = student.data(upload(student, "scan.txt", b"lorem ipsum dolor sit amet", "text/plain"))
    assert m["processing_status"] == "PROCESSED" and m["subject"] == "General" and not m["subject_detected"]

    fake_ai["replies"]["You write exam questions"] = chat({"questions": [MCQ]})
    q = student.data(generate(student, m["id"], "MCQ", 1))["questions"][0]
    assert q["topic"] == "General"

    # the student names it; anything they type is a valid subject, and the questions move with it
    patched = student.data(student.client.patch(f"/api/study-materials/{m['id']}", headers=student.headers, json={"subject": "  Medieval  Tamil Literature "}))
    assert patched["subject"] == "Medieval Tamil Literature" and patched["subject_detected"]
    assert student.data(student.get(f"/api/questions/{q['id']}"))["topic"] == "Medieval Tamil Literature"
    folder = next(f for f in student.data(student.get("/api/dashboard"))["materials"] if f["id"] == m["id"])
    assert folder["subject"] == "Medieval Tamil Literature" and folder["question_count"] == 1 and folder["answered"] == 0


def test_subject_typed_at_upload_wins_and_ai_subject_is_used_otherwise(student, fake_ai):
    fake_ai["replies"]["From the material below"] = chat({"title": "Supply and demand", "subject": "Microeconomics", "concepts": ["elasticity"], "sections": []})
    assert student.data(upload(student, "a.txt", OOP, "text/plain"))["subject"] == "Microeconomics"
    typed = student.client.post("/api/study-materials/upload", headers=student.headers, files={"file": ("a.txt", OOP, "text/plain")}, data={"subject": "Data Structures"})
    assert student.data(typed)["subject"] == "Data Structures"


def test_generated_folder_tracks_progress(student, fake_ai):
    qid, material_id = _one(student, fake_ai, "MCQ", 1, MCQ)
    student.answer(qid, "A")
    folder = next(f for f in student.data(student.get("/api/dashboard"))["materials"] if f["id"] == material_id)
    assert folder["answered"] == 1 and folder["correct"] == 1 and folder["accuracy"] == 100


# ───────────────────────── question types ─────────────────────────

ONE_WORD = {"question": "Which pigment absorbs light in plants?", "expected_answer": "chlorophyll", "accepted_answers": ["chlorophyl"], "explanation": "Chlorophyll absorbs light.", "difficulty": "Easy"}


def test_one_word_questions_and_per_type_folders(student, fake_ai):
    m = student.data(upload(student))
    fake_ai["replies"]["You write exam questions"] = chat({"questions": [ONE_WORD]})
    assert generate(student, m["id"], "ONE_WORD", 2).json()["error"]["code"] == "INVALID_MARKS"
    q = student.data(generate(student, m["id"], "ONE_WORD", 1))["questions"][0]
    assert q["type"] == "ONE_WORD" and q["options"] == [] and q["difficulty"] == "easy"

    # each type is its own list within the folder
    assert student.get(f"/api/questions/next?material_id={m['id']}").json()["error"]["code"] == "NO_QUESTIONS_OF_TYPE"
    nxt = student.data(student.get(f"/api/questions/next?material_id={m['id']}&question_type=ONE_WORD"))
    assert nxt["question"]["id"] == q["id"] and nxt["total"] == 1
    assert student.get(f"/api/questions/next?material_id={m['id']}&question_type=ESSAY").json()["error"]["code"] == "INVALID_QUESTION_TYPE"

    right = student.data(student.post("/api/attempts/evaluate", {"question_id": q["id"], "answer": "Chlorophyll"}))
    assert right["is_correct"] and right["tiara_awarded"] == 1 and right["question_type"] == "ONE_WORD"
    fake_ai["replies"]["filled in a blank"] = chat({"classification": "MISCONCEPTION", "feedback": "That is the gas, not the pigment.", "confidence": 80})
    wrong = student.data(student.post("/api/attempts/evaluate", {"question_id": q["id"], "answer": "oxygen"}))
    assert not wrong["is_correct"] and wrong["diagnostic"] is None
    fake_ai["replies"]["Explain the correct answer to them"] = chat({"explanation": "Chlorophyll is the green pigment that soaks up light."})
    explained = student.data(student.post(f"/api/attempts/{wrong['attempt_id']}/explain", {"level": 0}))
    assert explained["correct_answer"]["text"] == "chlorophyll" and "pigment" in explained["explanation"]
    folder = next(f for f in student.data(student.get("/api/dashboard"))["materials"] if f["id"] == m["id"])
    assert folder["questions_by_type"] == {"ONE_WORD": 1}


def test_starter_folders_can_have_other_question_types(student, fake_ai):
    assert student.get("/api/questions/next?topic=fractions&question_type=FILL_BLANK").json()["error"]["code"] == "NO_QUESTIONS_OF_TYPE"
    seen = []

    def reply(prompt):
        seen.append(prompt)
        return chat({"questions": [{"question": "1/2 is the same as ____ quarters.", "expected_answer": "2", "accepted_answers": ["two"], "explanation": "1/2 = 2/4."}]})

    fake_ai["replies"]["You write exam questions"] = reply
    out = student.data(student.post("/api/questions/generate", {"folder": "fractions", "question_type": "FILL_BLANK", "marks": 1, "number_of_questions": 1}))
    # written from the folder's own verified content, not from nothing
    assert "Adds numerators together and denominators together" in seen[0] and "3/4" in seen[0]
    nxt = student.data(student.get("/api/questions/next?topic=fractions&question_type=FILL_BLANK"))
    assert nxt["question"]["id"] == out["questions"][0]["id"] and nxt["question"]["topic"] == "Fractions"
    assert student.data(student.post("/api/attempts/evaluate", {"question_id": nxt["question"]["id"], "answer": "two"}))["is_correct"]
    # the helper material behind it is not shown as an upload, and the MCQ folder is untouched
    assert student.data(student.get("/api/study-materials")) == [] and student.data(student.get("/api/dashboard"))["materials"] == []
    assert student.data(student.get("/api/questions/next?topic=fractions"))["number"] == 1


# ───────────────────────── concept-based marking and mistake types ─────────────────────────


def test_written_answers_get_structured_concept_feedback_and_partial_marks(student, fake_ai):
    qid, _ = _one(student, fake_ai, "SHORT_ANSWER", 8, WRITTEN)
    prompts = []

    def grade(prompt):
        prompts.append(prompt)
        return chat({"marks_awarded": 5, "keywords_matched": ["light", "glucose (you said: sugar)"], "concepts_covered": ["Plants use light to make food"], "missing_concepts": ["Oxygen is released"],
                     "complete_answer": "Light, water and carbon dioxide become glucose and oxygen.", "feedback": "Good start.", "confidence": 64})

    fake_ai["replies"]["You mark a student's written answer"] = grade
    fake_ai["replies"]["Decide which ONE kind of mistake"] = chat({"mistake_type": "incomplete understanding", "reason": "The outputs were left out."})
    r = student.data(student.post("/api/attempts/evaluate", {"question_id": qid, "answer": "Plants use sunlight to make sugar."}))
    # the marker is told to judge ideas, not wording
    assert "Mark the CONCEPTS, not the wording" in prompts[0] and "water turns to gas when heated" in prompts[0] and "NOT the only acceptable wording" in prompts[0]
    assert r["marks_awarded"] == 5 and r["percentage"] == 62.5 and not r["is_correct"]  # partial marks, below the 70% bar
    assert r["keywords_matched"] == ["light", "glucose (you said: sugar)"] and r["concepts_covered"] == ["Plants use light to make food"]
    assert r["missing_concepts"] == ["Oxygen is released"] and r["complete_answer"].startswith("Light, water")

    fake_ai["replies"]["Explain the correct answer to them"] = chat({"explanation": "Plants turn light into food and give off oxygen."})
    e = student.data(student.post(f"/api/attempts/{r['attempt_id']}/explain", {"level": 0}))
    assert e["mistake_type"]["kind"] == "GAP_IN_UNDERSTANDING" and e["mistake_type"]["message"] == "Looks like this was a Gap in Understanding"
    # classified once, then remembered
    calls = len([c for c in fake_ai["calls"] if c[0] == "groq"])
    assert student.data(student.post(f"/api/attempts/{r['attempt_id']}/explain", {"level": 1}))["mistake_type"]["kind"] == "GAP_IN_UNDERSTANDING"
    assert len([c for c in fake_ai["calls"] if c[0] == "groq"]) == calls + 1  # only the new explanation


# ───────────────────────── structured answers, follow-ups for written answers, finishing a set ─────────────────────────


def test_the_correct_answer_always_comes_in_four_parts(student, fake_ai):
    from app.services.ai_client import ProviderError

    def down(_prompt):
        raise ProviderError("groq", "Explanations are temporarily unavailable.")

    # without Groq: built from the answer key
    fake_ai["replies"]["Explain the correct answer to them"] = down
    r = student.answer("f1", "A")
    e = student.data(student.post(f"/api/attempts/{r['attempt_id']}/explain", {"level": 0}))
    assert e["key_terms"] and e["core_concepts"] and e["explanation"] and e["remember"]
    # with Groq: its own key terms, concepts and line to remember
    fake_ai["replies"]["Explain the correct answer to them"] = chat({"key_terms": ["common denominator"], "core_concepts": ["Only like parts can be added."], "explanation": "Make the bottoms match, then add the tops.", "remember": "Same bottoms first, then add the tops."})
    e = student.data(student.post(f"/api/attempts/{r['attempt_id']}/explain", {"level": 1}))
    assert e["source"] == "groq" and e["key_terms"] == ["common denominator"] and e["core_concepts"] == ["Only like parts can be added."] and e["remember"].startswith("Same bottoms")
    # a reply that leaves a part out is completed from the answer key, never shown with a hole
    fake_ai["replies"]["Explain the correct answer to them"] = chat({"explanation": "Make the bottoms match, then add the tops."})
    e = student.data(student.post(f"/api/attempts/{r['attempt_id']}/explain", {"level": 2}))
    assert e["key_terms"] and e["core_concepts"] and e["remember"]


FOLLOW = {"question": "Which part of a leaf cell holds chlorophyll?", "options": ["Chloroplast", "Nucleus", "Cell wall", "Vacuole"], "correct_option": "A", "explanation": "Chlorophyll sits in the chloroplasts."}


def test_wrong_written_answer_gets_up_to_two_follow_ups_on_the_same_concept(student, fake_ai):
    m = student.data(upload(student))
    fake_ai["replies"]["You write exam questions"] = chat({"questions": [ONE_WORD]})
    q = student.data(generate(student, m["id"], "ONE_WORD", 1))["questions"][0]
    fake_ai["replies"]["filled in a blank"] = chat({"classification": "misconception", "feedback": "Not this one.", "confidence": 80})
    wrong = student.data(student.post("/api/attempts/evaluate", {"question_id": q["id"], "answer": "water"}))
    aid = wrong["attempt_id"]

    prompts = []

    def write(prompt):
        prompts.append(prompt)
        return chat({**FOLLOW, "question": f"{FOLLOW['question']} ({len(prompts)})"})

    fake_ai["replies"]["tests the SAME concept"] = write
    f = student.data(student.post(f"/api/attempts/{aid}/followup"))
    assert f["number"] == 1 and f["max"] == 2 and f["question"]["type"] == "MCQ" and "about as hard" in prompts[0]
    assert all("correct" not in o for o in f["question"]["options"])  # no answer key before it is answered
    # asking again returns the same pending question; it cannot be explained until it is answered
    assert student.data(student.post(f"/api/attempts/{aid}/followup"))["question"]["id"] == f["question"]["id"] and len(prompts) == 1
    assert student.post(f"/api/attempts/{aid}/explain", {"question_id": f["question"]["id"]}).json()["error"]["code"] == "INVALID_QUESTION"

    miss = student.data(student.post(f"/api/attempts/{aid}/followup/evaluate", {"question_id": f["question"]["id"], "selected_option": "b"}))
    assert not miss["is_correct"] and miss["can_try_another"] and not miss["recovered"]
    fake_ai["replies"]["Explain the correct answer to them"] = chat({"key_terms": ["chloroplast"], "core_concepts": ["Chlorophyll sits in chloroplasts."], "explanation": "Chloroplasts are the little green parts that hold chlorophyll.", "remember": "Chloro- goes with chloro-."})
    assert student.data(student.post(f"/api/attempts/{aid}/explain", {"level": 1, "question_id": f["question"]["id"]}))["correct_answer"]["text"] == "Chloroplast"

    # one more, easier, and not a repeat of what was already asked
    second = student.data(student.post(f"/api/attempts/{aid}/followup"))
    assert second["number"] == 2 and second["question"]["id"] != f["question"]["id"] and "Make it EASIER" in prompts[1] and "(1)" in prompts[1]
    tiara = student.data(student.get("/api/dashboard"))["tiara"]["count"]
    hit = student.data(student.post(f"/api/attempts/{aid}/followup/evaluate", {"question_id": second["question"]["id"], "selected_option": "A"}))
    assert hit["is_correct"] and hit["recovered"] and not hit["can_try_another"]
    assert student.data(student.get("/api/dashboard"))["tiara"]["count"] == tiara  # practice, not a new Tiara
    assert student.post(f"/api/attempts/{aid}/followup").json()["error"]["code"] == "NO_MORE_FOLLOWUPS"
    # follow-ups are not part of the folder's own list
    assert student.data(student.get(f"/api/questions/next?material_id={m['id']}&question_type=ONE_WORD"))["total"] == 1


def test_follow_ups_are_only_for_wrong_answers_and_their_owner(student, other, fake_ai):
    m = student.data(upload(student))
    fake_ai["replies"]["You write exam questions"] = chat({"questions": [ONE_WORD]})
    q = student.data(generate(student, m["id"], "ONE_WORD", 1))["questions"][0]
    right = student.data(student.post("/api/attempts/evaluate", {"question_id": q["id"], "answer": "chlorophyll"}))
    assert student.post(f"/api/attempts/{right['attempt_id']}/followup").json()["error"]["code"] == "NOTHING_TO_FOLLOW_UP"
    assert other.post(f"/api/attempts/{right['attempt_id']}/followup").json()["error"]["code"] == "ATTEMPT_NOT_FOUND"


def test_a_finished_set_reports_completion_instead_of_looping(student, fake_ai):
    m = student.data(upload(student))
    second = {**ONE_WORD, "question": "Which gas do plants take in?", "expected_answer": "carbon dioxide", "accepted_answers": ["co2"]}
    fake_ai["replies"]["You write exam questions"] = chat({"questions": [ONE_WORD, second]})
    qs = student.data(generate(student, m["id"], "ONE_WORD", 1, n=2))["questions"]
    url = f"/api/questions/next?material_id={m['id']}&question_type=ONE_WORD"
    first = student.data(student.get(url))
    assert first["completed"] is False and first["number"] == 1 and first["total"] == 2

    fake_ai["replies"]["filled in a blank"] = chat({"classification": "misconception", "feedback": "Not this one.", "confidence": 80})
    student.post("/api/attempts/evaluate", {"question_id": qs[0]["id"], "answer": "chlorophyll"})
    student.post("/api/attempts/evaluate", {"question_id": qs[1]["id"], "answer": "oxygen"})
    done = student.data(student.get(url))
    assert done["completed"] is True and done["question"] is None
    assert done["summary"] == {"total": 2, "attempted": 2, "correct": 1, "wrong": 1, "skipped": 0, "score": 50, "completed": True}
    assert student.data(student.get(url))["completed"] is True  # still done, not back at question 1

    # questions added later carry on from where the set ended: the old ones do not come round again
    third = {**ONE_WORD, "question": "Which sugar do plants make?", "expected_answer": "glucose", "accepted_answers": []}
    fake_ai["replies"]["You write exam questions"] = chat({"questions": [third]})
    new = student.data(generate(student, m["id"], "ONE_WORD", 1))["questions"][0]
    nxt = student.data(student.get(url))
    assert nxt["completed"] is False and nxt["question"]["id"] == new["id"] and nxt["number"] == 3 and nxt["total"] == 3

    # a new upload is a new folder that starts at its own first question
    fresh = student.data(upload(student, name="more.txt"))
    fake_ai["replies"]["You write exam questions"] = chat({"questions": [ONE_WORD]})
    generate(student, fresh["id"], "ONE_WORD", 1)
    assert student.data(student.get(f"/api/questions/next?material_id={fresh['id']}&question_type=ONE_WORD"))["number"] == 1

    # going through a set again is a choice, not something that happens by itself
    student.post("/api/attempts/evaluate", {"question_id": new["id"], "answer": "glucose"})
    assert student.data(student.get(url))["completed"] is True
    assert student.data(student.post("/api/questions/restart", {"material_id": m["id"], "question_type": "ONE_WORD"}))["restarted"]
    again = student.data(student.get(url))
    assert again["completed"] is False and again["number"] == 1 and again["question"]["id"] == first["question"]["id"]


def test_starter_folder_completes_too(student):
    total = student.data(student.get("/api/questions/next?topic=fractions"))["total"]
    for _ in range(total):
        q = student.data(student.get("/api/questions/next?topic=fractions"))["question"]
        student.post("/api/attempts", {"question_id": q["id"], "skipped": True})
    done = student.data(student.get("/api/questions/next?topic=fractions"))
    assert done["completed"] and done["summary"]["skipped"] == total and done["summary"]["attempted"] == 0 and done["summary"]["score"] == 0
    topic = next(t for t in student.data(student.get("/api/progress"))["topics"] if t["id"] == "fractions")
    assert topic["completed"] and topic["question_number"] == total


# ───────────────────────── replies in the shapes Mistral really sends ─────────────────────────


def test_answers_written_as_objects_and_code_fenced_answers_are_kept(student, fake_ai):
    """Mistral wrote detailed answers as objects ({"code_snippet": ..., "explanation": ...}) and put ``` code blocks
    inside answers; both used to make every question unusable."""
    import json

    m = student.data(upload(student))
    code = "```cpp\nclass A {};\nclass B : public A {};\n```"
    detailed = {"question": "Explain multilevel inheritance with a program.", "model_answer": {"code_snippet": code, "explanation": "B inherits from A."},
                "rubric": ["names the idea", {"criterion": "working program", "marks": "8 marks"}], "expected_concepts": "inheritance; base class", "key_points": [{"point": "B extends A"}]}
    # the reply also carries a raw line break inside a string, as model replies sometimes do
    reply = json.dumps({"questions": [detailed]}).replace("\\n", "\n")
    fake_ai["replies"]["You write exam questions"] = chat(reply)
    q = student.data(generate(student, m["id"], "LONG_ANSWER", 15))["questions"]
    assert len(q) == 1 and q[0]["prompt"].startswith("Explain multilevel")
    r = student.data(student.get(f"/api/questions/{q[0]['id']}"))
    assert r["type"] == "LONG_ANSWER"


def test_a_batch_with_nothing_usable_is_asked_for_again(student, fake_ai):


    m = student.data(upload(student))
    replies = [chat({"questions": [{"question": "?"}]}), chat({"questions": [ONE_WORD]})]
    fake_ai["replies"]["You write exam questions"] = lambda _prompt: replies.pop(0)
    assert len(student.data(generate(student, m["id"], "ONE_WORD", 1))["questions"]) == 1 and not replies
