"""PDF libraries, deleting folders, verified maths answers, and task deadlines with reminders."""
from datetime import timedelta

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models import Attempt, MistakeLog, Question, Task
from app.models.base import now
from app.services import pdf_service, reminder_service
from tests.conftest import chat
from tests.test_folders_mistakes_notes import BLANK_JUDGE, GENERATED, STRUCTURE, adding_across, folder, make_notes, outbox, put  # noqa: F401
from tests.test_materials_and_ai import ONE_WORD, generate



# ───────────────────────── PDF ─────────────────────────


def notes_pdf(student, fake_ai):
    fake_ai["replies"]["notes app"] = chat(STRUCTURE)
    fake_ai["replies"]["You write revision notes"] = chat(GENERATED)
    n = make_notes(student).json()["data"]
    return student.get(f"/api/notes/{n['id']}/pdf")


def test_pdf_is_made_with_reportlab(student, fake_ai):
    assert pdf_service.library() == "reportlab"
    r = notes_pdf(student, fake_ai)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content.startswith(b"%PDF") and b"ReportLab" in r.content[:400]
    assert r.headers["content-disposition"] == 'attachment; filename="HamSTAR_Notes_Photosynthesis.pdf"'


def test_pdf_falls_back_to_fpdf2_and_reports_clearly_when_nothing_can_be_installed(student, fake_ai, monkeypatch):
    monkeypatch.setattr(pdf_service, "_available", lambda: "fpdf2")
    r = notes_pdf(student, fake_ai)
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and b"ReportLab" not in r.content[:400]

    tried = []
    monkeypatch.setattr(pdf_service, "_available", lambda: None)
    monkeypatch.setattr(pdf_service, "_install", lambda: tried.append(1))
    r = notes_pdf(student, fake_ai)
    assert tried == [1] and r.status_code == 503 and r.json()["error"]["code"] == "PDF_UNAVAILABLE" and "pip install reportlab" in r.json()["error"]["message"]


# ───────────────────────── deleting folders ─────────────────────────


def remove(student, **body):
    return student.post("/api/folders/delete", body)


def test_delete_a_subfolder_then_a_parent_folder_with_everything_inside(student, other, fake_ai):
    fake_ai["replies"]["filled in a blank"] = BLANK_JUDGE
    a = put(student, name="a.txt", subject="Physics")
    put(student, name="b.txt", subject="Physics")
    c = put(student, name="c.txt", subject="Chemistry")
    put(other, name="theirs.txt", subject="Physics")
    fake_ai["replies"]["You write exam questions"] = chat({"questions": [{**ONE_WORD, "topic": "Light"}]})
    q = student.data(generate(student, a["id"], "ONE_WORD", 1))["questions"][0]
    student.post("/api/attempts/evaluate", {"question_id": q["id"], "answer": "water"})
    student.post("/api/attempts/evaluate", {"question_id": q["id"], "answer": "sand"})
    assert student.data(student.get("/api/recurring-mistakes"))["recurring"]

    r = student.data(remove(student, parent="Science", subfolder="physics"))
    science = next(f for f in r["folders"] if f["name"] == "Science")
    assert r["removed"] == 2 and [s["name"] for s in science["subfolders"]] == ["Chemistry"]
    # the documents, their questions, the answers and the mistake log are gone
    assert student.get(f"/api/study-materials/{a['id']}").status_code == 404 and student.get(f"/api/questions/{q['id']}").status_code == 404
    with SessionLocal() as db:
        assert not db.query(Attempt).filter(Attempt.user_id == student.id).count() and not db.query(MistakeLog).filter(MistakeLog.user_id == student.id).count()
        assert not db.query(Question).filter(Question.study_material_id == a["id"]).count()
    assert student.data(student.get("/api/recurring-mistakes"))["recurring"] == []

    r = student.data(remove(student, parent="Science"))
    assert r["removed"] == 1 and "Science" not in [f["name"] for f in r["folders"]] and student.get(f"/api/study-materials/{c['id']}").status_code == 404
    # someone else's folder of the same name is untouched
    assert folder(other, "Science")["document_count"] == 1
    assert remove(student, parent="Science").json()["error"]["code"] == "FOLDER_NOT_FOUND"


