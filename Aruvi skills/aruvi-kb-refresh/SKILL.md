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
| `knowledge_commons/Aruvi_Storage_Protocol_V2.docx` | Saving, loading, file formats (cat_d) |
| `mirror/ask_aruvi/forwarded_queries/` | Gaps in current KB — unmatched teacher questions |

> The forwarded_queries/ directory is read as supplementary input only —
> it surfaces recurring unmatched questions that may justify new pairs.
> Reading it is optional; skip if the directory is empty or absent.

---

## How to Run (Cowork)

### Step 1 — Verify paths

```bash
# Check KB file exists
ls mnt/data/mirror/ask_aruvi/qa_knowledge_base.json

# Check output dir exists
ls mnt/data/knowledge_commons/other_commons/

# Check knowledge sources exist
ls mnt/data/knowledge_commons/*.docx
```

### Step 2 — Run the refresh script

```bash
cd mnt/data
python3 aruvi-scripts/refresh_kb.py --dry-run
```

The `--dry-run` flag produces the diff report only — no files are written.
Review the report with Kumar before proceeding.

```bash
# After Kumar confirms, write the outputs:
python3 aruvi-scripts/refresh_kb.py --write
```

### Step 3 — Verify outputs

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

A Python script that:

1. Loads the current `qa_knowledge_base.json`.
2. Extracts the authoritative text from each knowledge source document
   using `python-docx` (for .docx files).
3. For each Q&A pair, calls `claude-haiku-4-5` with:
   - System prompt: *You are an editorial assistant for the Ask Aruvi platform
     helpline. Your job is to judge whether each Q&A pair is accurate,
     current, and correctly scoped against the provided knowledge sources.
     Respond in JSON only.*
   - Context: the pair's question and answer, plus the relevant section of
     the knowledge source for that category.
   - Output schema:
     ```json
     {
       "verdict": "keep" | "amend" | "delete",
       "reason": "one sentence",
       "revised_answer": "amended answer text if verdict is amend, else null"
     }
     ```
4. Separately scans `forwarded_queries/` (if present) and proposes new
   Q&A pairs for unmatched recurring queries. Presents them as ADD
   candidates in the diff report.
5. Generates a diff report (plain text, printed to stdout) listing:
   - KEEP: count of pairs with no changes
   - AMEND: each amended pair with old → new answer
   - DELETE: each pair flagged for deletion with reason
   - ADD: each proposed new pair with source (forwarded query reference)
6. In `--write` mode:
   - Applies all AMEND and ADD changes
   - Does NOT delete flagged pairs automatically — marks them with a
     `"flagged_for_deletion": true` field instead. Kumar removes manually.
   - Enforces 80-word limit on all answers (truncate at word boundary with
     ellipsis if needed; log a warning per truncation)
   - Updates `"last_refreshed"` to today's date (ISO format)
   - Writes updated JSON to `mirror/ask_aruvi/qa_knowledge_base.json`
   - Writes Word document to
     `knowledge_commons/other_commons/qa_knowledge_base.docx`

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
python3 aruvi-scripts/refresh_kb.py --dry-run
# review diff report
python3 aruvi-scripts/refresh_kb.py --write
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
