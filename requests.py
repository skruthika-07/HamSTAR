"""Everything the API accepts from outside is validated here first."""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

Avatar = Literal["graduate", "reader", "cool", "royal", "music", "sleepy", "explorer", "coder"]


class Envelope(BaseModel):
    """Every response: {"success": true, "data": ...} or {"success": false, "error": {"code", "message"}}."""

    success: bool = True
    data: Any = None


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)
    name: str | None = Field(default=None, max_length=80)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or v.startswith("@") or v.endswith("@") or " " in v:
            raise ValueError("enter a valid email address")
        return v


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.strip().lower()


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.strip().lower()


class ResetPasswordRequest(ForgotPasswordRequest):
    code: str = Field(min_length=4, max_length=12)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("code")
    @classmethod
    def _code(cls, v: str) -> str:
        return "".join(v.split())


class FolderRename(BaseModel):
    parent: str = Field(min_length=1, max_length=80, description="The parent folder (to rename it, or to say where the subfolder is)")
    subfolder: str | None = Field(default=None, max_length=80, description="The subfolder to rename; omit to rename the parent folder itself")
    name: str = Field(min_length=1, max_length=80, description="The new name")


class FolderDelete(BaseModel):
    parent: str = Field(min_length=1, max_length=80)
    subfolder: str | None = Field(default=None, max_length=80, description="The subfolder to delete; omit to delete the whole parent folder")


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    topic: str = Field(default="General", max_length=80)
    starred: bool = False
    deadline: datetime | None = Field(default=None, description="Optional. ISO 8601; a time without a zone is taken as UTC")


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    topic: str | None = Field(default=None, max_length=80)
    done: bool | None = None
    starred: bool | None = None
    # send null to remove the deadline
    deadline: datetime | None = None


class ProfilePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    role: str | None = Field(default=None, max_length=80)
    avatar: Avatar | None = None


class MaterialPatch(BaseModel):
    subject: str = Field(min_length=1, max_length=80, description="The subfolder: any subject or subtopic, e.g. Physics or Data Structures")
    parent: str | None = Field(default=None, max_length=80, description="The parent folder, e.g. Science. Worked out from the subject when omitted")


class QuestionGenerationRequest(BaseModel):
    study_material_id: str | None = None
    # a starter folder id, as an alternative to a material
    folder: str | None = Field(default=None, max_length=80)
    question_type: str = "MCQ"
    marks: int = 1
    number_of_questions: int = Field(default=10, ge=1, le=20)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    topic: str = Field(default="", max_length=120)


class EvaluateRequest(BaseModel):
    question_id: str
    answer: str | None = Field(default=None, max_length=20000)
    selected_option: str | None = Field(default=None, max_length=2)
    reasoning: str | None = Field(default=None, max_length=4000)
    # sent by the client so that a repeated request is recognised and not rewarded twice
    client_key: str | None = Field(default=None, max_length=64)
    # focused practice and drills: the answer counts, but the folder's own position does not move
    practice: bool = False
    # a photo uploaded to /api/answer-images, stored with this answer and shown beside it
    image_id: str | None = Field(default=None, max_length=32)


class ExplainRequest(BaseModel):
    # 0 = the first, plain explanation; 1, 2, … = simpler each time, with an everyday example
    level: int = Field(default=0, ge=0, le=6)
    # for a diagnosis: which of its questions to explain (the original one when omitted)
    question_id: str | None = None


class AttemptFollowUpAnswer(BaseModel):
    question_id: str
    selected_option: str = Field(min_length=1, max_length=2)


class RestartRequest(BaseModel):
    topic: str | None = None
    material_id: str | None = None
    question_type: str = "MCQ"


class AttemptRequest(BaseModel):
    question_id: str
    skipped: bool = True
    client_key: str | None = Field(default=None, max_length=64)
    practice: bool = False


class DiagnosticCreate(BaseModel):
    attempt_id: str


class ReasoningRequest(BaseModel):
    reasoning: str = Field(min_length=1, max_length=4000)


class FollowUpAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=2, description="The option chosen: A, B, C or D")
    reasoning: str | None = Field(default=None, max_length=4000)

    @field_validator("answer")
    @classmethod
    def _letter(cls, v: str) -> str:
        return v.strip().upper()


class RetryAnswer(BaseModel):
    question_id: str
    selected_option: str = Field(min_length=1, max_length=2)


class EvaluationRunRequest(BaseModel):
    students: int = Field(default=400, ge=20, le=2000)
    seed: int = Field(default=7, ge=0, le=1_000_000)


class DemoRequest(BaseModel):
    action: Literal["load", "reset", "add_tiara"]
    amount: int = Field(default=50, ge=1, le=500)