def test_deleting_a_starter_folder_erases_progress_and_hides_it_until_restored(student, other):
    (q1, o1), (q2, o2) = adding_across()[:2]
    student.answer(q1["id"], o1)
    student.answer(q2["id"], o2)
    r = student.data(remove(student, parent="Maths", subfolder="Fractions"))
    maths = next(f for f in r["folders"] if f["name"] == "Maths")
    assert r["removed"] == 1 and [s["name"] for s in maths["subfolders"]] == ["Algebra"] and r["hidden_starters"] == 1
    assert student.data(student.get("/api/recurring-mistakes")) == {"recurring": [], "patterns": [], "logged": 0}
    # the shared questions themselves still exist for everyone else
    assert sorted(s["name"] for s in folder(other, "Maths")["subfolders"]) == ["Algebra", "Fractions"]

    r = student.data(remove(student, parent="Maths"))
    assert r["folders"] == [] and r["hidden_starters"] == 2
    back = student.data(student.post("/api/folders/restore-starters"))
    assert back["restored"] == 2 and back["hidden_starters"] == 0
    fractions = next(s for s in back["folders"][0]["subfolders"] if s["name"] == "Fractions")["documents"][0]
    assert fractions["answered"] == 0 and student.data(student.get("/api/questions/next?topic=fractions"))["number"] == 1


# ───────────────────────── verified maths answers ─────────────────────────

WRONG_KEY = {"question": "Simplify: -(4-3x)+2x", "expected_answer": "x+4", "accepted_answers": ["4+x"], "explanation": "Combine terms.", "topic": "Brackets"}
FIXED = {"number": 1, "working": "-(4-3x)+2x = -4+3x+2x = 5x-4.", "final_answer": "5x-4", "proposed_is_correct": False}


def test_a_wrong_maths_answer_key_is_corrected_before_it_is_stored(student, fake_ai):
    m = put(student, subject="Algebra")
    seen = []

    def check(prompt):
        seen.append(prompt)
        return chat({"results": [FIXED]})

    fake_ai["replies"]["You write exam questions"] = chat({"questions": [WRONG_KEY]})
    fake_ai["replies"]["You check the answer keys"] = check
    q = student.data(generate(student, m["id"], "ONE_WORD", 1))["questions"][0]
    assert "Question: Simplify: -(4-3x)+2x" in seen[0] and "Proposed answer: x+4" in seen[0] and "distribute signs first" in seen[0] and "step by step" in seen[0]
    # the student's correct answer is now marked correct, and the old wrong key is not
    right = student.data(student.post("/api/attempts/evaluate", {"question_id": q["id"], "answer": "5x - 4"}))
    assert right["is_correct"] and right["expected_answer"] == "5x-4" and "-4+3x+2x" in right["feedback"]
    assert len(seen) == 1  # verified once, when it was written
    fake_ai["replies"]["filled in a blank"] = BLANK_JUDGE
    assert not student.data(student.post("/api/attempts/evaluate", {"question_id": q["id"], "answer": "x+4"}))["is_correct"]


def test_generation_prompt_asks_for_checked_maths(student, fake_ai):
    m = put(student, subject="Algebra")
    seen = []
    fake_ai["replies"]["You write exam questions"] = lambda p: seen.append(p) or chat({"questions": [ONE_WORD]})
    generate(student, m["id"], "ONE_WORD", 1)
    assert "always verify mathematical answers step by step" in seen[0] and "distribute signs first, collect like terms, then double-check the final result" in seen[0]
    assert ("groq", "/chat/completions") not in fake_ai["calls"]  # not a maths question: no check needed


def test_mcq_with_a_wrong_key_is_rekeyed_or_dropped(student, fake_ai):
    m = put(student, subject="Algebra")
    item = {"question": "Simplify: -(4-3x)+2x", "options": ["x+4", "5x-4", "5x+4", "x-4"], "correct_option": "A", "explanation": "", "wrong_option_diagnosis": {"B": "Sign slip", "C": "Kept the plus"}, "topic": "Brackets"}
    hopeless = {**item, "question": "What is 7 * 8?", "options": ["54", "58", "48", "64"], "correct_option": "A", "wrong_option_diagnosis": {}}
    fake_ai["replies"]["You write exam questions"] = chat({"questions": [item, hopeless]})
    fake_ai["replies"]["You check the answer keys"] = chat({"results": [FIXED, {"number": 2, "working": "7*8 = 56.", "final_answer": "56", "proposed_is_correct": False}]})
    qs = student.data(generate(student, m["id"], "MCQ", 1, n=2))["questions"]
    assert len(qs) == 1  # no option of the second question is right, so it is never asked
    r = student.answer(qs[0]["id"], "B")
    assert r["is_correct"] and [o["id"] for o in r["question"]["options"] if o["correct"]] == ["B"]


