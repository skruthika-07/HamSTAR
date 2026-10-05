from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import get_db
from ..core.errors import ApiError, ok
from ..core.security import current_user
from ..models import User
from ..schemas.requests import Envelope
from ..services import notes_service
from .deps import AUTH_ERRORS

router = APIRouter(prefix="/api/notes", tags=["Notes generator"], responses=AUTH_ERRORS)


@router.post("", response_model=Envelope, status_code=201, summary="Generate structured notes from an uploaded file",
             responses={413: {"description": "FILE_TOO_LARGE"}, 415: {"description": "INVALID_FILE_TYPE"}, 422: {"description": "DOCUMENT_PROCESSING_FAILED"}, 503: {"description": "AI_PROVIDER_ERROR"}})
async def create(file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """
    Mistral reads the file (text, headings, definitions); Groq writes the notes, always in the same sections:
    headings and subheadings, definitions, summary, must-know keywords, key points, topic weightage, concept hierarchy,
    core concepts, potential questions and a brief summary. The notes are saved to the account.
    """
    limit = get_settings().max_upload_size_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise ApiError("FILE_TOO_LARGE", f"Files can be at most {get_settings().max_upload_size_mb} MB.", 413)
    return ok(notes_service.view(notes_service.create(db, user, file.filename or "file", file.content_type, data)))


@router.get("", response_model=Envelope, summary="Your saved notes, newest first")
def listing(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok(notes_service.listing(db, user))


@router.get("/{note_id}", response_model=Envelope, summary="One set of notes", responses={404: {"description": "NOTE_NOT_FOUND"}})
def get_note(note_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return ok(notes_service.view(notes_service.own(db, user, note_id)))


@router.get("/{note_id}/pdf", summary="Download the notes as a formatted PDF (HamSTAR_Notes_<Topic>.pdf)", responses={404: {"description": "NOTE_NOT_FOUND"}, 200: {"content": {"application/pdf": {}}}})
def get_pdf(note_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    note = notes_service.own(db, user, note_id)
    return Response(notes_service.pdf(note), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{notes_service.pdf_name(note)}"'})


@router.delete("/{note_id}", response_model=Envelope, summary="Delete saved notes", responses={404: {"description": "NOTE_NOT_FOUND"}})
def delete_note(note_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(notes_service.own(db, user, note_id))
    db.commit()
    return ok({"deleted": note_id})
