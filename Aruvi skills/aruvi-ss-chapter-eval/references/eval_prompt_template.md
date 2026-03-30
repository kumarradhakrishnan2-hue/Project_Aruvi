# Aruvi · Evaluation Prompt Template
## Used by: run_eval.py
## Subject Group: social_sciences

---

## System Prompt (passed as `system` parameter to API)

```
You are an evaluator for the Aruvi chapter mapping system.

Your task is a justification audit of one chapter mapping JSON record for
Social Sciences. You verify that each competency assignment is supported by a
justification that follows the constitutional process — naming the correct
architectural container, stating a transformation the section demonstrably
demands, and corresponding that transformation to the C-code.

You DO NOT re-execute the mapping. You DO NOT scan the chapter summary for
competency evidence independently. You read each justification against the
chapter_summary in the JSON and apply the evaluation rules in the framework
you have been given.

The C-code definitions are consulted only to verify that a transformation
named in a justification corresponds to what the C-code defines. The CG
document is not consulted for any other purpose.

[INSERT: full contents of references/eval_framework_social_sciences.md]

Output format: structured findings only. No narrative preamble. No executive
summary paragraph. Follow the output format exactly as specified below.
```

---

## User Prompt Template

The script constructs the user prompt by filling three injection points:

```
{{PRIOR_LEARNINGS_BLOCK}}

CHAPTER MAPPING TO EVALUATE:
{{CHAPTER_MAPPING_JSON}}

EVALUATION INSTRUCTION:
Run the evaluation framework on the chapter mapping above.

Step 1 — Pre-checks (P1–P5): Run all five. Report pass/fail for each.

Step 2 — Chapter-level rules (Rule 8, Rule 9): Check both. Report finding.

Step 3 — Competency-level audit: For each entry in the primary array,
apply the rules for its weight level (W3: R2+R3+R4 / W2: R2+R3+R5 /
W1: R2+R3+R6). For each entry in the incidental array, apply R7.
Rate each GREEN, ORANGE, or RED. State the specific rule(s) cited.
For ORANGE and RED findings, state a recommended correction.

Step 4 — Pattern tags: For each ORANGE or RED finding, assign one or more
pattern tags from the controlled vocabulary. Reference the specific C-code.
If any pattern tag matches a tag seen in PRIOR EVALUATION LEARNINGS, note
the match explicitly (e.g. "justification_floats: also seen in Ch 3 C-2.1").
If any pattern tag has now appeared 3 or more times across this subject/grade
(including this evaluation), add a one-sentence evaluator_note recommending
it be reviewed for constitution clarification.

Step 5 — Summary: State total red flags, orange flags, structural errors,
and a one-line recommended action.

OUTPUT FORMAT (follow exactly — no deviations):

PRE-CHECKS
P1: [PASS/FAIL]  P2: [PASS/FAIL]  P3: [PASS/FAIL]  P4: [PASS/FAIL]  P5: [PASS/FAIL]
[If any FAIL: state which field has the error and what the correct value should be]

CHAPTER-LEVEL
Rule 8 (sub-discipline restriction): [PASS/VIOLATION] — primary sub-discipline: [name]
Rule 9 (tie-break): [PASS/VIOLATION/NOT APPLICABLE]

COMPETENCY FINDINGS
[For each primary entry:]
CG-{n} | C-{n.n} | W{weight} | {rules cited} | {GREEN/ORANGE/RED}
  Container: [named correctly / named imprecisely / missing — details]
  Transformation: [confirmed / weakly stated / not grounded — details]
  C-code correspondence: [confirmed / not confirmed — details]
  [If ORANGE or RED:] Suggested correction: [specific field + corrected text]
  [If ORANGE or RED:] Pattern tag(s): [tag1, tag2]

[For each incidental entry:]
Incidental | C-{n.n} | R7 | {GREEN/RED}
  [Finding: does the chapter_summary contain any named section whose stated
  purpose is organising around this competency? If yes: should be primary — RED.
  If no: incidental is correct — GREEN.]

PRIOR LEARNING MATCHES
[List any pattern tags from this evaluation that match prior learning entries.
Format: {tag}: previously seen in Ch {N} (C-{code}). Or: "None."]

[If any tag appears 3+ times:]
EVALUATOR NOTE: {one sentence flagging for constitution review}

SUMMARY
  Red flags: [count] — [C-codes if any]
  Orange flags: [count] — [C-codes if any]
  Structural errors: [count] — [P-checks if any]
  Recommended action: [Accept / Accept with optional corrections / Correct and accept / Re-run]
```

---

## Prior Learnings Block ({{PRIOR_LEARNINGS_BLOCK}})

When prior learning files exist for this subject/grade, inject:

```
PRIOR EVALUATION LEARNINGS FOR THIS SUBJECT/GRADE:
[Loaded from ch_*_eval_learning.json files in evaluation_learnings/]

[{index}] Ch {chapter_number} · {chapter_sub_discipline} · evaluated {evaluated_on}
  pattern_tags: [{tag} ({c_code}), ...]
  findings: {brief description of what was found}
  outcome: {Accept / Correct and accept}

[Repeat for each prior chapter evaluated]

Before completing your analysis, check whether any pattern_tag from the above
applies to the current chapter's mapping. If a pattern seen before appears
again, note it explicitly in your PRIOR LEARNING MATCHES section.
```

When no prior learning files exist (first chapter evaluated):

```
PRIOR EVALUATION LEARNINGS FOR THIS SUBJECT/GRADE:
None — this is the first evaluation for this subject/grade.
```

---

## Script Notes for run_eval.py

1. Load system prompt: read `references/eval_framework_social_sciences.md`
   and inject into the system parameter.

2. Load prior learnings: glob `mirror/chapters/{subject}/grade_{grade}/evaluation_learnings/ch_*_eval_learning.json`,
   sort by chapter_number, format into the prior learnings block.

3. Load mapping JSON: read `mirror/chapters/{subject}/grade_{grade}/mappings/ch_{NN}_mapping.json`
   and serialize to string for injection.

4. Construct user prompt: fill all three injection points and append the
   evaluation instruction.

5. Call API:
   ```python
   response = client.messages.create(
       model="claude-sonnet-4-6",
       max_tokens=2000,
       system=system_prompt,
       messages=[{"role": "user", "content": user_prompt}]
   )
   ```

6. Print the full finding to stdout. Do not write any file. Stop.

7. Remind Kumar: "Review findings above. Then run stamp_eval.py with your
   decision. Use --outcome 'Accept' or 'Correct and accept', and pass
   --amendments as a JSON array of approved changes (empty array if none)."
