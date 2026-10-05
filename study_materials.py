from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import get_db
from ..core.errors import ApiError, ok
from ..core.security import current_user
from ..models import StudyMaterial, User
from ..schemas.requests import Envelope, MaterialPatch
from ..services import document_service, folder_service
from .deps import AUTH_ERRORS, own_material

router = APIRouter(prefix="/api/study-materials", tags=["Study materials"], responses=AUTH_ERRORS)


def _view(db: Session, user: User, m: StudyMaterial) -> dict:
    return document_service.view(m, len([q for q in m.questions if q.role == "main"]))


@router.post("/upload", response_model=Envelope, status_code=201, summary="Upload study material",
             responses={413: {"description": "FILE_TOO_LARGE"}, 415: {"description": "INVALID_FILE_TYPE"}})
async def upload(file: UploadFile = File(...), topic: str | None = Form(default=None), subject: str | None = Form(default=None, max_length=80), parent: str | None = Form(default=None, max_length=80), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """
    Accepts a PDF, PowerPoint, image or notes file. PDFs, slides and images are read with Mistral OCR;
    plain-text notes are read directly. Every document sits in a parent folder (`parent`, e.g. Science) and a subfolder
    inside it (`subject`, e.g. Physics); several documents can share a subfolder. Pass them to choose yourself, otherwise
    both are detected. When it cannot be detected `subject_detected` is false and the material is filed under "General" until
    a subject is set with PATCH. If reading fails the material is still stored, with
    `processing_status: FAILED` and the reason, so the upload is not lost.
    """
    limit = get_settings().max_upload_size_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise ApiError("FILE_TOO_LARGE", f"Files can be at most {get_settings().max_upload_size_mb} MB.", 413)
    m = document_service.store_and_process(db, user, file.filename or "file", file.content_type, data, topic, subject, parent)
    return ok(_view(db, user, m))


@router.get("", response_model=Envelope, summary="List your study materials")
def list_materials(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(StudyMaterial).where(StudyMaterial.user_id == user.id, StudyMaterial.file_type != "starter").order_by(StudyMaterial.created_at.desc())).all()
    return ok([_view(db, user, m) for m in rows])


@router.get("/{material_id}", response_model=Envelope, summary="One study material", responses={404: {"description": "STUDY_MATERIAL_NOT_FOUND"}, 403: {"description": "FORBIDDEN"}})
def get_material(material_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok(_view(db, user, own_material(db, user, material_id)))


@router.patch("/{material_id}", response_model=Envelope, summary="Move a study material: set its subfolder (subject) and parent folder", responses={404: {"description": "STUDY_MATERIAL_NOT_FOUND"}, 403: {"description": "FORBIDDEN"}})
def patch_material(material_id: str, body: MaterialPatch, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Any subject name is valid. Questions already written from this material move to the new subject with it."""
    m = own_material(db, user, material_id)
    m.subject = document_service.clean_subject(body.subject)
    # the parent folder: as chosen, else where this subject belongs, else where the document already was
    m.parent_subject = folder_service.clean_parent(body.parent) or folder_service.parent_of(m.subject) or m.parent_subject or folder_service.OTHER
    for q in m.questions:
        q.topic = (m.subject or document_service.GENERAL)[:80]
    db.commit()
    return ok(_view(db, user, m))


@router.delete("/{material_id}", response_model=Envelope, summary="Delete a study material and its generated questions", responses={404: {"description": "STUDY_MATERIAL_NOT_FOUND"}, 403: {"description": "FORBIDDEN"}})
def delete_material(material_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    m = own_material(db, user, material_id)
    document_service.delete_file(m)
    db.delete(m)
    db.commit()
    return ok({"deleted": material_id})
