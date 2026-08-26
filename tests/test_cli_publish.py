import pytest

from knowledge import cli, db, scan
from tests.conftest import write_knowledge_toml


@pytest.fixture
def working(repo, monkeypatch):
    monkeypatch.chdir(repo.root)
    conn = db.connect(repo)
    scan.scan(conn, repo)
    db.save(conn, repo)
    return repo


def run(argv):
    return cli.build_parser().parse_args(argv)


def test_publish_reports_a_clone_failure_cleanly_instead_of_a_traceback(working, capsys):
    """The wiki remote does not exist (a plain nonexistent local path stands in for an
    unreachable or not-yet-created GitHub wiki, so this stays offline and deterministic).
    cmd_publish must catch CalledProcessError itself rather than let it escape as a
    traceback — main() only catches RuntimeError."""
    bogus_remote = working.root / "no-such-wiki"
    write_knowledge_toml(working.root, remote=bogus_remote.as_posix())

    args = run(["publish"])
    exit_code = args.handler(args)

    assert exit_code == 1
    out = capsys.readouterr().out
    assert "error:" in out
    assert "could not clone" in out
    assert "web UI" in out  # the uninitialised-wiki hint


def test_dry_run_removes_a_stale_page_before_writing(working, tmp_path, capsys):
    out = tmp_path / "wiki-out"
    out.mkdir()
    (out / "Old-Name.md").write_text("stale content\n", encoding="utf-8")

    args = run(["publish", "--dry-run", "-o", str(out)])
    exit_code = args.handler(args)

    assert exit_code == 0
    assert not (out / "Old-Name.md").exists()
    printed = capsys.readouterr().out
    assert "stale page(s) removed: Old-Name.md" in printed


def test_dry_run_default_output_resolves_against_the_repo_root(working, monkeypatch, capsys):
    nested = working.root / "specs" / "assets"
    monkeypatch.chdir(nested)

    args = run(["publish", "--dry-run"])
    exit_code = args.handler(args)

    assert exit_code == 0
    assert (working.root / "build" / "wiki" / "Assets.md").is_file()
    assert not (nested / "build").exists()


def test_publish_follows_a_renamed_folder_by_the_path_column(working, tmp_path, capsys):
    """The same bug `scan` was fixed for: `publish.render_page` took an id from the
    database and reconstructed `specs/<id>` instead of resolving via the row's current
    `path`, so a renamed folder crashed the publish with FileNotFoundError."""
    conn = db.connect(working)
    conn.execute("UPDATE spec SET status='verified', verified_by='jesus' WHERE id='assets'")
    db.save(conn, working)

    (working.specs / "assets").rename(working.specs / "assets-renamed")
    args = run(["scan"])
    args.handler(args)
    capsys.readouterr()

    out = tmp_path / "wiki-out"
    args = run(["publish", "--dry-run", "-o", str(out)])
    assert args.handler(args) == 0
    assert (out / "Assets.md").is_file()


def test_publish_skips_a_spec_whose_folder_is_gone_instead_of_crashing(working, tmp_path, capsys):
    for child in (working.specs / "concepts").iterdir():
        child.unlink()
    (working.specs / "concepts").rmdir()

    out = tmp_path / "wiki-out"
    args = run(["publish", "--dry-run", "-o", str(out)])
    assert args.handler(args) == 0
    printed = capsys.readouterr().out
    assert "concepts" in printed
    assert "knowledge forget" in printed
    assert not (out / "Concepts.md").exists()
    assert (out / "Assets.md").is_file()
