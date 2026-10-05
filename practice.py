from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.errors import ApiError, ok
from ..core.security import current_user
from ..models import User
from ..schemas.requests import Envelope, FolderDelete, FolderRename
from ..services import folder_service, mistake_service
from .deps import AUTH_ERRORS

router = APIRouter(prefix="/api", tags=["Folders, weakness and recurring mistakes"], responses=AUTH_ERRORS)


@router.get("/folders", response_model=Envelope, summary="Parent folders, subfolders and documents with confidence and weakness")
def folders(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """
    Every folder and document carries a confidence score: the share of its questions answered correctly, weighted by
    question type (one-mark and multiple choice 1, brief 2, detailed 3), starting from a neutral prior. Documents are
    sorted weakest first; `weak` marks the ones worth improving, and `weakest` names a parent folder's weakest subfolder.
    """
    return ok(folder_service.tree(db, user))


@router.post("/folders/rename", response_model=Envelope, summary="Rename a parent folder or a subfolder", responses={404: {"description": "FOLDER_NOT_FOUND"}, 422: {"description": "INVALID_FOLDER_NAME"}})
def rename_folder(body: FolderRename, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """
    Give `parent` and `name` to rename a parent folder; add `subfolder` to rename that subfolder instead. Every document
    in it moves with the name, the starter sets included. Returns the folders as they now stand.
    """
    moved = folder_service.rename(db, user, body.parent, body.subfolder, body.name)
    return ok({"moved": moved, **folder_service.tree(db, user)})


@router.post("/folders/delete", response_model=Envelope, summary="Delete a parent folder or a subfolder, with everything in it", responses={404: {"description": "FOLDER_NOT_FOUND"}})
def delete_folder(body: FolderDelete, user: User = Depends(current_user), db: Session = Depends(get_db)):
    """
    Deletes the documents in the folder, their files, the questions written from them and your answers, diagnoses and
    mistake log for them. This cannot be undone. A starter set is hidden rather than destroyed (your progress on it is
    erased); `POST /api/folders/restore-starters` brings it back fresh. Returns the folders as they now stand.
    """
    removed = folder_service.delete(db, user, body.parent, body.subfolder)
    return ok({"removed": removed, **folder_service.tree(db, user)})


@router.post("/folders/restore-starters", response_model=Envelope, summary="Bring back deleted starter sets")
def restore_starters(user: User = Depends(current_user), db: Session = Depends(get_db)):
    restored = folder_service.restore_starters(db, user)
    return ok({"restored": restored, **folder_service.tree(db, user)})


@router.get("/recurring-mistakes", response_model=Envelope, summary="Concepts and kinds of mistake that keep coming back")
def recurring(user: User = Depends(current_user), db: Session = Depends(get_db)):
    """A concept is recurring once it has gone wrong twice or more; two correct answers on it clear it."""
    return ok(mistake_service.summary(db, user))


@router.get("/practice", response_model=Envelope, summary="A focused set of questions: one concept (mini-drill) or one document",
            responses={404: {"description": "NOTHING_TO_DRILL or STUDY_MATERIAL_NOT_FOUND"}, 422: {"description": "INVALID_PRACTICE"}})
def practice(concept: str | None = Query(default=None, max_length=120), document: str | None = Query(default=None, max_length=60, description='A starter folder id, or "material:<id>"'), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """Answer these through `/api/attempts/evaluate` with `practice: true`, so the folder's own position does not move."""
    if concept:
        return ok(mistake_service.drill(db, user, concept))
    if document:
        return ok(mistake_service.practice(db, user, document))
    raise ApiError("INVALID_PRACTICE", "Say what to practise: a concept or a document.", 422)
