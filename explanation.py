EXPLANATION_PROMPT_VERSION = "EXPLANATION_PROMPT_V2"

# Shown after a wrong answer. It teaches the right answer, in a fixed structure, and does not dwell on what the student did wrong.
EXPLANATION_PROMPT_V2 = """A student is learning from this question. Explain the correct answer to them.

QUESTION: {question}
CORRECT ANSWER: {answer}
NOTES FROM THE ANSWER KEY: {notes}

{style}

Rules:
- Address the student as "you", in a warm tone. No filler praise such as "keep it up" or "you're doing great": every sentence teaches.
- Explain why the correct answer is correct. Do NOT discuss the student's own answer or say why it was wrong.
- You have not seen the student's answer: never say or imply that they got it right or wrong, and do not praise their work on it.
- Plain sentences, no markdown.

Return JSON only:
{{"key_terms": [two to five important words or terms in the answer, each a word or short phrase],
  "core_concepts": [one to three main ideas, each one short simple sentence],
  "explanation": the full explanation,
  "remember": one short line to remember it by (a tip, rule of thumb or one-line summary)}}
"""

STYLES = [
    "For the full explanation give a clean, clear account in two to four sentences, using the proper terms.",
    "For the full explanation, explain it again more simply, in everyday words a younger student would follow, and include one analogy or real-life example. Three to five short sentences. Keep the core concepts in plain words too.",
    "For the full explanation, explain it once more, even more simply, with a DIFFERENT everyday example from before (food, money, sport, or something at home), one small step at a time. Three to five short sentences. Keep the core concepts in plain words too.",
]


def explanation_prompt(question: str, answer: str, notes: str, level: int) -> str:
    return EXPLANATION_PROMPT_V2.format(question=question, answer=answer, notes=notes or "none", style=STYLES[min(level, len(STYLES) - 1)])
