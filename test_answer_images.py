"""Photos sent with answers: stored with the submission, shown back, never read."""
from tests.conftest import chat
from tests.test_folders_mistakes_notes import put
from tests.test_materials_and_ai import ONE_WORD, generate

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def photo(student, name="working.png", data=PNG, mime="image/png"):
    return student.client.post("/api/answer-images", headers=student.headers, files={"file": (name, data, mime)})


def test_a_photo_is_stored_with_the_answer_and_shown_back_without_being_read(student, other, fake_ai):
    m = put(student, subject="Biology")
    fake_ai["replies"]["You write exam questions"] = chat({"questions": [ONE_WORD]})
    q = student.data(generate(student, m["id"], "ONE_WORD", 1))["questions"][0]
    img = student.data(photo(student))
    assert img["url"] == f"/api/answer-images/{img['id']}"
    calls = len(fake_ai["calls"])
    r = student.data(student.post("/api/attempts/evaluate", {"question_id": q["id"], "answer": "chlorophyll", "image_id": img["id"]}))
    assert r["is_correct"] and r["image"]["id"] == img["id"]
    assert len(fake_ai["calls"]) == calls  # nothing looked at the photo
    got = student.get(img["url"])
    assert got.status_code == 200 and got.headers["content-type"] == "image/png" and got.content == PNG
    assert student.data(student.get("/api/attempts/history"))[0]["image"]["id"] == img["id"]
    # it belongs to that answer, and to that student
    q2 = student.data(student.get(f"/api/questions/{q['id']}"))
    assert student.post("/api/attempts/evaluate", {"question_id": q2["id"], "answer": "x", "image_id": img["id"]}).json()["error"]["code"] == "IMAGE_ALREADY_USED"
    assert other.get(img["url"]).status_code == 404
    assert other.post("/api/attempts/evaluate", {"question_id": "f1", "selected_option": "B", "image_id": img["id"]}).json()["error"]["code"] == "IMAGE_NOT_FOUND"


def test_only_photos_are_accepted(student):
    assert photo(student, name="notes.txt", data=b"hello", mime="text/plain").json()["error"]["code"] == "INVALID_FILE_TYPE"
    assert photo(student, data=b"not really a png").json()["error"]["code"] == "INVALID_FILE_TYPE"
    assert student.client.post("/api/answer-images", files={"file": ("w.png", PNG, "image/png")}).status_code == 401


def test_handwriting_reading_is_gone(student):
    assert student.client.post("/api/ocr/handwriting", headers=student.headers, files={"file": ("w.png", PNG, "image/png")}).status_code == 404
