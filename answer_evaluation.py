ANSWER_EVALUATION_PROMPT_VERSION = "ANSWER_EVALUATION_PROMPT_V2"

# Written answers are marked on the ideas they contain, never on whether the wording matches the model answer.
ANSWER_EVALUATION_PROMPT_V2 = """You mark a student's written answer for a learning app.

QUESTION ({marks} marks, {kind}): {question}
MODEL ANSWER (one good answer, NOT the only acceptable wording): {model_answer}
RUBRIC: {rubric}
EXPECTED CONCEPTS: {concepts}

STUDENT ANSWER: {answer}

How to mark:
- Mark the CONCEPTS, not the wording. An idea expressed in the student's own words, in everyday language, or with a
  synonym counts in full. Example: if the model answer says "vaporization occurs at 100°C" and the student writes
  "water turns to gas when heated", that concept is covered.
- Never lower the mark because the phrasing, order, length or vocabulary differs from the model answer.
- Give partial marks in proportion to how much of the rubric the answer's ideas cover. Judge {criteria}.
- List as missed only what is genuinely absent or wrong, not what is merely worded differently.
- Do not reward technical terms that are used without showing understanding.

Return JSON only:
{{"marks_awarded": number between 0 and {marks},
  "keywords_matched": [key terms the student got right; if they expressed one in other words, write it as "term (you said: their words)"],
  "concepts_covered": [each core idea the student understood correctly, as a short phrase],
  "missing_concepts": [only the points that are genuinely missing or wrong, as short phrases],
  "complete_answer": two to four sentences on what a complete answer should include,
  "misconceptions": [any wrong ideas the answer shows],
  "feedback": one or two warm sentences addressed to the student,
  "evidence": up to four short observations that justify the mark,
  "confidence": 0-100, how well the answer demonstrates understanding}}
Give the conclusion and the observations only. Do not include step-by-step private reasoning.
"""

CRITERIA = {
    "SHORT_ANSWER": "the key concepts, their accuracy, and whether the reasoning hangs together",
    "LONG_ANSWER": "the key concepts, the quality and accuracy of the explanation, logical structure and flow, examples, and any relevant formulas or steps",
}

FILL_BLANK_PROMPT_V1 = """A student filled in a blank. Decide whether their answer is acceptable.

QUESTION: {question}
EXPECTED: {expected}
ALSO ACCEPTED: {accepted}
STUDENT WROTE: {answer}

Return JSON only:
{{"classification": "CORRECT" | "MINOR_ERROR" | "CALCULATION_ERROR" | "MISCONCEPTION" | "MISINTERPRETATION",
  "feedback": one sentence for the student,
  "confidence": 0-100}}
CORRECT means equivalent in meaning or value to the expected answer. MINOR_ERROR means right idea with a spelling or formatting slip.
"""

MISTAKE_TYPE_PROMPT_VERSION = "MISTAKE_TYPE_PROMPT_V1"

# A first impression of the KIND of mistake, from one wrong answer. Shown as "Looks like…", never as a verdict.
MISTAKE_TYPE_PROMPT_V1 = """A student answered a question incorrectly. Decide which ONE kind of mistake it most looks like.

QUESTION: {question}
CORRECT ANSWER: {correct}
STUDENT'S ANSWER: {given}
NOTES: {notes}

Kinds:
- CARELESS_SLIP: they knew it but made a small error (wrong sign, skipped a step, a typo, misread the question).
- MISCONCEPTION: they have a wrong mental model of the concept: the answer follows a faulty rule or belief.
- GAP_IN_UNDERSTANDING: they have not learned this concept: the answer is a guess, blank, or far off, or key ideas are missing.
- CALCULATION_ERROR: they understood the concept and the method, but an arithmetic or computation step went wrong.

Choose MISCONCEPTION only when the answer itself shows a wrong idea; a single wrong answer is often just a slip.

Return JSON only: {{"mistake_type": one of the four kinds, "reason": one short, kind sentence}}
"""
