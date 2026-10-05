"""Mistral: document OCR, concept extraction and question generation. Nothing else calls Mistral directly."""
import base64

from pydantic import BaseModel

from ..core.config import get_settings
from ..core.logging import log
from ..prompts.question_generation import CONCEPT_EXTRACTION_PROMPT_V1, generation_prompt
from ..prompts.notes import NOTES_STRUCTURE_PROMPT_V1
from ..schemas.ai import Concepts, DocStructure, GeneratedFillBlank, GeneratedMCQ, GeneratedWritten
from .ai_client import JsonChatClient, ProviderError

ITEM_SCHEMA = {"ONE_WORD": GeneratedFillBlank, "MCQ": GeneratedMCQ, "FILL_BLANK": GeneratedFillBlank, "SHORT_ANSWER": GeneratedWritten, "LONG_ANSWER": GeneratedWritten}


class _Batch(BaseModel):
    questions: list[dict]


class MistralService(JsonChatClient):
    provider = "mistral"
    base_url = "https://api.mistral.ai/v1"
    unavailable = "Document processing failed. Please try again in a moment."

    def __init__(self):
        s = get_settings()
        super().__init__(s.mistral_api_key, s.mistral_chat_model)
        self.ocr_model = s.mistral_ocr_model
        # set after the first refusal, so later uploads do not wait on a model the plan does not include
        self.ocr_blocked = False

    def ocr(self, data: bytes, mime: str) -> str:
        """Text of a PDF or image, page by page, as markdown."""
        uri = f"data:{mime};base64,{base64.b64encode(data).decode()}"
        document = {"type": "image_url", "image_url": uri} if mime.startswith("image/") else {"type": "document_url", "document_url": uri}
        if self.ocr_blocked:
            raise ProviderError(self.provider, self.unavailable)
        try:
            reply = self._post("/ocr", {"model": self.ocr_model, "document": document})
        except ProviderError:
            self.ocr_blocked = True
            raise
        pages = reply.get("pages") or []
        text = "\n\n".join(p.get("markdown", "") for p in pages).strip()
        if not text:
            raise ProviderError(self.provider, "No readable text was found in this document.")
        return text

    def read_image(self, data: bytes, mime: str) -> str:
        """Transcribe an image with the vision chat model, for accounts where the OCR model is not available."""
        uri = f"data:{mime};base64,{base64.b64encode(data).decode()}"
        text = self.chat_text([{"type": "text", "text": "Transcribe all the text in this image exactly, keeping maths as written. Output only the text."}, {"type": "image_url", "image_url": uri}])
        if not text:
            raise ProviderError(self.provider, "No readable text was found in this image.")
        return text

    def extract_concepts(self, text: str) -> Concepts:
        return self.chat_json(CONCEPT_EXTRACTION_PROMPT_V1.format(text=text[:24000]), Concepts)

    def read_structure(self, text: str) -> DocStructure:
        """The document's own title, headings and definitions: the first step of the notes generator."""
        return self.chat_json(NOTES_STRUCTURE_PROMPT_V1.format(text=text[:24000]), DocStructure)

    def generate_questions(self, question_type: str, marks: int, n: int, difficulty: str, topic: str, context: str) -> list[BaseModel]:
        """Questions of one type, each validated against its schema. Invalid items are dropped, not stored."""
        batch = self.chat_json(generation_prompt(question_type, marks, n, difficulty, topic, context[:24000]), _Batch)
        schema, out = ITEM_SCHEMA[question_type], []
        for raw in batch.questions:
            try:
                out.append(schema.model_validate(raw))
            except Exception as e:  # noqa: BLE001 - one bad item must not sink the batch
                log.warning("A generated %s question was dropped: %s", question_type, str(e).splitlines()[0:3])
        return out


_instance: MistralService | None = None


def get_mistral() -> MistralService:
    global _instance
    if _instance is None:
        _instance = MistralService()
    return _instance
