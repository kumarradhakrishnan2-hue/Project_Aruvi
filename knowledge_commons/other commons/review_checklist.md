# Pilot Chapter Review Checklist
## Use after each of the first 3 pilot chapter mappings

Review the JSON output against each criterion below before proceeding to the next chapter.
If more than 2 criteria fail, correct the prompt in `call_mapping_api.py` before continuing.

---

## A. Chapter Summary Quality

- [ ] **Heading coverage**: Does the summary have a paragraph for EVERY major heading/subheading in the textbook chapter? Count headings in the PDF vs paragraphs in the summary.
- [ ] **Word count**: Is the summary between 600–900 words? (`len(summary.split())`)
- [ ] **Content fidelity**: Does the summary describe what the chapter *actually contains* — specific people, events, concepts, examples — rather than generic statements like "students will learn about..."?
- [ ] **Activity reference**: Where the chapter includes textbook exercises or "Think and Discuss" boxes, are these mentioned in the summary?
- [ ] **No hallucination**: Is every factual claim in the summary traceable to the chapter text? Read one paragraph and spot-check against the PDF.

---

## B. Competency Weight Assignments

- [ ] **Weight 3 defensibility**: For each Weight 3 assignment, ask: "If this competency were removed, would the chapter lose its fundamental purpose?" If you can still teach the chapter's core content without it, the weight is wrong.
- [ ] **Weight 2 defensibility**: Is there a dedicated section or activity block in the chapter that develops this competency? Not just a mention — a dedicated structural element.
- [ ] **Weight 1 defensibility**: Is there at least one explicit exercise or guided question in the chapter structured around this competency? Not incidental — explicitly structured.
- [ ] **No over-counting**: Does the chapter have so many Weight 3 assignments that it looks like everything is central? (Red flag: >2 Weight 3s in a typical chapter)
- [ ] **Sub-discipline rule (Social Sciences)**: If the chapter is primarily Geography, are History C-codes correctly capped at Weight 2 or below?

---

## C. Incidental Competencies

- [ ] **Correctly incidental**: For each incidental competency, confirm: is it genuinely present in the content but with zero explicit structural element (no exercise, no guided question) devoted to it?
- [ ] **Not missed primaries**: Is anything classified as incidental that actually has a dedicated exercise? If so, it should be Weight 1 at minimum.

---

## D. Technical Validity

- [ ] **chapter_weight arithmetic**: Does `chapter_weight` equal the sum of all primary weights? Check manually.
- [ ] **C-code validity**: Do all C-codes in the output exist in the Curricular Goals document? No invented codes.
- [ ] **min_viable_periods**: Is the value plausible for the chapter's complexity? A 15-page chapter with 3 competencies should not have min_viable_periods = 1.
- [ ] **JSON structure**: Does the output parse correctly and contain all required fields?

---

## E. Go / No-Go Decision

| Outcome | Action |
|---------|--------|
| All A + B criteria pass | Proceed to next pilot chapter |
| 1–2 minor issues (word count, one weight borderline) | Note issues, proceed, fix in bulk review after chapter 3 |
| Summary doesn't follow headings | Fix system prompt — add explicit instruction to list headings first, then write one paragraph per heading |
| Weight assignments systematically wrong (e.g. everything is Weight 3) | Fix constitution emphasis in system prompt before chapter 2 |
| C-codes not in CG document | Fix CG extraction — re-check extract_cg.py output |

---

## Token Cost Check

After each pilot chapter, check `token_log.csv`:
- Input tokens should be ~2,500–3,500
- Output tokens should be ~800–1,200
- Cost should be ~₹4–5

If input tokens exceed 4,000, the chapter text may be very long — consider trimming
boilerplate pages (prelims, glossary references) from the chapter PDF before extraction.
