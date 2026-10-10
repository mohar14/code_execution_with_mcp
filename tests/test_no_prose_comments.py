import ast
import io
import re
import subprocess
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORY_RE = re.compile(
    r"previously|used to be|historically|no longer|formerly|legacy|rationale|DECISIONS\.md|see docs/",
    re.IGNORECASE,
)
MAX_LINES = 2
DOC_NODES = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _tracked_py() -> list[Path]:
    out = subprocess.check_output(["git", "ls-files", "*.py"], cwd=ROOT, text=True)
    return [ROOT / p for p in out.split() if p != "tests/test_no_prose_comments.py"]


def _comment_blocks(text: str) -> list[tuple[int, str]]:
    blocks: list[tuple[int, list[str]]] = []
    prev_line = -2
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type != tokenize.COMMENT:
            continue
        line = tok.start[0]
        if line == 1 and tok.string.startswith("#!"):
            continue
        if line == prev_line + 1 and blocks:
            blocks[-1][1].append(tok.string)
        else:
            blocks.append((line, [tok.string]))
        prev_line = line
    return [(ln, "\n".join(c)) for ln, c in blocks]


def _is_agent_facing(rel: str, node: ast.AST) -> bool:
    # Runtime-read docstrings: mcp_server/tools/* (list_available_tools, read_docstring) and
    # @mcp.tool/@mcp.prompt functions (FastMCP descriptions). Must stay byte-identical.
    if rel.startswith("mcp_server/tools/"):
        return True
    return any(
        ast.unparse(d).startswith(("mcp.tool", "mcp.prompt"))
        for d in getattr(node, "decorator_list", [])
    )


def test_comments_stay_short_and_free_of_history():
    offenders = []
    for path in _tracked_py():
        rel = path.relative_to(ROOT).as_posix()
        for line, block in _comment_blocks(path.read_text()):
            if block.count("\n") + 1 > MAX_LINES or HISTORY_RE.search(block):
                offenders.append(f"{rel}:{line} {block[:60]!r}")
    assert not offenders, "prose comment(s):\n" + "\n".join(offenders)


def test_docstrings_stay_short_and_free_of_history():
    offenders = []
    for path in _tracked_py():
        rel = path.relative_to(ROOT).as_posix()
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, DOC_NODES):
                continue
            doc = ast.get_docstring(node, clean=True)
            if doc is None:
                continue
            if _is_agent_facing(rel, node):
                continue
            if HISTORY_RE.search(doc) or doc.count("\n") + 1 > MAX_LINES:
                name = getattr(node, "name", "<module>")
                offenders.append(f"{rel}:{getattr(node, 'lineno', 1)} {name}")
    assert not offenders, "prose docstring(s):\n" + "\n".join(offenders)
