"""
run_mapping.py
Orchestrator for the Aruvi chapter mapping pipeline.

All paths are resolved automatically from aruvi_config.json + subject_group + grade.
You never need to specify PDF paths, output paths, or token log paths manually.

Usage:
  # Map specific chapters by number (pilot run)
  python3 run_mapping.py \
    --config  "/Users/.../Project Aruvi/aruvi_config.json" \
    --subject social_sciences \
    --grade   vii \
    --chapters 1 4 8

  # Map ALL chapters in the chapter directory
  python3 run_mapping.py \
    --config  "/Users/.../Project Aruvi/aruvi_config.json" \
    --subject social_sciences \
    --grade   vii \
    --all

  # Dry run: resolve and print all paths without calling API
  python3 run_mapping.py \
    --config  "/Users/.../Project Aruvi/aruvi_config.json" \
    --subject mathematics \
    --grade   ix \
    --dry-run

  # Works identically for any subject/grade combination:
  python3 run_mapping.py --config aruvi_config.json --subject mathematics --grade ix --all
  python3 run_mapping.py --config aruvi_config.json --subject science --grade vi --chapters 1 2 3
  python3 run_mapping.py --config aruvi_config.json --subject languages --grade viii --all
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_resolver import resolve_paths, validate_paths, list_chapters
from extract_chapter  import extract_chapter
from extract_cg       import extract_cg
from call_mapping_api import call_mapping_api


def chapter_number_from_filename(filename: str) -> int | None:
    """Extract chapter number from filename like 'Chapter 01 – Title.pdf'"""
    match = re.search(r'[Cc]hapter\s+(\d+)', filename)
    if match:
        return int(match.group(1))
    # Try leading digits
    match = re.match(r'^(\d+)', filename)
    if match:
        return int(match.group(1))
    return None


def load_existing_mappings(output_path: str) -> dict:
    p = Path(output_path)
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {str(r["chapter_number"]): r for r in data}
    return data


def save_mappings(output_path: str, mappings: dict):
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    sorted_records = sorted(mappings.values(), key=lambda r: r["chapter_number"])
    p.write_text(json.dumps(sorted_records, ensure_ascii=False, indent=2), encoding="utf-8")


def run_single_chapter(chapter_pdf: str, chapter_number: int, paths: dict):
    """Full pipeline for one chapter. Returns record or None on failure."""
    print(f"\n{'='*60}")
    print(f"Chapter {chapter_number}: {Path(chapter_pdf).name}")
    print(f"{'='*60}")

    print("  [1/4] Extracting chapter text...")
    chapter_data = extract_chapter(chapter_pdf)
    print(f"        {chapter_data['char_count']:,} chars · "
          f"{len(chapter_data['section_headings'])} headings · "
          f"{chapter_data['page_count']} pages")

    print("  [2/4] Loading Curricular Goals...")
    cg_data = extract_cg(paths["cg_text_path"])
    if cg_data["cg_count"] == 0:
        print("        ✗ ERROR: No CGs extracted — check CG PDF")
        return None
    print(f"        {cg_data['cg_count']} CGs · {cg_data['c_code_count']} C-codes")

    print("  [3/4 + 4/4] Two-call Claude pipeline...")
    record = call_mapping_api(
        chapter_data      = chapter_data,
        cg_data           = cg_data,
        subject_group     = paths["subject_group"],
        stage             = paths["stage"],
        grade             = paths["grade"],
        chapter_number    = chapter_number,
        constitution_path = paths["constitution_path"],
        token_log_path    = paths["token_log"]
    )

    # ── Write mirror summary .txt ────────────────────────────────────────────
    nn = f"{chapter_number:02d}"
    project_root = Path(paths["project_root"])

    summary_dir = Path(paths["mirror_summaries"])
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary_file = summary_dir / f"ch_{nn}_summary.txt"
    summary_file.write_text(record["chapter_summary"], encoding="utf-8")

    # relative path from project root — stored as summary_path in mapping JSON
    summary_path_rel = str(summary_file.relative_to(project_root))

    # ── Write mirror mapping .json (no chapter_summary, adds summary_path) ───
    mappings_out_dir = Path(paths["mirror_mappings_out"])
    mappings_out_dir.mkdir(parents=True, exist_ok=True)
    mapping_file = mappings_out_dir / f"ch_{nn}_mapping.json"
    mapping_record = {k: v for k, v in record.items() if k != "chapter_summary"}
    mapping_record["summary_path"] = summary_path_rel
    mapping_file.write_text(
        json.dumps(mapping_record, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── Update combined master JSON (archive — includes summary) ─────────────
   # mappings = load_existing_mappings(paths["output_json"])
    #mappings[str(chapter_number)] = record
    #save_mappings(paths["output_json"], mappings)

    weight_display = record.get('chapter_weight', record.get('effort_index', '—'))
    print(f"\n  ✓ Saved  |  weight={weight_display}  "
          f"primary={len(record['primary'])}  "
          f"summary={len(record['chapter_summary'].split())}w")
    print(f"    Summary : {summary_path_rel}")
    print(f"    Mapping : {str(mapping_file.relative_to(project_root))}")
    for comp in record["primary"]:
        print(f"    [{comp.get('weight', '—')}] {comp['c_code']} — {comp['justification'][:70]}...")

    return record


def _find_config() -> str | None:
    """Auto-detect aruvi_config.json from cwd, script dir, or script's parent."""
    for candidate in [Path.cwd(), Path(__file__).parent, Path(__file__).parent.parent]:
        p = candidate / "aruvi_config.json"
        if p.exists():
            return str(p)
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Aruvi Chapter Mapping — auto-resolves all paths from config"
    )
    parser.add_argument("--config",  default=None,
                        help="Path to aruvi_config.json (auto-detected if omitted)")
    parser.add_argument("--subject", required=True,
                        choices=["social_sciences", "languages", "mathematics", "science"])
    parser.add_argument("--grade",   required=True,
                        help="Grade in roman numerals e.g. vii, ix")
    parser.add_argument("--chapters", "--chapter", nargs="+", type=int,
                        help="Specific chapter numbers to map (e.g. --chapters 1 4 8)")
    parser.add_argument("--all",     action="store_true",
                        help="Map all chapters found in the chapter directory")
    parser.add_argument("--dry-run", action="store_true",
                        help="Resolve paths and list chapters without calling API")
    parser.add_argument("--skill-dir", default=None,
                        help="Deprecated — no longer used. Kept for backward compatibility.")
    args = parser.parse_args()

    if not args.chapters and not args.all and not args.dry_run:
        parser.error("Specify --chapters N [N ...], --all, or --dry-run")

    # ── Resolve config path ──────────────────────────────────────────────────
    config_path = args.config or _find_config()
    if not config_path:
        parser.error(
            "Could not auto-detect aruvi_config.json — provide --config PATH"
        )

    # ── Resolve all paths ────────────────────────────────────────────────────
    paths = resolve_paths(config_path, args.subject, args.grade)
    warnings = validate_paths(paths)

    print(f"\nAruvi Chapter Mapping")
    print(f"Subject : {paths['subject_group']}  |  Grade: {paths['grade'].upper()}  "
          f"|  Stage: {paths['stage']}")
    print(f"Config  : {config_path}")
    print(f"CG text : {paths['cg_text_path']}  {'✓' if paths['cg_text_path_exists'] else '✗'}")
    print(f"Pedagogy: {paths['pedagogy_text_path']}  {'✓' if paths['pedagogy_text_path_exists'] else '✗'}")
    print(f"Chapters: {paths['chapter_dir']}  {'✓' if paths['chapter_dir_exists'] else '✗'}")
    print(f"Tokens  : {paths['token_log']}")
    print(f"Constitution: {paths['constitution_path']}  "
          f"{'✓' if paths['constitution_path_exists'] else '✗'}")

    if warnings:
        print(f"\n⚠ Path warnings:")
        for w in warnings:
            print(f"  {w}")
        if not args.dry_run:
            print("Cannot proceed — resolve path issues first.")
            sys.exit(1)

    # ── List available chapters ──────────────────────────────────────────────
    available = list_chapters(paths["chapter_dir"])
    print(f"\nChapters found in directory: {len(available)}")
    for c in available:
        num = chapter_number_from_filename(c["filename"])
        print(f"  [{num or '?':>2}] {c['filename']}")

    if args.dry_run:
        print("\nDry run complete — no API calls made.")
        return

    # ── Select chapters to process ───────────────────────────────────────────
    if args.all:
        to_process = []
        for c in available:
            num = chapter_number_from_filename(c["filename"])
            if num:
                to_process.append((c["path"], num))
            else:
                print(f"  ⚠ Skipping (can't parse chapter number): {c['filename']}")
    else:
        # Map requested chapter numbers to file paths
        num_to_path = {}
        for c in available:
            num = chapter_number_from_filename(c["filename"])
            if num:
                num_to_path[num] = c["path"]
        to_process = []
        for n in sorted(args.chapters):
            if n in num_to_path:
                to_process.append((num_to_path[n], n))
            else:
                print(f"  ⚠ Chapter {n} not found in {paths['chapter_dir']}")

    if not to_process:
        print("No chapters to process.")
        sys.exit(1)

    print(f"\nWill map {len(to_process)} chapter(s): "
          f"{[n for _, n in to_process]}")

    # ── Skip already-mapped chapters ────────────────────────────────────────
    existing = load_existing_mappings(paths["output_json"])
    already_done = [n for _, n in to_process if str(n) in existing]
    if already_done:
        print(f"Already mapped (will overwrite): {already_done}")

    # ── Run mapping ──────────────────────────────────────────────────────────
    succeeded, failed = [], []

    for chapter_pdf, chapter_num in to_process:
        try:
            record = run_single_chapter(chapter_pdf, chapter_num, paths)
            if record:
                succeeded.append(chapter_num)
            else:
                failed.append((chapter_num, "extraction returned None"))
        except Exception as e:
            print(f"\n  ✗ FAILED Chapter {chapter_num}: {e}")
            failed.append((chapter_num, str(e)))

    # ── Final summary ────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"RUN COMPLETE")
    print(f"Succeeded : {len(succeeded)} chapters {succeeded}")
    if failed:
        print(f"Failed    : {len(failed)}")
        for num, err in failed:
            print(f"  Chapter {num}: {err}")

    # Token log totals for this run
    token_log = Path(paths["token_log"])
    if token_log.exists():
        import csv
        with open(token_log, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        run_rows = [r for r in rows
                    if r.get("subject") == paths["subject_group"]
                    and r.get("grade") == paths["grade"]
                    and int(r.get("chapter_number", 0)) in succeeded]
        if run_rows:
            total_in   = sum(int(r["input_tokens"])  for r in run_rows)
            total_out  = sum(int(r["output_tokens"]) for r in run_rows)
            total_cost = sum(float(r["cost_inr"])    for r in run_rows)
            print(f"\nToken totals ({len(run_rows)} API calls across {len(succeeded)} chapters):")
            print(f"  Input  : {total_in:,} tokens")
            print(f"  Output : {total_out:,} tokens")
            print(f"  Cost   : Rs.{total_cost:.2f}")
            n_ch = len(succeeded); print(f"  Per ch : Rs.{total_cost/n_ch:.2f} average (2 calls per chapter)")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
