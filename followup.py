FOLLOWUP_PROMPT_VERSION = "FOLLOWUP_PROMPT_V1"

# Used for questions generated from uploaded material, where no verified probe exists.
FOLLOWUP_PROMPT_V1 = """A student got a multiple-choice question wrong. Two explanations compete:

A) MISCONCEPTION: {misconception}
B) CARELESS SLIP: the student understands the idea and made a one-off error.

ORIGINAL QUESTION: {question}
THEY CHOSE: {selected}
CORRECT ANSWER: {correct}
QUESTIONS ALREADY ASKED: {asked}

Write ONE new multiple-choice question on the same idea that tells A from B:
- a student who holds the misconception in A would be drawn to one specific wrong option;
- a student who simply slipped would get it right;
- different numbers or wording from the questions already asked; simpler arithmetic than the original, so a slip is unlikely.

Return JSON only:
{{"question": str,
  "options": [exactly four strings],
  "correct_option": "A"|"B"|"C"|"D",
  "misconception_option": the letter the misconception leads to,
  "purpose": one sentence on what the answer will reveal,
  "explanation": the worked solution}}
"""

CONCEPT_FOLLOWUP_PROMPT_VERSION = "CONCEPT_FOLLOWUP_PROMPT_V1"

# After the correct answer has been explained: does the idea carry over to a slightly different question?
CONCEPT_FOLLOWUP_PROMPT_V1 = """A student got a question wrong, was shown the correct answer and says they now understand.
Write ONE new multiple-choice question that tests the SAME concept, so it shows whether the idea carried over.

ORIGINAL QUESTION: {question}
ITS CORRECT ANSWER: {answer}
NOTES: {notes}
QUESTIONS ALREADY ASKED (do not repeat them): {asked}

Rules:
- Same concept, but a slightly different question: different numbers, example or wording. Not the original reworded.
- {level}
- Four options, exactly one correct; the wrong ones are plausible, typical mistakes on this concept.
- Write the options as plain text without a leading letter.

Return JSON only:
{{"question": str, "options": [exactly four strings], "correct_option": "A"|"B"|"C"|"D", "explanation": one or two sentences on why that option is right}}
"""
