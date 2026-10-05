DIAGNOSIS_PROMPT_VERSION = "DIAGNOSIS_PROMPT_V1"

# Groq reads what the student said about their own answer. It supplies signals; the
# confidence itself is computed by the engine from those signals and the answers.
DIAGNOSIS_PROMPT_V1 = """A student answered a multiple-choice question incorrectly and explained their thinking.
A wrong answer does not by itself mean a misconception: it may be a careless slip, a calculation error or a misreading.

QUESTION: {question}
OPTIONS: {options}
CORRECT OPTION: {correct}
STUDENT CHOSE: {selected}
STUDENT'S EXPLANATION: "{reasoning}"

CANDIDATE HYPOTHESES (id: meaning):
{hypotheses}

For each hypothesis the explanation gives real evidence for, report it. Ignore hypotheses the explanation says nothing about.

Return JSON only:
{{"signals": [{{"hypothesis": one of the ids above, "strength": "weak" | "moderate" | "strong", "quote": the few words of the explanation that show it}}],
  "slip_kind": "CALCULATION_ERROR" | "MISINTERPRETATION" | "CARELESS_SLIP" | null,
  "explanation": one sentence, for the student, on what their explanation suggests}}
Report observations and the conclusion only. Do not include step-by-step private reasoning.
"""

FEEDBACK_PROMPT_VERSION = "FEEDBACK_PROMPT_V1"

FEEDBACK_PROMPT_V1 = """Write feedback for a student after a diagnosis. Be warm, specific and brief (at most three sentences). Address the student as "you".

QUESTION: {question}
THEY CHOSE: {selected}
CORRECT ANSWER: {correct}
DIAGNOSIS: {diagnosis} ({confidence}% confidence, status {status})
EVIDENCE: {evidence}

If the status is UNCERTAIN, say plainly that there is not enough evidence yet and do not name a cause.
If the diagnosis is a slip or an error in calculation or reading, reassure them that the idea is sound.
Return JSON only: {{"feedback": str}}
"""
