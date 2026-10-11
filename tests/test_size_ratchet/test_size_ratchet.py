import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SEED = "def big():\n    y = 1\n    return y\n"


def run(repo, *args, env=None, input=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "GITHEAD_"))}
    e.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    e.update(env or {})
    return subprocess.run(args, cwd=repo, env=e, capture_output=True, text=True, input=input)


@pytest.fixture
def repo(tmp_path):
    hooks = tmp_path / ".githooks"
    hooks.mkdir()
    (tmp_path / "scripts").mkdir()
    shutil.copy(ROOT / "scripts/size_ratchet.py", tmp_path / "scripts")
    shutil.copy(ROOT / ".githooks/commit-msg", hooks)
    (hooks / "pre-merge-commit").write_text(
        '#!/bin/sh\nexec python3 "$(git rev-parse --show-toplevel)/scripts/size_ratchet.py" --if-merge\n'
    )
    for h in hooks.iterdir():
        h.chmod(0o755)
    (tmp_path / "agent_api").mkdir()
    (tmp_path / "agent_api/a.py").write_text(SEED)
    run(tmp_path, "git", "init", "-q", "-b", "main")
    run(tmp_path, "git", "add", "-A")
    run(tmp_path, "git", "commit", "-qm", "seed")
    run(tmp_path, "git", "config", "core.hooksPath", ".githooks")
    return tmp_path


def grow(repo, lines=2, path="agent_api/a.py", prefix="v"):
    with open(repo / path, "a") as f:
        f.write("".join(f"{prefix}{i} = {i}\n" for i in range(lines)))
    run(repo, "git", "add", path)


def commit(repo, msg):
    return run(repo, "git", "commit", "-qm", msg)


def test_chore_growth_refused(repo):
    grow(repo)
    r = commit(repo, "chore: tidy")
    assert r.returncode != 0 and "must not add" in r.stderr


def test_chore_comment_and_blank_growth_allowed(repo):
    with open(repo / "agent_api/a.py", "a") as f:
        f.write("\n# note\n")
    run(repo, "git", "add", "-A")
    assert commit(repo, "refactor: comment").returncode == 0


def test_chore_shrink_allowed(repo):
    (repo / "agent_api/a.py").write_text("def big():\n    return 1\n")
    run(repo, "git", "add", "-A")
    assert commit(repo, "style: shrink").returncode == 0


def test_out_of_scope_and_tests_not_counted(repo):
    (repo / "tests").mkdir()
    (repo / "tests/test_x.py").write_text("a = 1\nb = 2\n")
    (repo / "scripts/other.py").write_text("a = 1\n")
    run(repo, "git", "add", "-A")
    assert commit(repo, "test: add").returncode == 0


def test_root_py_in_scope(repo):
    (repo / "top.py").write_text("a = 1\n")
    run(repo, "git", "add", "-A")
    assert commit(repo, "docs: x").returncode != 0


def test_fix_limit(repo):
    grow(repo, 41)
    r = commit(repo, "fix: big")
    assert r.returncode != 0 and "at most 40" in r.stderr
    assert commit(repo, "fix: big\n\nGrowth: needed").returncode == 0


def test_fix_small_ok(repo):
    grow(repo, 40)
    assert commit(repo, "fix: small").returncode == 0


def test_feat_needs_growth(repo):
    grow(repo, 1)
    r = commit(repo, "feat(x): new")
    assert r.returncode != 0 and "needs a reason" in r.stderr
    assert commit(repo, "feat: new\n\nGrowth: new thing").returncode == 0


def test_new_long_function_refused_existing_ok(repo):
    body = "def long_one():\n" + "".join(f"    v{i} = {i}\n" for i in range(85))
    with open(repo / "agent_api/a.py", "a") as f:
        f.write(body)
    run(repo, "git", "add", "-A")
    r = commit(repo, "feat: long\n\nGrowth: g")
    assert r.returncode != 0 and "long_one" in r.stderr


def test_size_override_printed(repo):
    grow(repo)
    r = commit(repo, "chore: tidy\n\nSize-Override: generated table")
    assert r.returncode == 0 and "Size-Override in effect: generated table" in r.stdout + r.stderr


def test_commit_dash_F(repo):
    grow(repo)
    msg = repo / "msg.txt"
    msg.write_text("chore: tidy\n")
    r = run(repo, "git", "commit", "-q", "-F", str(msg))
    assert r.returncode != 0 and "must not add" in r.stderr


def test_editor_commit(repo):
    grow(repo)
    ed = repo / "ed.sh"
    ed.write_text('#!/bin/sh\nprintf "chore: tidy\\n" > "$1"\n')
    ed.chmod(0o755)
    r = run(repo, "git", "commit", "-q", env={"GIT_EDITOR": str(ed)})
    assert r.returncode != 0 and "must not add" in r.stderr
    ed.write_text('#!/bin/sh\nprintf "feat: t\\n\\nGrowth: yes\\n" > "$1"\n')
    assert run(repo, "git", "commit", "-q", env={"GIT_EDITOR": str(ed)}).returncode == 0


def test_branch_commits_not_judged(repo):
    run(repo, "git", "checkout", "-q", "-b", "br")
    grow(repo)
    assert commit(repo, "chore: whatever").returncode == 0


def merge_setup(repo, branch_msg):
    run(repo, "git", "checkout", "-q", "-b", "br")
    grow(repo, 1)
    assert commit(repo, branch_msg).returncode == 0
    run(repo, "git", "checkout", "-q", "main")
    (repo / "side.txt").write_text("s\n")
    run(repo, "git", "add", "side.txt")
    assert commit(repo, "docs: side").returncode == 0


def test_no_ff_merge_judged_by_branch_types(repo):
    merge_setup(repo, "feat: grows")
    r = run(repo, "git", "merge", "--no-ff", "br", "-m", "merge: br")
    assert r.returncode != 0 and "needs a reason" in r.stderr + r.stdout


def test_no_ff_merge_with_growth_passes(repo):
    merge_setup(repo, "feat: grows\n\nGrowth: new")
    assert run(repo, "git", "merge", "--no-ff", "br", "-m", "merge: br").returncode == 0
