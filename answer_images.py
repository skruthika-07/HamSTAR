from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.errors import ApiError, ok
from ..core.security import current_user
from ..models import User
from ..schemas.requests import Envelope
from ..services import answer_image_service
from .deps import AUTH_ERRORS

router = APIRouter(prefix="/api/answer-images", tags=["Answer photos"], responses=AUTH_ERRORS)


@router.post("", response_model=Envelope, status_code=201, summary="Upload a photo to send with an answer",
             responses={413: {"description": "FILE_TOO_LARGE"}, 415: {"description": "INVALID_FILE_TYPE"}})
async def upload(file: UploadFile = File(...), user: User = Depends(current_user), db: Session = Depends(get_db)):
    """
    A photo of working, a diagram or a solution (PNG, JPG or WebP, up to 8 MB). Pass the returned `id` as `image_id`
    to `/api/attempts/evaluate` to store it with that answer. The photo is kept as it is: it is not read or marked.
    """
    data = await file.read(answer_image_service.MAX_MB * 1024 * 1024 + 1)
    return ok(answer_image_service.view(answer_image_service.store(db, user, file.filename or "photo.jpg", file.content_type, data)))


@router.get("/{image_id}", summary="One of your answer photos", responses={404: {"description": "IMAGE_NOT_FOUND"}, 200: {"content": {"image/*": {}}}})
def get_image(image_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    row = answer_image_service.own(db, user, image_id)
    if not Path(row.file_path).exists():
        raise ApiError("IMAGE_NOT_FOUND", "That photo was not found.", 404)
    return FileResponse(row.file_path, media_type=row.mime)
