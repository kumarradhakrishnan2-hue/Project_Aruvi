---
name: aruvi-kb-refresh
description: >
  Refreshes the Ask Aruvi Q&A knowledge base — reads qa_knowledge_base.json,
  checks every pair for accuracy against the authoritative Aruvi knowledge
  sources (constitutions, design docs, project report), and writes an updated
  JSON and a matching Word document to knowledge_commons/other_commons/.

  USE THIS SKILL whenever the user asks to:
  - Refresh or update the Ask Aruvi knowledge base
  - Add, amend, or delete Q&A pairs in the helpline
  - Run the monthly knowledge base maintenance cycle
  - Verify the Q&A knowledge base against current constitutions or design docs
  - Sync the Word doc and JSON after any Aruvi document update
  - Ensure the Ask Aruvi helpline reflects the latest platform knowledge

  Run once a month or after any constitution/design doc version bump.
  Requires ANTHROPIC_API_KEY in the environment (calls claude-haiku-4-5).
  Cowork session must have mnt/data/ mapped to the Aruvi project root.
---

# Ask Aruvi Knowledge Base Refresh Skill

## What This Skill Does

This skill performs a supervised editorial refresh of the Ask Aruvi Q&A
knowledge base. It does three things in sequence:

1. **Reads** the current `qa_knowledge_base.json` from
   `mirror/ask_aruvi/qa_knowledge_base.json`.
2. **Verifies** every Q&A pair against the authoritative Aruvi documents
   (see knowledge sources below). Flags pairs that are outdated, inaccurate,
   missing, or violate the 80-word answer rule.
3. **Writes** an updated JSON (same path) and a formatted Word document
   (`qa_knowledge_base.docx`) to `knowledge_commons/other_commons/`.

The script never auto-deletes — it produces a diff report for human review
before writing the final output. Kumar confirms, then writes.

---

## Project Paths

| Item | Path |
|------|------|
| Project root | `/Users/kumar_radhakrishnan/main/kumar/AI/Project Aruvi/` |
| Current KB JSON | `mirror/ask_aruvi/qa_knowledge_base.json` |
| Output JSON (updated) | `mirror/ask_aruvi/qa_knowledge_base.json` (overwrite) |
| Output Word doc | `knowledge_commons/other_commons/qa_knowledge_base.docx` |
| .env | Project root `.env` (ANTHROPIC_API_KEY) |

---

## Q&A Knowledge Base Structure

The JSON schema is:

```json
{
  "version": "1.0",
  "last_refreshed": "2026-03-29",
  "categories": {
    "cat_a": {
      "label": "How Aruvi plans lessons",
      "description": "...",
      "pairs": [
        { "q": "Why does my lesson have 5 periods?", "a": "..." },
        ...
      ]
    },
    "cat_b": { ... },
    "cat_c": { ... },
    "cat_d": { ... },
    "cat_e": { ... }
  }
}
```

### Five Categories (fixed — do not add or remove categories)

| Key | Label |
|-----|-------|
| `cat_a` | How Aruvi plans lessons |
| `cat_b` | How Aruvi builds assessments |
| `cat_c` | The competency framework |
| `cat_d` | Using the platform |
| `cat_e` | What Aruvi cannot do |

### 80-Word Hard Limit

Every `"a"` field must be ≤ 80 words. This is enforced at write time —
answers exceeding the limit are trimmed or split before the file is written.

---

## Authoritative Knowledge Sources

These are the only documents the refresh script reads for verification. The
script never traverses the folder tree independently.

| Source document | What it governs |
|-----------------|-----------------|
| `knowledge_commons/Aruvi_Project_Report_V5.docx` | Platform purpose, competency chain, constitutional logic |
| `knowledge_commons/Aruvi_Competency_Mapping_Constitutions_V1_1.docx` | Mapping rules, C-codes, weight logic |
| `knowledge_commons/Aruvi_LessonPlan_Constitution_V1_2.docx` (or latest) | Lesson plan structure, period logic, activities |
| `knowledge_commons/Aruvi_Assessment_Constitution_V1_2_1.docx` (or latest) | Assessment design, question types, scope |
| `knowledge_commons/Aruvi_Ask_Aruvi_Design_V1_1.docx` | Ask Aruvi feature scope, category structure, 80-word rule |
| `knowledge_commons/Aruvi_Optimizer_PeriodAllocation_V1.docx` | Period allocation logic (cat_a and cat_d) |
| `knowledge_commons/Aruvi_Storage_Protocol_V3.docx` | Saving, loading, file formats (cat_d) |
| `mirror/ask_aruvi/forwarded_queries/` | Gaps in current KB — unmatched teacher questions |

> The forwarded_queries/ directory is read as supplementary input only —
> it surfaces recurring unmatched questions that may justify new pairs.
> Reading it is optional; skip if the directory is empty or absent.

---

## Two-Stage Workflow

This skill operates in two mandatory stages with a human review gate between
them. Nothing is written to any file until Stage 2 is explicitly cleared.

