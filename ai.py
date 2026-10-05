"""Shapes every AI reply must fit before anything is stored. Malformed replies are rejected, never saved."""
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Letter = Literal["A", "B", "C", "D"]
Difficulty = Literal["easy", "medium", "hard"]


def as_text(value, depth: int = 0) -> str:
    """Any JSON value as readable text. Models sometimes write an answer as an object ({"code_snippet": ..., "explanation": ...})
    or a list of parts instead of one string; the content is kept, laid out as lines."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "\n".join(t for t in (as_text(v, depth + 1) for v in value) if t)
    if isinstance(value, dict):
        lines = []
        for k, v in value.items():
            text = as_text(v, depth + 1)
            if not text:
                continue
            label = str(k).replace("_", " ").strip().capitalize()
            # code stays a block of its own; short values sit on the label's line
            lines.append(f"{label}:\n{text}" if "\n" in text or "code" in str(k).lower() else f"{label}: {text}")
        return "\n".join(lines)
    return str(value)


def as_lines(value) -> list[str]:
    """A list of short strings, from a list, a single string, or a list of objects."""
    if value is None:
        return []
    if isinstance(value, str):
        return [s.strip(" -•\t") for s in value.replace(";", "\n").splitlines() if s.strip(" -•\t")]
    if isinstance(value, dict):
        value = list(value.values())
    return [t for t in (as_text(v) for v in value) if t]


class _Item(BaseModel):
    """Small slips in an otherwise good question (\"Medium\", \"b\") are tidied rather than thrown away."""

    @field_validator("question", "explanation", "model_answer", "expected_answer", "topic", mode="before", check_fields=False)
    @classmethod
    def _text(cls, v):
        return as_text(v)

    @field_validator("accepted_answers", "expected_concepts", "key_points", mode="before", check_fields=False)
    @classmethod
    def _lines(cls, v):
        return as_lines(v)

    @field_validator("difficulty", mode="before", check_fields=False)
    @classmethod
    def _difficulty(cls, v):
        v = str(v or "medium").strip().lower()
        return v if v in ("easy", "medium", "hard") else "medium"

    @field_validator("correct_option", "misconception_option", mode="before", check_fields=False)
    @classmethod
    def _letter(cls, v):
        return str(v).strip().upper()[:1]


class Concepts(BaseModel):
    title: str = ""
    subject: str = ""
    parent_subject: str = ""
    concepts: list[str] = []
    sections: list[dict] = []


class GeneratedMCQ(_Item):
    question: str = Field(min_length=5)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_option: Letter
    explanation: str = ""
    wrong_option_diagnosis: dict[str, str] = {}
    topic: str = ""
    difficulty: Difficulty = "medium"

    @field_validator("options", mode="before")
    @classmethod
    def _options(cls, v):
        if isinstance(v, dict):
            v = [v[k] for k in sorted(v)]
        if isinstance(v, list):
            return [as_text(o.get("text", o.get("option", o))) if isinstance(o, dict) else as_text(o) for o in v]
        return v

    @field_validator("wrong_option_diagnosis", mode="before")
    @classmethod
    def _diagnosis(cls, v):
        return {str(k).strip().upper()[:1]: as_text(t) for k, t in v.items()} if isinstance(v, dict) else {}

    @model_validator(mode="after")
    def _distinct(self):
        if len({o.strip().lower() for o in self.options}) != 4:
            raise ValueError("options must be four different answers")
        return self


class GeneratedFillBlank(_Item):
    question: str = Field(min_length=5)
    expected_answer: str = Field(min_length=1)
    accepted_answers: list[str] = []
    explanation: str = ""
    topic: str = ""
    difficulty: Difficulty = "medium"


class RubricPoint(BaseModel):
    point: str
    marks: float = 1

    @model_validator(mode="before")
    @classmethod
    def _shape(cls, v):
        # a rubric point written as plain text, or with its marks as "2 marks"
        if isinstance(v, str):
            return {"point": v, "marks": 1}
        if isinstance(v, dict):
            v = dict(v)
            v["point"] = as_text(v.get("point") or v.get("criterion") or v.get("description") or v.get("text") or "")
            m = re.search(r"\d+(\.\d+)?", str(v.get("marks", 1)))
            v["marks"] = float(m.group()) if m else 1
        return v


class GeneratedWritten(_Item):
    question: str = Field(min_length=5)
    model_answer: str = Field(min_length=5)
    rubric: list[RubricPoint] = []
    expected_concepts: list[str] = []
    key_points: list[str] = []
    topic: str = ""
    difficulty: Difficulty = "medium"


class ReasoningSignal(BaseModel):
    hypothesis: str
    strength: Literal["weak", "moderate", "strong"] = "weak"
    quote: str = ""


class ReasoningAnalysis(BaseModel):
    signals: list[ReasoningSignal] = []
    slip_kind: Literal["CALCULATION_ERROR", "MISINTERPRETATION", "CARELESS_SLIP"] | None = None
    explanation: str = ""


class Explanation(BaseModel):
    key_terms: list[str] = []
    core_concepts: list[str] = []
    explanation: str = Field(min_length=10)
    remember: str = ""


class ConceptFollowUp(_Item):
    question: str = Field(min_length=5)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_option: Letter
    explanation: str = ""

    @model_validator(mode="after")
    def _distinct(self):
        if len({o.strip().lower() for o in self.options}) != 4:
            raise ValueError("options must be four different answers")
        return self


class Feedback(BaseModel):
    feedback: str = Field(min_length=3)


class GeneratedFollowUp(_Item):
    question: str = Field(min_length=5)
    options: list[str] = Field(min_length=4, max_length=4)
    correct_option: Letter
    misconception_option: Letter
    purpose: str = ""
    explanation: str = ""

    @model_validator(mode="after")
    def _separates(self):
        if self.correct_option == self.misconception_option:
            raise ValueError("the misconception must lead to a wrong option")
        return self


class WrittenGrade(BaseModel):
    marks_awarded: float = Field(ge=0)
    keywords_matched: list[str] = []
    concepts_covered: list[str] = []
    missing_concepts: list[str] = []
    complete_answer: str = ""
    misconceptions: list[str] = []
    feedback: str = ""
    evidence: list[str] = []
    confidence: float = Field(ge=0, le=100)


class MistakeType(BaseModel):
    mistake_type: Literal["CARELESS_SLIP", "MISCONCEPTION", "GAP_IN_UNDERSTANDING", "CALCULATION_ERROR"]
    reason: str = ""

    @field_validator("mistake_type", mode="before")
    @classmethod
    def _upper(cls, v):
        v = str(v).strip().upper().replace(" ", "_").replace("-", "_")
        return {"INCOMPLETE_UNDERSTANDING": "GAP_IN_UNDERSTANDING", "GAP": "GAP_IN_UNDERSTANDING"}.get(v, v)


class FillBlankJudgement(BaseModel):
    classification: Literal["CORRECT", "MINOR_ERROR", "CALCULATION_ERROR", "MISCONCEPTION", "MISINTERPRETATION"]
    feedback: str = ""
    confidence: float = Field(ge=0, le=100, default=60)

    @field_validator("classification", mode="before")
    @classmethod
    def _upper(cls, v):
        return str(v).upper()


class DiagnosticResult(BaseModel):
    """The diagnosis as returned to the frontend."""

    primary_hypothesis: str
    alternative_hypotheses: list[str]
    evidence: list[str]
    confidence: float
    requires_followup: bool
    explanation: str


# ───────────────────────── notes ─────────────────────────


class NoteHeading(BaseModel):
    heading: str
    subheadings: list[str] = []


class NoteDefinition(BaseModel):
    term: str
    definition: str


class DocStructure(BaseModel):
    """What Mistral reads out of a document before the notes are written."""

    title: str = ""
    headings: list[NoteHeading] = []
    definitions: list[NoteDefinition] = []


class NoteKeyword(BaseModel):
    keyword: str
    meaning: str


class NoteWeightage(BaseModel):
    level: str = "Medium"
    reason: str = ""

    @field_validator("level", mode="before")
    @classmethod
    def _level(cls, v):
        v = str(v or "").strip().capitalize()
        return v if v in ("High", "Medium", "Low") else "Medium"


class NoteSubConcept(BaseModel):
    concept: str
    details: list[str] = []


class NoteConcept(BaseModel):
    concept: str
    children: list[NoteSubConcept] = []


class NoteCore(BaseModel):
    concept: str
    explanation: str


def _lines(v):
    """A list of lines, even when the model wrote them as one block of text."""
    if isinstance(v, str):
        return [s.strip(" -•\t") for s in v.replace(". ", ".\n").splitlines() if s.strip(" -•\t")]
    return v


class GeneratedNotes(BaseModel):
    title: str = Field(min_length=1)
    outline: list[NoteHeading] = []
    definitions: list[NoteDefinition] = []
    summary: str = Field(min_length=20)
    keywords: list[NoteKeyword] = []
    key_points: list[str] = Field(min_length=1)
    weightage: NoteWeightage = NoteWeightage()
    hierarchy: list[NoteConcept] = []
    core_concepts: list[NoteCore] = []
    potential_questions: list[str] = Field(min_length=3)
    brief_summary: list[str] = Field(min_length=1)

    @field_validator("key_points", "potential_questions", "brief_summary", mode="before")
    @classmethod
    def _as_lines(cls, v):
        return _lines(v)

    @model_validator(mode="after")
    def _trim(self):
        self.potential_questions = self.potential_questions[:10]
        self.brief_summary = self.brief_summary[:5]
        return self


# ───────────────────────── maths verification ─────────────────────────


class MathCheck(BaseModel):
    number: int
    working: str = ""
    final_answer: str = ""
    proposed_is_correct: bool = True

    @field_validator("final_answer", "working", mode="before")
    @classmethod
    def _text(cls, v):
        return "" if v is None else str(v)


class MathChecks(BaseModel):
    results: list[MathCheck] = []
