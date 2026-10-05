NOTES_PROMPT_VERSION = "NOTES_PROMPT_V1"

# Step 1 (Mistral): read the document's own structure.
NOTES_STRUCTURE_PROMPT_V1 = """You read a study document for a notes app.
Read its structure and return JSON with:
  "title": the topic of the document in a few words,
  "headings": up to 12 objects {{"heading": str, "subheadings": [str]}} following the document's own order,
  "definitions": every term the document defines, as {{"term": str, "definition": str}}.
Use only what is in the document. Return JSON only.

DOCUMENT:
{text}
"""

# Step 2 (Groq): write the revision notes, always in the same sections.
NOTES_PROMPT_V1 = """You write revision notes for a student from their study material. Use only what the material says.

STRUCTURE ALREADY READ FROM THE DOCUMENT (may be empty):
{structure}

MATERIAL:
{text}

Return JSON only, with exactly these keys:
{{"title": the topic title,
  "outline": [{{"heading": str, "subheadings": [str]}}]  (the document's headings and subheadings, in order),
  "definitions": [{{"term": str, "definition": str}}]  (all key definitions, clearly worded),
  "summary": a concise summary of the entire content, one paragraph,
  "keywords": [{{"keyword": str, "meaning": one line}}]  (the essential must-know keywords),
  "key_points": [str]  (the most important facts, one per item),
  "weightage": {{"level": "High"|"Medium"|"Low", "reason": why this topic matters that much for an exam}},
  "hierarchy": [{{"concept": parent concept, "children": [{{"concept": sub concept, "details": [str]}}]}}]  (a tree: parent concept, sub concepts, details),
  "core_concepts": [{{"concept": str, "explanation": the idea explained simply in one or two sentences}}],
  "potential_questions": [str]  (5 to 10 likely exam questions from this content),
  "brief_summary": [str]  (3 to 5 lines for quick revision)}}
Plain text in every value: no markdown, no numbering inside the strings.
"""
