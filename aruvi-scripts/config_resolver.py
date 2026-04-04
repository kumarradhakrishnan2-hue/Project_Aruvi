"""
config_resolver.py — patched for DYNAMIC project_root
Resolves all file paths for a given subject_group + grade from aruvi_config.json.
If project_root is "DYNAMIC", derives root from config file's own location.

Constitution path is resolved from mirror/constitutions/competency_mapping/
using the subject_group name — no skill_dir or references/ folder required.

CG and Pedagogy text paths are resolved from mirror/framework/ using the
mirror_framework_filenames patterns in aruvi_config.json — no runtime PDF
extraction.
"""
import json
import sys
from pathlib import Path


def resolve_paths(config_path: str, subject_group: str, grade: str,
                  skill_dir: str = None) -> dict:
    """
    Resolve all paths for the given subject_group + grade.

    skill_dir is accepted for backward-compatibility but is no longer used
    for constitution loading — constitutions are read from mirror/ at runtime.
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"aruvi_config.json not found at: {config_path}\n"
            f"Please create it at your project root."
        )

    config = json.loads(config_path.read_text(encoding="utf-8"))

    # DYNAMIC project_root: derive from config file's own location.
    if config.get("project_root", "DYNAMIC") == "DYNAMIC":
        root = config_path.parent
    else:
        root = Path(config["project_root"])

    subject_config = config["subject_groups"].get(subject_group)
    if not subject_config:
        raise ValueError(
            f"Unknown subject_group: '{subject_group}'. "
            f"Valid options: {list(config['subject_groups'].keys())}"
        )

    stage = None
    for stage_name, grades in subject_config["stages"].items():
        if grade.lower() in grades:
            stage = stage_name
            break
    if not stage:
        valid_grades = [g for gs in subject_config["stages"].values() for g in gs]
        raise ValueError(
            f"Grade '{grade}' not found for subject '{subject_group}'. "
            f"Valid grades: {valid_grades}"
        )

    fw_subdir = subject_config["framework_subdir"]
    fw_base   = root / config["paths"]["framework"] / fw_subdir / stage
    cg_pdf    = fw_base / config["framework_filenames"]["curricular_goals"]
    ped_pdf   = fw_base / config["framework_filenames"]["pedagogy"]

    tb_subdir   = subject_config["textbook_subdir"]
    chapter_dir = root / config["paths"]["textbooks"] / tb_subdir / grade.lower()

    mappings_dir = root / config["paths"]["mappings"]
    output_json  = mappings_dir / config["mapping_output_pattern"].format(
        subject_group=subject_group, grade=grade.lower()
    )
    token_log = root / config["paths"]["token_log"]

    # ── Constitution path — resolved from mirror, no skill_dir required ──────
    constitution_key  = subject_config["constitution_key"]
    mirror_const_base = root / config["paths"]["mirror_constitutions"]
    constitution_path = (
        mirror_const_base
        / "competency_mapping"
        / subject_group
        / f"mapping_constitution_{subject_group}.txt"
    )

    if not constitution_path.exists():
        raise FileNotFoundError(
            f"Constitution file not found: {constitution_path}\n"
            f"Expected: mirror/constitutions/competency_mapping/"
            f"{subject_group}/mapping_constitution_{subject_group}.txt\n"
            f"Extract the source DOCX with pandoc and save it there first."
        )

    # ── Lesson plan and assessment constitution paths ──────────────────────────
    lp_const_root = root / config["paths"]["lp_constitution_root"]
    ac_const_root = root / config["paths"]["assessment_constitution_root"]
    lp_constitution = (
        lp_const_root / subject_group / "lesson_plan_constitution.txt"
    )
    assessment_const = (
        ac_const_root / subject_group / "assessment_constitution.txt"
    )

    # ── CG and Pedagogy text paths — resolved from mirror/framework ───────────
    mirror_fw_base = root / config["paths"]["mirror_framework"] / fw_subdir / stage
    cg_filename  = config["mirror_framework_filenames"]["cg"].format(
        stage=stage, subject_group=subject_group
    )
    ped_filename = config["mirror_framework_filenames"]["pedagogy"].format(
        stage=stage, subject_group=subject_group
    )
    cg_text_path      = mirror_fw_base / cg_filename
    pedagogy_text_path = mirror_fw_base / ped_filename

    # ── Mirror chapter output directories ────────────────────────────────────
    grade_dir = f"grade_{grade.lower()}"
    mirror_summaries = (
        root / config["paths"]["mirror_summaries_dir"]
        / subject_group / grade_dir / "summaries"
    )
    mirror_mappings_out = (
        root / config["paths"]["mirror_mappings_dir"]
        / subject_group / grade_dir / "mappings"
    )

    return {
        "project_root":              str(root),
        "subject_group":             subject_group,
        "grade":                     grade.lower(),
        "stage":                     stage,
        # Source PDFs (kept for reference; not read at runtime)
        "cg_pdf":                    str(cg_pdf),
        "pedagogy_pdf":              str(ped_pdf),
        # Mirror .txt — runtime reads
        "cg_text_path":              str(cg_text_path),
        "pedagogy_text_path":        str(pedagogy_text_path),
        # Chapters
        "chapter_dir":               str(chapter_dir),
        # Outputs
        "output_json":               str(output_json),
        "token_log":                 str(token_log),
        "mappings_dir":              str(mappings_dir),
        # Mirror chapter outputs
        "mirror_summaries":          str(mirror_summaries),
        "mirror_mappings_out":       str(mirror_mappings_out),
        # Competency mapping constitution
        "constitution_path":         str(constitution_path),
        "constitution_key":          constitution_key,
        # Lesson plan and assessment constitutions
        "lp_constitution":           str(lp_constitution),
        "assessment_const":          str(assessment_const),
        # Existence flags
        "cg_pdf_exists":             cg_pdf.exists(),
        "pedagogy_pdf_exists":       ped_pdf.exists(),
        "cg_text_path_exists":       cg_text_path.exists(),
        "pedagogy_text_path_exists": pedagogy_text_path.exists(),
        "chapter_dir_exists":        chapter_dir.exists(),
        "constitution_path_exists":  constitution_path.exists(),
        "lp_constitution_exists":    lp_constitution.exists(),
        "assessment_const_exists":   assessment_const.exists(),
    }


def validate_paths(paths: dict, require_chapters: bool = True) -> list:
    warnings = []
    if not paths["cg_text_path_exists"]:
        warnings.append(
            f"CG mirror .txt not found: {paths['cg_text_path']}\n"
            f"  Extract curricular_goals.pdf with pdfplumber and save it there first."
        )
    if not paths["pedagogy_text_path_exists"]:
        warnings.append(
            f"Pedagogy mirror .txt not found: {paths['pedagogy_text_path']}\n"
            f"  Extract pedagogy.pdf with pdfplumber and save it there first."
        )
    if require_chapters and not paths["chapter_dir_exists"]:
        warnings.append(
            f"Chapter directory not found: {paths['chapter_dir']}"
        )
    if not paths["constitution_path_exists"]:
        warnings.append(
            f"Constitution .txt not found: {paths['constitution_path']}"
        )
    return warnings


def list_chapters(chapter_dir: str) -> list:
    d = Path(chapter_dir)
    if not d.exists():
        return []
    pdfs = sorted(d.glob("*.pdf"))
    return [{"path": str(p), "filename": p.name} for p in pdfs]