def test_questions_stored_before_the_check_are_verified_on_first_use(student, fake_ai):
    from app.services.ai_client import ProviderError

    def down(_):
        raise ProviderError("groq", "down")

    m = put(student, subject="Algebra")
    fake_ai["replies"]["You write exam questions"] = chat({"questions": [WRONG_KEY]})
    fake_ai["replies"]["You check the answer keys"] = down
    q = student.data(generate(student, m["id"], "ONE_WORD", 1))["questions"][0]  # stored unverified, as older questions were
    fake_ai["replies"]["You check the answer keys"] = chat({"results": [FIXED]})
    student.data(student.get(f"/api/questions/next?material_id={m['id']}&question_type=ONE_WORD"))
    calls = len(fake_ai["calls"])
    assert student.data(student.post("/api/attempts/evaluate", {"question_id": q["id"], "answer": "5x-4"}))["is_correct"]
    assert len(fake_ai["calls"]) == calls  # already verified when it was shown


# ───────────────────────── tasks, deadlines, reminders ─────────────────────────


def add(student, title, hours=None, **extra):
    body = {"title": title, "topic": "Maths", **extra}
    if hours is not None:
        body["deadline"] = (now() + timedelta(hours=hours)).isoformat()
    return student.data(student.post("/api/tasks", body))


def patch(student, task_id, **body):
    return student.data(student.client.patch(f"/api/tasks/{task_id}", headers=student.headers, json=body))


def test_tasks_belong_to_the_account_and_deadlines_are_optional(student, other):
    plain = add(student, "  Revise fractions  ")
    dated = add(student, "Finish worksheet", hours=48, starred=True)
    assert plain["title"] == "Revise fractions" and plain["deadline"] is None and not plain["done"] and not plain["reminder_sent"]
    assert dated["deadline"].endswith("+00:00") and dated["starred"]
    listed = student.data(student.get("/api/tasks"))
    assert [t["id"] for t in listed["tasks"]] == [plain["id"], dated["id"]] and listed["reminders"] is False
    assert student.data(other.get("/api/tasks"))["tasks"] == []
    assert patch(student, plain["id"], done=True, starred=True)["done"]
    assert other.client.patch(f"/api/tasks/{plain['id']}", headers=other.headers, json={"done": False}).json()["error"]["code"] == "TASK_NOT_FOUND"
    assert patch(student, dated["id"], deadline=None)["deadline"] is None
    assert student.data(student.client.delete(f"/api/tasks/{plain['id']}", headers=student.headers)) == {"deleted": plain["id"]}
    assert student.post("/api/tasks", {"title": ""}).status_code == 422


def run_reminders():
    with SessionLocal() as db:
        return reminder_service.send_due(db)


def test_one_reminder_goes_out_the_day_before_and_only_for_unfinished_tasks(student, outbox):  # noqa: F811
    soon = add(student, "Algebra worksheet", hours=20)
    finished = add(student, "Already done", hours=20)
    patch(student, finished["id"], done=True)
    add(student, "Next week", hours=24 * 6)
    add(student, "No deadline")
    add(student, "Missed it", hours=-3)

    run_reminders()
    mine = [m for m in outbox if m["to"] == student.email]
    assert len(mine) == 1 and mine[0]["subject"] == "⏰ HamSTAR Reminder: Algebra worksheet is due tomorrow!"
    assert "Algebra worksheet" in mine[0]["text"] and "hamster" in mine[0]["text"] and "#/tasks" in mine[0]["html"]
    listed = student.data(student.get("/api/tasks"))
    assert next(t for t in listed["tasks"] if t["id"] == soon["id"])["reminder_sent"] and listed["reminders"] is True

    # never a second email for the same task
    run_reminders()
    run_reminders()
    assert len([m for m in outbox if m["to"] == student.email]) == 1
    # moving the deadline arms the reminder again for the new date
    assert not patch(student, soon["id"], deadline=(now() + timedelta(hours=10)).isoformat())["reminder_sent"]
    run_reminders()
    assert len([m for m in outbox if m["to"] == student.email]) == 2


def test_a_failed_send_is_retried_and_nothing_is_sent_without_email_settings(student, monkeypatch):
    from app.core.errors import ApiError
    from app.services import email_service

    t = add(student, "Chemistry notes", hours=5)
    assert run_reminders() == 0  # email is not configured in this test
    s = get_settings()
    for k, v in {"smtp_host": "smtp.test", "smtp_user": "u", "smtp_password": "p"}.items():
        monkeypatch.setattr(s, k, v)

    def broken(*a, **k):
        raise ApiError("EMAIL_FAILED", "down", 502)

    monkeypatch.setattr(email_service, "send", broken)
    run_reminders()
    with SessionLocal() as db:
        assert db.get(Task, t["id"]).reminder_sent is False  # still owed: the next hourly run tries again


def test_the_hourly_job_is_scheduled(monkeypatch):
    assert reminder_service.start() is None  # switched off for tests
    monkeypatch.setattr(get_settings(), "reminders_enabled", True)
    scheduler = reminder_service.start()
    try:
        assert scheduler.get_job("task-reminders").trigger.interval == timedelta(hours=1)
    finally:
        scheduler.shutdown(wait=False)
