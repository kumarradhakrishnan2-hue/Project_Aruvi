"""
run_wrapper.py — ensures aruvi-scripts/call_mapping_api.py (with verify=False
+ socks proxy fix) wins over the read-only skill copy.

runpy.run_path() prepends the script's own directory to sys.path, defeating
any prior sys.path.insert. We use exec() instead so sys.path is never touched
by the runner itself.
"""
import sys
import os

# Insert patched modules dir FIRST, before anything else
_patch_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _patch_dir)

skill_script = os.environ.get("ARUVI_SKILL_SCRIPT")
if not skill_script:
    raise RuntimeError("ARUVI_SKILL_SCRIPT env var not set")

with open(skill_script, encoding="utf-8") as _f:
    _code = compile(_f.read(), skill_script, "exec")

exec(_code, {
    "__name__":    "__main__",
    "__file__":    skill_script,
    "__doc__":     None,
    "__package__": None,
    "__spec__":    None,
    "__builtins__": __builtins__,
})
