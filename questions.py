from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.errors import ApiError, ok
from ..core.security import current_user
from ..models import MARK_RULES, StudyMaterial, User
from ..schemas.requests import Envelope, QuestionGenerationRequest, RestartRequest
from ..services import answer_evaluation_service, bank_service, question_generation_service, verification_service
from .deps import AUTH_ERRORS, own_material, visible_question

router = APIRouter(prefix="/api/questions", tags=["Questions"], responses=AUTH_ERRORS)


@router.post("/generate", response_model=Envelope, status_code=201, summary="Generate questions from uploaded material (Mistral)",
             responses={422: {"description": "INVALID_QUESTION_TYPE or INVALID_MARKS"}, 409: {"description": "DOCUMENT_PROCESSING_FAILED"}, 503: {"description": "QUESTION_GENERATION_FAILED"}})
def generate(body: QuestionGenerationRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """
    Marks allowed per type: ONE_WORD 1 · FILL_BLANK 1-2 · MCQ 1 · SHORT_ANSWER 4-8 · LONG_ANSWER 12-20.
    Pass `study_material_id` for an upload, or `folder` for a starter folder.
    Questions are written only from the material and validated before they are stored.
    """
    question_generation_service.check_marks(body.question_type, body.marks)
    if body.study_material_id:
        material = own_material(db, user, body.study_material_id)
    elif body.folder and bank_service.is_bank_topic(body.folder):
        material = bank_service.starter_material(db, user, body.folder)
    else:
        raise ApiError("STUDY_MATERIAL_NOT_FOUND", "Choose a folder to write questions for.", 404)
    rows = question_generation_service.generate(db, user, material, body.question_type, body.marks, body.number_of_questions, body.difficulty, body.topic)
    return ok({"questions": [bank_service.public(q) for q in rows], "study_material_id": material.id})


@router.get("/next", response_model=Envelope, summary="The next question in a folder", responses={404: {"description": "QUESTION_NOT_FOUND"}})
def next_question(topic: str | None = Query(default=None, description="A folder from the verified bank (see /api/progress for their ids)"), material_id: str | None = Query(default=None), question_type: str = Query(default="MCQ", description="ONE_WORD, FILL_BLANK, MCQ, SHORT_ANSWER or LONG_ANSWER"), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """
    Returns the next question of the chosen type, without its answer key. When every question in the set has been
    done it returns `completed: true` with a `summary` (attempted, correct, wrong, score) instead of looping back. Pass either a bank `topic` or a `material_id`.
    `NO_QUESTIONS_OF_TYPE` means none have been written yet: call `/api/questions/generate` for that type first.
    """
    if question_type not in MARK_RULES:
        raise ApiError("INVALID_QUESTION_TYPE", f"Question type must be one of {', '.join(MARK_RULES)}.", 422)
    if material_id:
        own_material(db, user, material_id)
        key = f"material:{material_id}"
    elif topic and bank_service.is_bank_topic(topic):
        # the verified bank is multiple choice; the folder's other types live in its starter material
        key = topic if question_type == "MCQ" else f"material:{bank_service.starter_material(db, user, topic).id}"
        db.commit()
    else:
        raise ApiError("QUESTION_NOT_FOUND", "Choose a folder to learn from.", 404)
    # the document these questions belong to: a question from another document never appears here
    material = db.get(StudyMaterial, key.split(":", 1)[1]) if key.startswith("material:") else None
    document = {"id": key if material is None or material.file_type != "starter" else topic, "title": material.title if material else topic, "file_name": material.file_name if material and material.file_type != "starter" else None}
    key = answer_evaluation_service.folder_key(key, question_type)
    questions = answer_evaluation_service.question_list(db, user, key)
    if not questions:
        raise ApiError("NO_QUESTIONS_OF_TYPE", "There are no questions of this type in this folder yet.", 404)
    i = (user.cursors or {}).get(key, 0)
    if i >= len(questions):
        # every question in this set has been done: report the result, do not start again from the first
        return ok({"completed": True, "question": None, "number": len(questions), "total": len(questions), "folder": key, "document": document, "summary": answer_evaluation_service.completion(db, user, key)})
    # a maths question stored before answers were verified gets its check now, before it is shown
    verification_service.ensure(db, questions[i])
    return ok({"completed": False, "question": bank_service.public(questions[i]), "number": i + 1, "total": len(questions), "folder": key, "document": document})


@router.post("/restart", response_model=Envelope, summary="Go through a completed set again", responses={404: {"description": "QUESTION_NOT_FOUND"}})
def restart(body: RestartRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Puts the position of one folder and question type back to its first question. Past attempts are kept."""
    if body.material_id:
        own_material(db, user, body.material_id)
        key = f"material:{body.material_id}"
    elif body.topic and bank_service.is_bank_topic(body.topic):
        key = body.topic if body.question_type == "MCQ" else f"material:{bank_service.starter_material(db, user, body.topic).id}"
    else:
        raise ApiError("QUESTION_NOT_FOUND", "Choose a folder to learn from.", 404)
    answer_evaluation_service.restart(db, user, answer_evaluation_service.folder_key(key, body.question_type))
    return ok({"restarted": True})


@router.get("/{question_id}", response_model=Envelope, summary="One question (without its answer)", responses={404: {"description": "QUESTION_NOT_FOUND"}, 403: {"description": "FORBIDDEN"}})
def get_question(question_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok(bank_service.public(visible_question(db, user, question_id)))