---

### Stage 1 — Generate the Proposals Report

```bash
# Verify paths first
ls mnt/data/mirror/ask_aruvi/qa_knowledge_base.json
ls mnt/data/knowledge_commons/other_commons/
ls mnt/data/knowledge_commons/*.docx

# Run Stage 1 — analysis only, no writes
cd mnt/data
python3 aruvi-scripts/refresh_kb.py --propose
```

This produces a **Proposals Report** printed to the console and saved as
`mirror/ask_aruvi/kb_proposals_pending.json` for Stage 2 to consume.

#### Proposals Report format

The report is organised **category by category** in fixed order:
cat_a → cat_b → cat_c → cat_d → cat_e.

Every proposed change is a **numbered proposal** — numbering is global and
sequential across all categories (Proposal 1, 2, 3 … N) so Kumar can
reference any item by number.

```
════════════════════════════════════════════════════════
ASK ARUVI — Q&A KNOWLEDGE BASE: PROPOSALS REPORT
Generated: 2026-03-29
════════════════════════════════════════════════════════

CATEGORY A — How Aruvi plans lessons
  Unchanged: 8 pairs

  Proposal 1 — AMEND
    Q: Why does my lesson have 5 periods?
    Current A: [existing answer]
    Proposed A: [revised answer]
    Reason: LP Constitution V1.4 now uses visual_aids field; answer
            referenced old visual representation language.

  Proposal 2 — DELETE
    Q: Can I add a sixth period to my lesson?
    Current A: [existing answer]
    Reason: Contradicts current period allocation logic in Optimizer doc.

──────────────────────────────────────────────────────
CATEGORY B — How Aruvi builds assessments
  Unchanged: 6 pairs

  Proposal 3 — AMEND
    Q: What is a Central competency?
    Current A: [existing answer]
    Proposed A: [revised answer]
    Reason: Weight terminology updated in Assessment Constitution V1.4.

  Proposal 4 — ADD  [source: forwarded_queries/2026-03.json, query #7]
    Proposed Q: Why do some chapters have more open-task questions?
    Proposed A: [new answer]
    Reason: Recurring unmatched query; derivable from Assessment
            Constitution competency weight rules.

──────────────────────────────────────────────────────
CATEGORY C — The competency framework
  Unchanged: 14 pairs  |  No proposals.

──────────────────────────────────────────────────────
CATEGORY D — Using the platform
  Unchanged: 9 pairs

  Proposal 5 — ADD
    Proposed Q: ...
    Proposed A: ...
    Reason: ...

──────────────────────────────────────────────────────
CATEGORY E — What Aruvi cannot do
  Unchanged: 7 pairs  |  No proposals.

════════════════════════════════════════════════════════
SUMMARY: 5 proposals across 3 categories
  AMEND: 2   DELETE: 1   ADD: 2   Unchanged pairs: 44

Awaiting clearance. Reply with: "Clear all", "Clear N,M,P",
"Clear all except N,M", or inline amendments per proposal.
════════════════════════════════════════════════════════
```

---

### Review Gate — Kumar's Instructions

After reading the Proposals Report, Kumar responds with one of:

- **"Clear all"** — accept every proposal as shown; proceed to Stage 2.
- **"Clear all except N, M"** — accept all; hold proposals N and M
  (dropped from this cycle, not applied).
- **"Clear N, M, P"** — accept only the listed proposals; drop the rest.
- **Inline amendment** — Kumar may revise any proposed answer text before
  clearing: "Clear 1 but change the answer to: [text]". The revised text
  replaces Haiku's proposed answer.

The skill waits at this gate. Nothing is written until Kumar has explicitly
cleared at least one proposal or confirmed no action is needed.

If there are zero proposals across all categories, confirm this to Kumar
and close the cycle without writing.

---

### Stage 2 — Write Cleared Proposals

```bash
# Apply specific proposal numbers
python3 aruvi-scripts/refresh_kb.py --write --proposals 1,3,4,5
# or apply all proposals in the pending file
python3 aruvi-scripts/refresh_kb.py --write --proposals all
```

Stage 2 applies only the cleared proposals. It:

