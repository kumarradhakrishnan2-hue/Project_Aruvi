"""
config_resolver.py — patched for DYNAMIC project_root
Resolves all file paths for a given subject_group + grade from aruvi_config.json.
If project_root is "DYNAMIC", derives root from config file's own location.
"""
import json
import sys
from pathlib import Path


def resolve_paths(config_path: str, subject_group: str, grade: str,
                  skill_dir: str = None) -> dict:
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"aruvi_config.json not found at: {config_path}\n"
            f"Please create it at your project root using the template in "
            f"references/aruvi_config.json"
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

    if skill_dir is None:
        # aruvi-scripts/ is peer to skill root — go up one to reach skill root
        # But if we're running from the skill's own scripts/, go up one too.
        # Best: look for references/ relative to this file first, then fall back.
        _this_dir = Path(__file__).parent
        if (_this_dir / "references").exists():
            skill_dir = _this_dir
        elif (_this_dir.parent / "references").exists():
            skill_dir = _this_dir.parent
        else:
            # Fall back to the original skill location
            skill_dir = _this_dir.parent
    else:
        skill_dir = Path(skill_dir)

    constitution_key  = subject_config["constitution_key"]
    constitution_path = skill_dir / "references" / f"{constitution_key}.md"

    if not constitution_path.exists():
        raise FileNotFoundError(
            f"Constitution file not found: {constitution_path}\n"
            f"Expected: references/{constitution_key}.md in the skill directory"
        )

    return {
        "subject_group":      subject_group,
        "grade":              grade.lower(),
        "stage":              stage,
        "cg_pdf":             str(cg_pdf),
        "pedagogy_pdf":       str(ped_pdf),
        "chapter_dir":        str(chapter_dir),
        "output_json":        str(output_json),
        "token_log":          str(token_log),
        "mappings_dir":       str(mappings_dir),
        "constitution_path":  str(constitution_path),
        "constitution_key":   constitution_key,
        "cg_pdf_exists":      cg_pdf.exists(),
        "pedagogy_pdf_exists": ped_pdf.exists(),
        "chapter_dir_exists": chapter_dir.exists(),
    }


def validate_paths(paths: dict, require_chapters: bool = True) -> list:
    warnings = []
    if not paths["cg_pdf_exists"]:
        warnings.append(
            f"Curricular Goals PDF not found: {paths['cg_pdf']}\n"
            f"  Expected filename: curricular_goals.pdf"
        )
    if require_chapters and not paths["chapter_dir_exists"]:
        warnings.append(
            f"Chapter directory not found: {paths['chapter_dir']}"
        )
    return warnings


def list_chapters(chapter_dir: str) -> list:
    d = Path(chapter_dir)
    if not d.exists():
        return []
    pdfs = sorted(d.glob("*.pdf"))
    return [{"path": str(p), "filename": p.name} for p in pdfs]
