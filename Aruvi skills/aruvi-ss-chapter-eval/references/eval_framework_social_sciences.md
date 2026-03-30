# Aruvi · Chapter Mapping Evaluation Framework
## Subject Group: Social Sciences | Middle Stage – Secondary Stage
## Constitution Reference: competency_constitution_social_sciences | Version 1.2
## Fetch Key: eval_framework_social_sciences

---

## Purpose

This document governs justification audits of Aruvi chapter mapping JSON records.
Its purpose is narrow: to verify that each competency assignment is supported by a
justification that follows the constitutional process — naming the correct architectural
container, stating a transformation the section demonstrably demands, and corresponding
that transformation to the C-code. It does not re-execute the mapping.

The chapter_summary in the JSON is the sole content reference. The CG document is
consulted only to verify that a stated transformation corresponds to a C-code definition
— never to scan the chapter for competency evidence independently.

---

## Section 2 — Pre-Checks (Mechanical)

Run first. These require no reasoning — arithmetic and structural checks only.
Report structural errors before the main evaluation. Structural errors must be
flagged regardless of outcome.

| Check | Pass Condition | Fail Action |
|---|---|---|
| P1 | chapter_weight equals sum of all weight values in primary array | Flag as structural error |
| P2 | Every weight in primary is exactly 1, 2, or 3 | Flag as structural error |
| P3 | primary array has at least one entry | Flag as structural error |
| P4 | Every entry in primary has a non-empty justification string | Flag as structural error |
| P5 | For every entry in primary, the cg field matches the parent CG of the c_code (e.g. C-2.1 must have cg: CG-2) | Flag as structural error |

---

## Section 3 — Chapter-Level Evaluation

Two rules checked once for the mapping as a whole.

**Rule 8 — Sub-discipline restriction**
Does the mapping assign Weight 3 to C-codes from more than one sub-discipline CG cluster?
Identify the chapter's primary sub-discipline from chapter_summary.
- History: CG-1, 2, 3
- Geography: CG-6, 7
- Political Science: CG-4, 8, 10
- Economics: CG-9
- Cross-cutting: CG-5, 7

**Rule 9 — Tie-break**
Are two or more competencies assigned Weight 3? If yes: verify the tie-break was
applied — the retained Weight 3's justification must reference chapter title, opening
paragraph, or concluding synthesis question. If count ≤ 1: not applicable.

---

## Section 4 — Competency-Level Evaluation

This evaluation is a justification audit — not a re-execution of the mapping.
The evaluator does not independently scan the chapter for competency evidence.
The evaluator reads each justification against the chapter summary and asks:
1. Does the justification name the correct architectural container?
2. Does it state a cognitive transformation the named section demonstrably demands —
   not one that a C-code-aware reader retrospectively connects to it?
3. Does that transformation correspond to what the C-code defines?

**CRITICAL:** The evaluator MUST NOT open the CG document and scan the chapter
summary for competency evidence. That is reverse deduction and is the same error
the constitution prohibits the mapping system from making. The C-code is consulted
only to verify that the transformation named in the justification corresponds to
what the C-code defines. Nothing more.

### Rules applied per weight level

- Weight 3: R2 (architectural container) · R3 (surface match rejection) · R4 (dissolution test)
- Weight 2: R2 · R3 · R5 (dedicated named section)
- Weight 1: R2 · R3 · R6 (single structural element, below section level)
- Incidental: R7 only (zero structural elements — verified from justification, not from C-code scanning)

### Rule definitions

**R2 — Architectural container:** The justification must name the specific section,
subsection, or activity block that is the architectural container for this competency.
A justification that names "the chapter" or "throughout the chapter" without naming
a specific container fails R2.

**R3 — Surface match rejection:** The justification must confirm that the match is
not based on shared vocabulary alone. The chapter's architecture must compel the
student to execute the specific analytical process the C-code defines.

**R4 — Dissolution test (Weight 3 only):** Removing this competency must structurally
dissolve the chapter's fundamental organising purpose. If the chapter would merely
reorganise or lose one section rather than lose its reason for existence, W3 fails.
Rhetorical prominence is not architectural centrality — the most discussed competency
is not necessarily the load-bearing one.

**R5 — Dedicated named section (Weight 2):** The chapter must have a dedicated,
architecturally distinct named section or activity block that develops this competency
and could stand alone as a learning unit. OR the competency must be developed
substantively and deliberately across multiple named sections with the chapter's own
organising logic making this continuity evident.

**R6 — Single structural element (Weight 1):** The chapter must include at least one
explicitly designated structural element (textbook exercise, guided question, student
task) organised around this competency, and that element must not constitute a
dedicated section or architecturally distinct activity block.

**R7 — Zero structural elements (Incidental):** The chapter's content surfaces the
competency, but the chapter's architecture includes zero explicitly designated
structural elements organised around its development.

---

## RAG Legend

| Rating | Meaning |
|---|---|
| GREEN | No violation. Justification names the architectural container, states a transformation the section demonstrably demands, and the transformation corresponds to the C-code. |
| ORANGE | Minor issue — architectural container named but imprecisely, or transformation stated but weakly grounded in what the section demands. Weight assignment defensible but justification needs sharpening. |
| RED | Significant violation — architectural container missing or wrong, transformation not grounded in section demands, weight incorrect, or competency should move between primary and incidental. Must correct before accepting. |

---

## Section 5 — Recommended Corrections

For each Red or Orange finding, state:
- Which field to change (weight, justification, move from primary to incidental, or vice versa)
- What the corrected justification should name: the container, the transformation the
  section demands, and its correspondence to the C-code.

Corrections are recommendations only. No change is made without Kumar's explicit approval.
