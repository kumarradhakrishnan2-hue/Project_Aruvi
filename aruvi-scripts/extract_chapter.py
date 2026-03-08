"""
extract_chapter.py
Extracts clean text and section headings from an NCERT chapter PDF.
Filters decorative/layout tables (>50% None-cell ratio).
Returns: chapter_title, full_text, section_headings
"""

import sys
import json
import re
import pdfplumber


def none_ratio(table):
    """Compute fraction of None cells in a pdfplumber table."""
    if not table or not table[0]:
        return 1.0
    total = sum(len(row) for row in table)
    nones = sum(1 for row in table for cell in row if cell is None)
    return nones / total if total > 0 else 1.0


def extract_chapter(pdf_path: str) -> dict:
    """
    Extract text and headings from a chapter PDF.

    Returns:
        {
            "chapter_title": str,
            "full_text": str,
            "section_headings": list[str],
            "page_count": int
        }
    """
    full_text_parts = []
    section_headings = []

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)

        for page in pdf.pages:
            # Extract plain text
            text = page.extract_text()
            if text:
                full_text_parts.append(text)

            # Extract content tables only (filter decorative ones)
            tables = page.extract_tables()
            for table in tables:
                if none_ratio(table) >= 0.5:
                    continue  # skip decorative/layout tables
                # Flatten clean table rows into text
                for row in table:
                    row_text = " | ".join(cell.strip() for cell in row if cell)
                    if row_text.strip():
                        full_text_parts.append(row_text)

    full_text = "\n".join(full_text_parts)

    # Extract section headings using capitalization and length heuristics
    # NCERT headings are typically ALL CAPS or Title Case, shorter than 80 chars,
    # not ending in punctuation
    lines = full_text.split("\n")
    for line in lines:
        line = line.strip()
        if not line or len(line) > 100:
            continue
        # Heading patterns: ALL CAPS line, or Title Case line 10–80 chars
        is_all_caps = line.isupper() and len(line) >= 5
        is_title_case = (
            line[0].isupper()
            and not line.endswith((".", ",", ";", ":"))
            and 10 <= len(line) <= 80
            and sum(1 for w in line.split() if w[0].isupper()) / max(len(line.split()), 1) > 0.5
        )
        if is_all_caps or is_title_case:
            # Exclude lines that are clearly sentences (contain common sentence words)
            sentence_indicators = [" is ", " are ", " was ", " were ", " the ", " and ", " of "]
            if not any(ind in line.lower() for ind in sentence_indicators):
                section_headings.append(line)

    # Deduplicate while preserving order
    seen = set()
    unique_headings = []
    for h in section_headings:
        if h not in seen:
            seen.add(h)
            unique_headings.append(h)

    # Chapter title: first meaningful heading
    chapter_title = unique_headings[0] if unique_headings else "Unknown Chapter"

    return {
        "chapter_title": chapter_title,
        "full_text": full_text,
        "section_headings": unique_headings,
        "page_count": page_count,
        "char_count": len(full_text)
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_chapter.py <pdf_path> [--json]")
        sys.exit(1)

    pdf_path = sys.argv[1]
    output_json = "--json" in sys.argv

    result = extract_chapter(pdf_path)

    if output_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Chapter Title : {result['chapter_title']}")
        print(f"Pages         : {result['page_count']}")
        print(f"Characters    : {result['char_count']}")
        print(f"Headings found: {len(result['section_headings'])}")
        print("\nSection Headings:")
        for i, h in enumerate(result['section_headings'], 1):
            print(f"  {i:2}. {h}")
        print("\n--- First 1000 chars of text ---")
        print(result['full_text'][:1000])
