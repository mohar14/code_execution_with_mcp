import ast
import os
import re
import subprocess
import sys

GATED = ("chore", "refactor", "docs", "test", "style")
ROOTS = ("agent_api/", "mcp_server/", "gradio_ui/")
MAX_FUNC = 80
MAX_FIX = 40
TYPE_RE = re.compile(r"^(chore|refactor|docs|test|style|fix|feat)(?:\([^)]*\))?!?:")


def git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else None


def in_scope(path):
    if not path.endswith(".py"):
        return False
    return path.startswith(ROOTS) or "/" not in path


def code_lines(text):
    return sum(1 for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#"))


def func_lengths(text):
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    out = {}

    def walk(node, prefix):
        for ch in ast.iter_child_nodes(node):
            named = isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            if named:
                q = prefix + ch.name
                if not isinstance(ch, ast.ClassDef):
                    out[q] = ch.end_lineno - ch.lineno + 1
                walk(ch, q + ".")
            else:
                walk(ch, prefix)

    walk(tree, "")
    return out


def measure():
    delta, files, long_funcs = 0, [], []
    names = git("diff", "--cached", "--name-only", "--no-renames", "HEAD") or ""
    for path in filter(in_scope, names.split("\n")):
        old = git("show", f"HEAD:{path}")
        new = git("show", f":{path}") or ""
        d = code_lines(new) - (code_lines(old) if old else 0)
        delta += d
        if d:
            files.append((path, d))
        before = func_lengths(old or "")
        for name, n in func_lengths(new).items():
            if n > MAX_FUNC and name not in before:
                long_funcs.append((path, name, n))
    return delta, files, long_funcs


def merged_heads(env):
    heads = []
    gitdir = git("rev-parse", "--git-dir").strip()
    mh = os.path.join(gitdir, "MERGE_HEAD")
    if os.path.exists(mh):
        heads += open(mh).read().split()
    heads += [k[len("GITHEAD_"):] for k in env if k.startswith("GITHEAD_")]
    return list(dict.fromkeys(heads))


def message_text(path):
    lines = open(path, errors="replace").read().splitlines()
    return "\n".join(ln for ln in lines if not ln.startswith("#"))


def collect(msg_file, env):
    heads = merged_heads(env)
    if heads:
        subjects, bodies = [], []
        for h in heads:
            subjects += (git("log", "--format=%s", f"HEAD..{h}") or "").splitlines()
            bodies.append(git("log", "--format=%B", f"HEAD..{h}") or "")
        return subjects, "\n".join(bodies)
    text = message_text(msg_file) if msg_file else ""
    return text.strip().split("\n", 1)[:1], text


def commit_kind(subjects):
    types = {m.group(1) for s in subjects if (m := TYPE_RE.match(s.strip()))}
    if "feat" in types:
        return "feat"
    if "fix" in types:
        return "fix"
    return next((t for t in GATED if t in types), None)


def trailer(text, key):
    m = re.search(rf"^{key}:[ \t]*(\S.*)$", text, re.M)
    return m.group(1).strip() if m else None


def judge(kind, delta, top, growth):
    if kind in GATED and delta > 0:
        return f"a {kind}: commit must not add non-test code; Python code lines grew by {delta} ({top}). Shrink it, or use feat:/fix: with 'Growth: <reason>'."
    if kind == "fix" and delta > MAX_FIX and not growth:
        return f"a fix: commit may add at most {MAX_FIX} code lines; this adds {delta} ({top}). Trim it or add 'Growth: <reason>'."
    if kind == "feat" and delta > 0 and not growth:
        return f"a feat: commit that adds code needs a reason; it adds {delta} lines ({top}). Add 'Growth: <reason>'."
    return None


def problems(kind, delta, files, long_funcs, growth):
    top = ", ".join(f"{p} {d:+d}" for p, d in sorted(files, key=lambda x: -abs(x[1]))[:4])
    found = [judge(kind, delta, top, growth)]
    found += [f"new function {q} in {p} is {n} lines (limit {MAX_FUNC})." for p, q, n in long_funcs]
    return [f for f in found if f]


def main(argv, env=os.environ):
    msg_file = argv[argv.index("--msg-file") + 1] if "--msg-file" in argv else None
    branch = (git("symbolic-ref", "--short", "-q", "HEAD") or "").strip()
    if branch != env.get("SIZE_RATCHET_BRANCH", "main"):
        return 0
    if "--if-merge" in argv and not merged_heads(env):
        return 0
    delta, files, long_funcs = measure()
    subjects, text = collect(msg_file, env)
    found = problems(commit_kind(subjects), delta, files, long_funcs, trailer(text, "Growth"))
    override = trailer(text, "Size-Override")
    if found and override:
        print(f"size-ratchet: Size-Override in effect: {override} (skipped: {'; '.join(found)})")
        return 0
    if found:
        print("size-ratchet: " + "\nsize-ratchet: ".join(found) + "\nA deliberate exception: a 'Size-Override: <reason>' line in the message.", file=sys.stderr)
        return 1
    if override:
        print(f"size-ratchet: Size-Override given: {override} (nothing needed it)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
