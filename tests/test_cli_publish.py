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


def test_publish_target_none_fails_with_a_readable_message_instead_of_a_traceback(
    working, capsys
):
    """'none' is the shipped default — a template cannot know where its user publishes, and
    guessing a destination is worse than requiring one. This must be a clean, actionable
    error, not an attempt to clone an empty remote."""
    write_knowledge_toml(working.root, target="none")

    args = run(["publish"])
    exit_code = args.handler(args)

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "publish.target" in err
    assert "directory" in err
    assert "github-wiki" in err


def test_publish_directory_target_writes_pages_without_pushing(working, tmp_path, capsys):
    out = tmp_path / "docs-out"
    write_knowledge_toml(working.root, target="directory", out_dir=out.as_posix())

    args = run(["publish"])
    exit_code = args.handler(args)

    assert exit_code == 0
    assert (out / "Assets.md").is_file()
    printed = capsys.readouterr().out
    assert "page(s) written to" in printed
    assert out.name in printed


def test_publish_directory_target_out_dir_flag_overrides_the_config(working, tmp_path, capsys):
    configured = tmp_path / "cfg-out"
    write_knowledge_toml(working.root, target="directory", out_dir=configured.as_posix())
    cli_out = tmp_path / "cli-out"

    args = run(["publish", "--out-dir", str(cli_out)])
    exit_code = args.handler(args)

    assert exit_code == 0
    assert (cli_out / "Assets.md").is_file()
    assert not configured.exists()


def test_publish_directory_target_without_an_out_dir_fails_cleanly(working, capsys):
    """Regression guard for a `Path("")` trap: `Path("")` normalises to `Path(".")`, whose
    `str()` is `"."` — truthy — so checking emptiness *after* wrapping in `Path` can never
    catch a missing out_dir. The check has to happen on the raw string first."""
    write_knowledge_toml(working.root, target="directory")

    args = run(["publish"])
    exit_code = args.handler(args)

    assert exit_code == 1
    err = capsys.readouterr().err
    assert "publish.out_dir is required" in err


def test_dry_run_succeeds_when_publish_target_is_none(working, tmp_path, capsys):
    """--dry-run is a preview, not a mode of publishing — a fresh template user with nothing
    configured yet must still be able to see what would be published."""
    write_knowledge_toml(working.root, target="none")
    out = tmp_path / "preview"

    args = run(["publish", "--dry-run", "-o", str(out)])
    exit_code = args.handler(args)

    assert exit_code == 0
    assert (out / "Assets.md").is_file()


def test_dry_run_takes_the_dry_run_path_even_under_a_directory_target(working, tmp_path, capsys):
    """A directory-target publish never lists individual pages; the dry-run path always does
    (see test_dry_run_removes_a_stale_page_before_writing). That listing is the distinguishing
    signal that --dry-run was honoured rather than silently ignored in favour of a real
    directory write — which would skip -o's target entirely and write to the configured
    out_dir instead."""
    configured = tmp_path / "cfg-out"
    write_knowledge_toml(working.root, target="directory", out_dir=configured.as_posix())
    preview = tmp_path / "preview-out"

    args = run(["publish", "--dry-run", "-o", str(preview)])
    exit_code = args.handler(args)

    assert exit_code == 0
    assert (preview / "Assets.md").is_file()
    assert not configured.exists()
    printed = capsys.readouterr().out
    assert "    Assets.md" in printed  # the dry-run path's per-page listing


def test_publish_directory_target_removes_a_page_whose_spec_is_gone(working, tmp_path, capsys):
    out = tmp_path / "docs-out"
    out.mkdir()
    (out / "Old-Name.md").write_text("stale content\n", encoding="utf-8")
    write_knowledge_toml(working.root, target="directory", out_dir=out.as_posix())

    args = run(["publish"])
    exit_code = args.handler(args)

    assert exit_code == 0
    assert not (out / "Old-Name.md").exists()
    printed = capsys.readouterr().out
    assert "stale page(s) removed: Old-Name.md" in printed
