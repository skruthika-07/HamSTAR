"""
Photos students attach to an answer: their working, a diagram, a worked solution. They are stored with the
submission and shown next to the typed answer when it is reviewed. Nothing reads them: no OCR, no AI.
"""
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.errors import ApiError
from ..models import AnswerImage, Attempt, User
from ..models.base import new_id
from . import document_service

MAX_MB = 8
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def store(db: Session, user: User, filename: str, content_type: str | None, data: bytes) -> AnswerImage:
    if len(data) > MAX_MB * 1024 * 1024:
        raise ApiError("FILE_TOO_LARGE", f"Photos can be at most {MAX_MB} MB.", 413)
    ext, kind = document_service.validate(filename or "photo.jpg", content_type, data)
    if kind != "image":
        raise ApiError("INVALID_FILE_TYPE", "Upload a photo (PNG, JPG or WebP).", 415)
    # stored under a generated name inside the upload directory, never under a name the user chose
    root = Path(get_settings().upload_dir).resolve()
    folder = root / user.id / "answers"
    folder.mkdir(parents=True, exist_ok=True)
    path = (folder / f"{new_id()}{ext}").resolve()
    if root not in path.parents:
        raise ApiError("INVALID_FILE_TYPE", "Invalid file name.", 400)
    path.write_bytes(data)
    row = AnswerImage(user_id=user.id, file_path=str(path), mime=MIME[ext], file_size=len(data), file_name=document_service.safe_name(filename))
    db.add(row)
    db.commit()
    return row


def own(db: Session, user: User, image_id: str) -> AnswerImage:
    row = db.get(AnswerImage, image_id)
    if not row or row.user_id != user.id:
        raise ApiError("IMAGE_NOT_FOUND", "That photo was not found.", 404)
    return row


def check(db: Session, user: User, image_id: str, client_key: str | None) -> None:
    """Before an answer is marked: the photo is the student's and not already sent with another answer
    (the same submission sent twice may carry it again)."""
    row = own(db, user, image_id)
    if row.attempt_id and not (client_key and (a := db.get(Attempt, row.attempt_id)) and a.client_key == client_key):
        raise ApiError("IMAGE_ALREADY_USED", "That photo was already sent with another answer.", 409)


def attach(db: Session, user: User, image_id: str, attempt_id: str) -> dict:
    """Link a photo to the answer it was sent with. A photo belongs to one answer only."""
    row = own(db, user, image_id)
    if row.attempt_id not in (None, attempt_id):
        raise ApiError("IMAGE_ALREADY_USED", "That photo was already sent with another answer.", 409)
    row.attempt_id = attempt_id
    attempt = db.get(Attempt, attempt_id)
    attempt.evaluation = {**(attempt.evaluation or {}), "image": view(row)}
    db.commit()
    return view(row)


def view(row: AnswerImage) -> dict:
    return {"id": row.id, "url": f"/api/answer-images/{row.id}", "file_name": row.file_name, "mime": row.mime}


def for_attempt(db: Session, attempt_id: str) -> dict | None:
    row = db.scalar(select(AnswerImage).where(AnswerImage.attempt_id == attempt_id))
    return view(row) if row else None


def delete_files(db: Session, attempt_ids: list[str]) -> None:
    """Remove the stored photos of answers that are being deleted (their rows go with the answers)."""
    if not attempt_ids:
        return
    root = Path(get_settings().upload_dir).resolve()
    for row in db.scalars(select(AnswerImage).where(AnswerImage.attempt_id.in_(attempt_ids))):
        path = Path(row.file_path).resolve()
        if root in path.parents and path.exists():
            path.unlink()
