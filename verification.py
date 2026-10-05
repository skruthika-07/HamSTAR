MATH_VERIFY_PROMPT_VERSION = "MATH_VERIFY_PROMPT_V1"

# A second model checks each maths answer key before a student sees it.
MATH_VERIFY_PROMPT_V1 = """You check the answer keys of maths questions before students see them. Answer keys are sometimes wrong.

For EACH question below: verify this answer. Work the question out yourself step by step, then confirm or correct the proposed answer.
- For algebra: distribute signs first (a minus in front of a bracket changes the sign of every term inside), collect like terms, then double-check the final result by substituting a number.
- For arithmetic and fractions: show each step and recompute the final value once more before answering.
- If the question lists options, the final answer must be the text of the one option that is correct; if none is correct say so in "working" and give the true answer.
- An answer that is equal in value but written differently (4 + x and x + 4, 1/2 and 0.5) counts as correct.

{questions}

Return JSON only:
{{"results": [{{"number": the question's number, "working": the step-by-step working in one or two short sentences, "final_answer": the correct final answer written as briefly as the proposed one, "proposed_is_correct": true or false}}]}}
One result for every question, in the same order.
"""


def verify_prompt(entries: list[dict]) -> str:
    lines = []
    for e in entries:
        line = f"{e['number']}. Question: {e['question']}\n   Proposed answer: {e['proposed']}"
        if e.get("options"):
            line += "\n   Options: " + " | ".join(e["options"])
        lines.append(line)
    return MATH_VERIFY_PROMPT_V1.format(questions="\n".join(lines))