- Applies AMEND changes (using Kumar's revised text if provided, else
  Haiku's proposed text)
- Applies ADD pairs into the correct category
- For DELETE proposals: marks the pair `"flagged_for_deletion": true`
  rather than removing it — Kumar removes flagged pairs manually
- Enforces 80-word limit on all answers (truncates at word boundary with
  ellipsis; logs a warning per truncation)
- Updates `"last_refreshed"` to today's date (ISO format)
- Writes updated JSON to `mirror/ask_aruvi/qa_knowledge_base.json`
- Writes Word document to
  `knowledge_commons/other_commons/qa_knowledge_base.docx`
- Deletes `mirror/ask_aruvi/kb_proposals_pending.json` on success

### Verify outputs

```bash
# Confirm JSON updated
cat mnt/data/mirror/ask_aruvi/qa_knowledge_base.json | python3 -m json.tool | head -40

# Confirm Word doc created
ls -lh mnt/data/knowledge_commons/other_commons/qa_knowledge_base.docx
```

---

## The Refresh Script — What to Prompt Cowork to Build

If `aruvi-scripts/refresh_kb.py` does not yet exist, prompt Cowork to
create it. The full specification follows.

### Script purpose

A Python script with two modes: `--propose` and `--write`.

**`--propose` mode:**

1. Loads the current `qa_knowledge_base.json`.
2. Extracts the authoritative text from each knowledge source document
   using `python-docx` (for .docx files).
3. For each Q&A pair, calls `claude-haiku-4-5` with a system prompt
   instructing it to judge accuracy against the knowledge source excerpt.
   Output schema per pair:
   ```json
   {
     "verdict": "keep" | "amend" | "delete",
     "reason": "one sentence",
     "revised_answer": "amended answer text if verdict is amend, else null"
   }
   ```
4. Scans `forwarded_queries/` (if present) and proposes new ADD pairs for
   recurring unmatched queries.
5. Assembles proposals in category order with global sequential numbering.
6. Prints the Proposals Report to stdout.
7. Saves proposals to `mirror/ask_aruvi/kb_proposals_pending.json`.

**`--write --proposals N,M,P` (or `--proposals all`) mode:**

1. Loads `kb_proposals_pending.json`.
2. Filters to the cleared proposal numbers only.
3. Applies changes as specified in Stage 2 above.
4. Writes JSON and Word doc outputs.
5. Deletes `kb_proposals_pending.json`.

### Word document format

The Word doc is the human-readable reference copy. Format:

- Title: **Ask Aruvi — Q&A Knowledge Base**
- Subtitle: Version, last refreshed date
- One section per category (Heading 1 = category label)
- Category description in italic below heading
- Each Q&A pair as:
  - **Q:** question text (bold)
  - **A:** answer text (normal)
  - Thin dividing line between pairs
- Footer: "Aruvi Knowledge Commons | Internal Document"

Use `python-docx` for generation. Do not use ReportLab for this document.

### Haiku call construction

```python
import anthropic, os

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=300,
    system=(
        "You are an editorial assistant for the Ask Aruvi platform helpline. "
        "Judge whether the given Q&A pair is accurate and current against "
        "the provided knowledge source excerpt. "
        "Respond ONLY in valid JSON. No preamble, no markdown fences."
    ),
    messages=[{
        "role": "user",
        "content": (
            f"KNOWLEDGE SOURCE EXCERPT:\n{source_excerpt}\n\n"
            f"Q&A PAIR:\nQ: {pair['q']}\nA: {pair['a']}\n\n"
            "Return JSON: {\"verdict\": \"keep\"|\"amend\"|\"delete\", "
            "\"reason\": \"one sentence\", "
            "\"revised_answer\": \"text or null\"}"
        )
    }]
)
```

### Category-to-source mapping

| Category | Primary source sections |
|----------|------------------------|
| cat_a | LP Constitution (period logic, activity sequencing) |
| cat_b | Assessment Constitution (question types, competency weight) |
| cat_c | Project Report §2–3, Competency Mapping Constitution |
| cat_d | Storage Protocol, Optimizer doc, Ask Aruvi Design §4 |
| cat_e | Ask Aruvi Design §2.1 (skill boundary), Project Report |

---

## Running Without Cowork (Direct Terminal)

If running directly from Mac terminal (lower cost, no Cowork overhead):

```bash
cd "/Users/kumar_radhakrishnan/main/kumar/AI/Project Aruvi"
source .env  # or: export $(cat .env | xargs)

# Stage 1 — generate proposals, review with Kumar
python3 aruvi-scripts/refresh_kb.py --propose

# Stage 2 — after Kumar's clearance
python3 aruvi-scripts/refresh_kb.py --write --proposals 1,3,4
# or: --proposals all
```

---

## Cost Reference

| Operation | Approximate cost |
|-----------|-----------------|
| Verify ~70 Q&A pairs (Haiku) | ~Rs.0.50–1.00 |
| Propose new pairs from forwarded queries | ~Rs.0.10–0.20 |
| Total per monthly refresh | ~Rs.1.00–1.50 |

Haiku is used for all editorial calls. Sonnet is not needed here.

---

## Hard Rules (Invariants)

- The five category keys (`cat_a`–`cat_e`) are fixed. Never add or remove.
- 80-word limit on every answer is a hard authoring constraint.
- The script never auto-deletes. Deletions require Kumar's explicit review.
- Constitutions, config files, and saved plans are never in scope for the
  knowledge base content. The KB is about platform operation, not platform outputs.
- The Word doc and JSON must always be in sync after a `--write` run.
- `last_refreshed` date must be updated on every `--write` run.
- The script reads only the explicitly listed knowledge sources above.
  It does not traverse the Aruvi folder tree independently.
