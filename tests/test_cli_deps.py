import subprocess

import pytest

from knowledge import cli, db, lifecycle, scan
from knowledge.config import load_config
from tests.conftest import write_knowledge_toml


def _init_code_repo(root):
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "T"], check=True)
    (root / "app" / "platform" / "(menuLayout)" / "assets").mkdir(parents=True)
    (root / "app" / "platform" / "(menuLayout)" / "assets" / "page.tsx").write_text("x\n")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "init"], check=True,
                   capture_output=True)


@pytest.fixture
def working(repo, monkeypatch):
    """The shared `repo` fixture's knowledge.toml points code_repo at "../code" — a
    sibling of tmp_path that would collide with every other test sharing the same pytest
    basetemp. Point it at a real git repo living inside tmp_path instead."""
    monkeypatch.chdir(repo.root)
    write_knowledge_toml(repo.root, code_repo="code")
    _init_code_repo(repo.root / "code")
    conn = db.connect(repo)
    scan.scan(conn, repo)
    db.save(conn, repo)
    return repo


def run(argv):
    return cli.build_parser().parse_args(argv)


def test_dep_list_add_remove_round_trips(working, capsys):
    args = run(["dep", "list", "assets"])
    assert args.handler(args) == 0
    out = capsys.readouterr().out
    assert "app/**/assets/page.tsx" in out
    assert "manual (0):" in out

    args = run(["dep", "add", "assets", "app/**/assets/page.tsx", "--note", "same as derived"])
    assert args.handler(args) == 0
    assert "assets now depends on app/**/assets/page.tsx" in capsys.readouterr().out

    args = run(["dep", "list", "assets"])
    args.handler(args)
    out = capsys.readouterr().out
    assert "manual (1):" in out
    assert "app/**/assets/page.tsx" in out

    args = run(["dep", "remove", "assets", "app/**/assets/page.tsx"])
    assert args.handler(args) == 0
    assert "assets no longer depends on app/**/assets/page.tsx" in capsys.readouterr().out

    conn = db.connect(working)
    assert list(conn.execute(
        "SELECT glob FROM spec_dependency WHERE spec_id='assets'"
    )) == []


def test_dep_add_warns_when_the_glob_matches_nothing(working, capsys):
    args = run(["dep", "add", "assets", "modules/server/submoduels/assets/**"])
    assert args.handler(args) == 0
    out = capsys.readouterr().out
    assert "warning: this glob matches no file in the code repository today" in out


def test_dep_add_does_not_warn_when_the_glob_matches_something(working, capsys):
    args = run(["dep", "add", "assets", "app/**/assets/page.tsx"])
    assert args.handler(args) == 0
    out = capsys.readouterr().out
    assert "warning" not in out


def test_dep_add_without_a_glob_returns_a_usage_message(working, capsys):
    args = run(["dep", "add", "assets"])
    assert args.handler(args) == 1
    out = capsys.readouterr().out
    assert "usage: knowledge dep add" in out

    conn = db.connect(working)
    assert list(conn.execute(
        "SELECT glob FROM spec_dependency WHERE spec_id='assets'"
    )) == []


def test_dep_remove_without_a_glob_returns_a_usage_message(working, capsys):
    args = run(["dep", "remove", "assets"])
    assert args.handler(args) == 1
    out = capsys.readouterr().out
    assert "usage: knowledge dep remove" in out


def test_dep_add_without_a_configured_code_repo_fails_clearly(repo, capsys, monkeypatch):
    """`dep add` validates the glob against the code repository's tracked files, so unlike
    `list`/`remove` it needs one configured. Guard it the same way `stale` is guarded rather
    than letting the git call underneath run against a nonexistent path."""
    monkeypatch.chdir(repo.root)
    write_knowledge_toml(repo.root, code_repo="")
    conn = db.connect(repo)
    scan.scan(conn, repo)
    db.save(conn, repo)

    args = run(["dep", "add", "assets", "app/**/assets/page.tsx"])
    assert args.handler(args) == 1
    assert "no code repository configured" in capsys.readouterr().err

    conn = db.connect(repo)
    assert list(conn.execute(
        "SELECT glob FROM spec_dependency WHERE spec_id='assets'"
    )) == []


def test_dep_list_works_without_a_configured_code_repo(repo, capsys, monkeypatch):
    """`list` only reads the graph and the database — it must keep working even when
    repo.code_repo is unset, unlike `add`."""
    monkeypatch.chdir(repo.root)
    write_knowledge_toml(repo.root, code_repo="")
    conn = db.connect(repo)
    scan.scan(conn, repo)
    db.save(conn, repo)

    args = run(["dep", "list", "assets"])
    assert args.handler(args) == 0
    assert "derived from the graph" in capsys.readouterr().out


def test_stale_reports_verified_specs_with_no_dependencies(working, capsys):
    conn = db.connect(working)
    conn.execute(
        "UPDATE spec SET status='verified', verified_by='jesus',"
        " verified_at='2026-01-01T00:00:00Z' WHERE id='concepts'"
    )
    db.save(conn, working)

    args = run(["stale"])
    assert args.handler(args) == 0
    out = capsys.readouterr().out
    assert "nothing has gone stale" in out
    assert "1 verified spec(s) have no dependencies and cannot be checked:" in out
    assert "concepts" in out
    assert 'Add one with: knowledge dep add <spec> "<glob>"' in out


def test_stale_without_demote_leaves_the_database_unchanged(working, capsys):
    conn = db.connect(working)
    config = load_config(working.root)
    base = lifecycle.head_commit(config.code_repo)
    lifecycle.mark_modeled(conn, working, "assets", by="writer", ontology_version="1.0.0")
    lifecycle.verify(conn, working, config, "assets", by="jesus", prune=[], commit=base)
    db.save(conn, working)

    page = config.code_repo / "app" / "platform" / "(menuLayout)" / "assets" / "page.tsx"
    page.write_text("changed\n")
    subprocess.run(["git", "-C", str(config.code_repo), "commit", "-am", "change"], check=True,
                   capture_output=True)

    args = run(["stale"])
    assert args.handler(args) == 0
    out = capsys.readouterr().out
    assert "assets: 1 dependency change(s)" in out
    assert "would be demoted (pass --demote to apply)" in out

    conn = db.connect(working)
    assert list(conn.execute("SELECT status, demoted_at FROM spec WHERE id='assets'")) == [
        ("verified", None)
    ]


def test_stale_reports_a_missing_base_commit_without_a_traceback(working, capsys):
    conn = db.connect(working)
    conn.execute(
        "UPDATE spec SET status='verified', verified_by='jesus',"
        " verified_at='2026-01-01T00:00:00Z', verified_against_commit='deadbeef'"
        " WHERE id='assets'"
    )
    db.save(conn, working)

    args = run(["stale"])
    assert args.handler(args) == 1
    out = capsys.readouterr().out
    assert "shallow clone" in out
    assert "fetch-depth" in out
    assert "Traceback" not in out
