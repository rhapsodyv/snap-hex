"""Change parameters at run time (the web configurator, or build.py --set).

params.py is run again with some of its top-level assignments replaced by other
expressions, so every value derived from them follows, and the modules that read
params are reloaded in import order. apply({}) brings the defaults back.
"""

import ast
import importlib
import sys
from pathlib import Path

HERE = Path(__file__).parent
SOURCE = HERE / "params.py"
DEPENDENT = ["layout", "profiles", "grid", "plug", "assembly", "spring_model"]   # import order


def _assignments(tree):
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            yield node.targets[0].id, node


def parameters():
    """Every top-level assignment of params.py, in file order: name, expression as written,
    its inline comment and the section it is in (the last '# --- ... ---' line above it)."""
    text = SOURCE.read_text()
    lines = text.splitlines()
    sections = {i + 1: line.strip("# -").strip() for i, line in enumerate(lines) if line.startswith("# ---")}
    out = []
    for name, node in _assignments(ast.parse(text)):
        expr = ast.get_source_segment(text, node.value)
        last = lines[node.end_lineno - 1]
        comment = ""
        if "#" in last[node.end_col_offset:]:
            comment = last[node.end_col_offset:].split("#", 1)[1].strip()
        section = next((sections[k] for k in sorted(sections, reverse=True) if k < node.lineno), "")
        out.append({"name": name, "expression": expr, "comment": comment, "section": section})
    return out


def apply(changes):
    """changes: {name: expression text}. Re-runs params.py with them and reloads the
    modules that depend on it; returns the params module."""
    text = SOURCE.read_text()
    tree = ast.parse(text)
    pending = dict(changes)
    for name, node in _assignments(tree):
        if name in pending:
            node.value = ast.parse(str(pending.pop(name)), mode="eval").body
    if pending:
        raise KeyError(f"unknown parameters: {', '.join(sorted(pending))}")
    params = importlib.import_module("params")
    exec(compile(tree, str(SOURCE), "exec"), params.__dict__)
    for name in DEPENDENT:
        if name in sys.modules:
            importlib.reload(sys.modules[name])
    return params


def parse_set(args):
    """['name=expression', ...] from the command line -> {name: expression}."""
    return dict(a.split("=", 1) for a in args)
