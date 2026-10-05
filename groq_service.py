"""Groq: reading student reasoning, writing follow-ups and feedback, marking written answers. Nothing else calls Groq directly."""
from ..core.config import get_settings
from ..prompts.answer_evaluation import ANSWER_EVALUATION_PROMPT_V2, CRITERIA, FILL_BLANK_PROMPT_V1, MISTAKE_TYPE_PROMPT_V1
from ..prompts.diagnosis import DIAGNOSIS_PROMPT_V1, FEEDBACK_PROMPT_V1
from ..prompts.explanation import explanation_prompt
from ..prompts.notes import NOTES_PROMPT_V1
from ..prompts.verification import verify_prompt
from ..prompts.followup import CONCEPT_FOLLOWUP_PROMPT_V1, FOLLOWUP_PROMPT_V1
from ..schemas.ai import GeneratedNotes, MathChecks
from ..schemas.ai import ConceptFollowUp, Explanation, Feedback, MistakeType, FillBlankJudgement, GeneratedFollowUp, ReasoningAnalysis, WrittenGrade
from .ai_client import JsonChatClient


def _options(question: dict) -> str:
    return "; ".join(f"{o['id']}) {o['text']}" for o in question["options"])


class GroqService(JsonChatClient):
    provider = "groq"
    base_url = "https://api.groq.com/openai/v1"
    unavailable = "Answer evaluation is temporarily unavailable."

    def __init__(self):
        s = get_settings()
        super().__init__(s.groq_api_key, s.groq_model)

    def analyze_reasoning(self, question: dict, selected: str, reasoning: str, hypotheses: dict[str, str]) -> ReasoningAnalysis:
        correct = next(o for o in question["options"] if o["correct"])
        return self.chat_json(
            DIAGNOSIS_PROMPT_V1.format(
                question=question["prompt"], options=_options(question), correct=f"{correct['id']}) {correct['text']}", selected=selected,
                reasoning=reasoning[:1500].replace('"', "'"), hypotheses="\n".join(f"- {k}: {v}" for k, v in hypotheses.items()),
            ),
            ReasoningAnalysis,
        )

    def feedback(self, question: dict, selected_text: str, correct_text: str, diagnosis: str, confidence: int, status: str, evidence: list[str]) -> str:
        return self.chat_json(
            FEEDBACK_PROMPT_V1.format(question=question["prompt"], selected=selected_text, correct=correct_text, diagnosis=diagnosis, confidence=confidence, status=status, evidence=" | ".join(evidence)),
            Feedback,
        ).feedback

    def explain(self, question: str, answer: str, notes: str, level: int) -> Explanation:
        """The correct answer explained in a fixed structure; a higher level means simpler words and a fresh everyday example."""
        return self.chat_json(explanation_prompt(question, answer, notes, level), Explanation)

    def verify_math(self, entries: list[dict]) -> MathChecks:
        """Each maths question worked out step by step, and whether its proposed answer holds."""
        return self.chat_json(verify_prompt(entries), MathChecks)

    def notes(self, text: str, structure: str) -> GeneratedNotes:
        """Revision notes in the fixed structure, written from the text Mistral read."""
        return self.chat_json(NOTES_PROMPT_V1.format(text=text[:24000], structure=structure[:6000] or "none"), GeneratedNotes)

    def concept_follow_up(self, question: str, answer: str, notes: str, asked: list[str], easier: bool) -> ConceptFollowUp:
        """A new multiple-choice question on the same concept as one the student got wrong."""
        return self.chat_json(
            CONCEPT_FOLLOWUP_PROMPT_V1.format(question=question, answer=answer, notes=notes or "none", asked=" | ".join(asked), level="Make it EASIER than the original: one small step, simple numbers or wording." if easier else "Make it about as hard as the original."),
            ConceptFollowUp,
        )

    def follow_up(self, question: dict, selected_text: str, correct_text: str, misconception: str, asked: list[str]) -> GeneratedFollowUp:
        return self.chat_json(
            FOLLOWUP_PROMPT_V1.format(misconception=misconception, question=question["prompt"], selected=selected_text, correct=correct_text, asked=" | ".join(asked) or "none"),
            GeneratedFollowUp,
        )

    def grade_written(self, kind: str, question: str, marks: int, model_answer: str, rubric: list, concepts: list, answer: str) -> WrittenGrade:
        grade = self.chat_json(
            ANSWER_EVALUATION_PROMPT_V2.format(marks=marks, kind=kind, question=question, model_answer=model_answer, rubric=rubric, concepts=concepts, answer=answer[:8000], criteria=CRITERIA[kind]),
            WrittenGrade,
        )
        grade.marks_awarded = min(grade.marks_awarded, marks)
        return grade

    def mistake_type(self, question: str, correct: str, given: str, notes: str) -> MistakeType:
        return self.chat_json(MISTAKE_TYPE_PROMPT_V1.format(question=question, correct=correct, given=given[:1500], notes=notes or "none"), MistakeType)

    def judge_fill_blank(self, question: str, expected: str, accepted: list[str], answer: str) -> FillBlankJudgement:
        return self.chat_json(FILL_BLANK_PROMPT_V1.format(question=question, expected=expected, accepted=accepted, answer=answer[:400]), FillBlankJudgement)


_instance: GroqService | None = None


def get_groq() -> GroqService:
    global _instance
    if _instance is None:
        _instance = GroqService()
    return _instance
