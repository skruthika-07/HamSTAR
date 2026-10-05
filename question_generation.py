QUESTION_GENERATION_PROMPT_VERSION = "QUESTION_GENERATION_PROMPT_V1"

CONCEPT_EXTRACTION_PROMPT_V1 = """You read study material for a learning app.
From the material below, return JSON with:
  "title": a short title for the material,
  "subject": the school or university subject it belongs to, in one to four words (for example "Physics", "Organic Chemistry", "Object-Oriented Programming", "Modern History", "Microeconomics"); use "" only if it truly cannot be told,
  "parent_subject": the broad area that subject sits in, one of "Maths", "Science", "Computer Science", "Social Studies", "Languages", "Commerce", "Other",
  "concepts": up to 12 distinct concepts or topics it teaches (short noun phrases),
  "sections": up to 8 objects {{"heading": str, "summary": one sentence}}.
Use only what is in the material. Return JSON only.

MATERIAL:
{text}
"""

_SHAPES = {
    "MCQ": """Each question object:
{"question": str, "options": [exactly four strings], "correct_option": "A"|"B"|"C"|"D",
 "explanation": str, "wrong_option_diagnosis": {"<letter of each wrong option>": the student's faulty thinking that leads to choosing it, written as a belief, e.g. "Believes plants take in oxygen for photosynthesis"},
 "topic": str, "difficulty": "easy"|"medium"|"hard"}
Every wrong option must be a plausible answer produced by one identifiable mistake. Exactly one option is correct.
Write the options as plain text without a leading letter.""",
    "ONE_WORD": """Each question object:
{"question": a direct question that is answered in one word or a short phrase (no blank, no options), "expected_answer": str, "accepted_answers": [equivalent ways of writing it],
 "explanation": one or two sentences on why that is the answer, "topic": str, "difficulty": "easy"|"medium"|"hard"}""",
    "FILL_BLANK": """Each question object:
{"question": a sentence with one blank written as ____, "expected_answer": str, "accepted_answers": [equivalent ways of writing it],
 "explanation": str, "topic": str, "difficulty": "easy"|"medium"|"hard"}""",
    "SHORT_ANSWER": """Each question object:
{"question": str, "model_answer": str, "rubric": [{"point": str, "marks": number}], "expected_concepts": [str],
 "topic": str, "difficulty": "easy"|"medium"|"hard"}
The rubric marks must add up to the marks per question.""",
    "LONG_ANSWER": """Each question object:
{"question": str, "model_answer": str, "rubric": [{"point": str, "marks": number}], "expected_concepts": [str], "key_points": [str],
 "topic": str, "difficulty": "easy"|"medium"|"hard"}
The rubric marks must add up to the marks per question.""",
}

QUESTION_GENERATION_PROMPT_V1 = """You write exam questions for a learning app, strictly from the study material provided.

Rules:
- Use only facts found in the material. Do not bring in outside content.
- The material is ONE document. Write questions only from this document, never from other documents on the same subject.
- Stay on the topic "{topic}".
- For maths: always verify mathematical answers step by step before returning them, and show the working (the steps) in the explanation.
- For algebra: distribute signs first, collect like terms, then double-check the final result. Example: -(4-3x)+2x = -4+3x+2x = 5x-4.
- No duplicate or near-duplicate questions. Each question has one unambiguous answer.
- Difficulty: {difficulty}. Question type: {question_type}. Marks per question: {marks}.
- Write exactly {n} questions.

{shape}

Return JSON only, in the form {{"questions": [ ... ]}}.

MATERIAL:
{context}
"""


def generation_prompt(question_type: str, marks: int, n: int, difficulty: str, topic: str, context: str) -> str:
    return QUESTION_GENERATION_PROMPT_V1.format(topic=topic or "the material", difficulty=difficulty, question_type=question_type, marks=marks, n=n, shape=_SHAPES[question_type], context=context)
