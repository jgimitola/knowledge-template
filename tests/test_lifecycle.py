import pytest

from knowledge import db, lifecycle, scan
from tests.conftest import make_config


@pytest.fixture
def seeded(repo):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    return repo, conn


@pytest.fixture
def config(tmp_path):
    return make_config(tmp_path / "code")


def test_verify_refuses_an_unmodeled_spec(seeded, config):
    repo, conn = seeded
    with pytest.raises(RuntimeError, match="not been modeled"):
        lifecycle.verify(conn, repo, config, "assets", by="jesus", prune=[], commit="abc123")


def test_verify_refuses_while_a_question_is_open(seeded, config):
    repo, conn = seeded
    lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
    lifecycle.open_question(conn, "assets", "Can it be negative?", asked_by="writer")
    with pytest.raises(RuntimeError, match="open question"):
        lifecycle.verify(conn, repo, config, "assets", by="jesus", prune=[], commit="abc123")


def test_verify_succeeds_once_the_question_is_answered(seeded, config):
    repo, conn = seeded
    lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
    qid = lifecycle.open_question(conn, "assets", "Can it be negative?", asked_by="writer")
    lifecycle.answer_question(conn, qid, "No, it is clamped at zero.", actor="jesus")
    lifecycle.verify(conn, repo, config, "assets", by="jesus", prune=[], commit="abc123")

    row = list(conn.execute(
        "SELECT status, verified_by, verified_against_commit FROM spec WHERE id='assets'"
    ))
    assert row == [("verified", "jesus", "abc123")]


def test_verify_can_prune_a_question_deliberately(seeded, config):
    repo, conn = seeded
    lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
    qid = lifecycle.open_question(conn, "assets", "Unanswerable?", asked_by="writer")
    lifecycle.verify(conn, repo, config, "assets", by="jesus",
                     prune=[(qid, "no longer relevant")], commit="abc123")

    assert list(conn.execute("SELECT status FROM open_question WHERE id=?", (qid,))) == [("dropped",)]
    events = [r[0] for r in conn.execute(
        "SELECT event FROM spec_event WHERE spec_id='assets' ORDER BY id"
    )]
    assert "question_dropped" in events and "verified" in events


def test_demote_returns_a_verified_spec_to_draft(seeded, config):
    repo, conn = seeded
    lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
    lifecycle.verify(conn, repo, config, "assets", by="jesus", prune=[], commit="abc123")
    lifecycle.demote(conn, "assets", "app/x/page.tsx changed", actor="stale-check")

    row = list(conn.execute(
        "SELECT status, demoted_reason, modeled_at IS NOT NULL FROM spec WHERE id='assets'"
    ))
    assert row[0][0] == "draft"
    assert "app/x/page.tsx" in row[0][1]
    # Demotion invalidates human confirmation, not the writer's audit.
    assert row[0][2] == 1


def test_reverify_after_demotion_clears_the_demotion(seeded, config):
    repo, conn = seeded
    lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
    lifecycle.verify(conn, repo, config, "assets", by="jesus", prune=[], commit="abc123")
    lifecycle.demote(conn, "assets", "app/x/page.tsx changed", actor="stale-check")
    lifecycle.verify(conn, repo, config, "assets", by="jesus", prune=[], commit="def456")

    row = list(conn.execute(
        "SELECT status, demoted_at, demoted_reason FROM spec WHERE id='assets'"
    ))
    assert row == [("verified", None, None)]


def test_new_spec_scaffolds_a_folder_with_frontmatter(repo):
    path = lifecycle.new_spec(repo, "budgets", "Budgets")
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\nid: budgets\n---\n")
    assert "# Budgets" in text
    assert (repo.specs / "budgets" / "spec.ttl").is_file()


def test_new_spec_refuses_to_overwrite(repo):
    lifecycle.new_spec(repo, "budgets", "Budgets")
    with pytest.raises(RuntimeError, match="already exists"):
        lifecycle.new_spec(repo, "budgets", "Budgets")


def test_new_spec_writes_lf_line_endings_on_every_platform(repo):
    """A scaffolded spec is a tracked source file; .gitattributes normalises a committed
    CRLF blob to LF, which would make scan's hash and CI's hash disagree on Windows."""
    path = lifecycle.new_spec(repo, "budgets", "Budgets")
    assert b"\r" not in path.read_bytes()
    assert b"\r" not in (repo.specs / "budgets" / "spec.ttl").read_bytes()


def test_model_raises_on_an_unknown_id(seeded):
    repo, conn = seeded
    with pytest.raises(RuntimeError, match="no spec with id 'nope'"):
        lifecycle.mark_modeled(conn, repo, "nope", by="writer", ontology_version="1.0.0")
    # Nothing was written: no orphan spec_event for an id that was never accepted.
    assert list(conn.execute("SELECT * FROM spec_event WHERE spec_id='nope'")) == []


def test_model_follows_a_renamed_folder_by_the_path_column(seeded):
    """The same bug `scan` was fixed for: `mark_modeled` took an id from the database and
    reconstructed `specs/<id>` instead of resolving via the row's current `path`."""
    repo, conn = seeded
    (repo.specs / "assets").rename(repo.specs / "assets-renamed")
    scan.scan(conn, repo)

    lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
    row = list(conn.execute(
        "SELECT modeled_by, ttl_hash IS NOT NULL, md_hash IS NOT NULL FROM spec WHERE id='assets'"
    ))
    assert row == [("writer", 1, 1)]


def test_forget_removes_the_row_but_keeps_the_event_history(seeded):
    repo, conn = seeded
    for child in (repo.specs / "concepts").iterdir():
        child.unlink()
    (repo.specs / "concepts").rmdir()
    scan.scan(conn, repo)  # records the row as present but missing

    lifecycle.forget(conn, repo, "concepts", by="jesus")

    assert list(conn.execute("SELECT id FROM spec WHERE id='concepts'")) == []
    events = [r[0] for r in conn.execute(
        "SELECT event FROM spec_event WHERE spec_id='concepts' ORDER BY id"
    )]
    assert events[-1] == "forgotten"


def test_forget_cascades_dependencies_resources_and_questions(seeded):
    repo, conn = seeded
    conn.execute("INSERT INTO spec_dependency (spec_id, glob) VALUES ('concepts','app/**')")
    lifecycle.open_question(conn, "concepts", "Any open question?", asked_by="writer")
    for child in (repo.specs / "concepts").iterdir():
        child.unlink()
    (repo.specs / "concepts").rmdir()
    scan.scan(conn, repo)

    lifecycle.forget(conn, repo, "concepts", by="jesus")

    assert list(conn.execute("SELECT * FROM spec_dependency WHERE spec_id='concepts'")) == []
    assert list(conn.execute("SELECT * FROM open_question WHERE spec_id='concepts'")) == []


def test_forget_refuses_when_the_folder_still_exists(seeded):
    repo, conn = seeded
    with pytest.raises(RuntimeError, match="specs/concepts still exists"):
        lifecycle.forget(conn, repo, "concepts", by="jesus")
    assert list(conn.execute("SELECT id FROM spec WHERE id='concepts'")) == [("concepts",)]


def test_forget_refuses_an_unknown_id(seeded):
    repo, conn = seeded
    with pytest.raises(RuntimeError, match="no spec with id 'nope'"):
        lifecycle.forget(conn, repo, "nope", by="jesus")


def test_forget_refuses_after_a_rename_naming_the_renamed_folder(seeded):
    """Regression: the guard used to resolve `specs/<id>` from the id directly, so once
    `assets` was renamed to `assets-v2` the guard checked a folder that no longer existed
    and let a spec whose files were still on disk be forgotten — destroying the
    verification history the guard exists to protect."""
    repo, conn = seeded
    (repo.specs / "assets").rename(repo.specs / "assets-v2")
    scan.scan(conn, repo)

    with pytest.raises(RuntimeError, match="specs/assets-v2 still exists"):
        lifecycle.forget(conn, repo, "assets", by="jesus")
    assert list(conn.execute("SELECT id FROM spec WHERE id='assets'")) == [("assets",)]

    for child in (repo.specs / "assets-v2").iterdir():
        child.unlink()
    (repo.specs / "assets-v2").rmdir()
    scan.scan(conn, repo)

    lifecycle.forget(conn, repo, "assets", by="jesus")
    assert list(conn.execute("SELECT id FROM spec WHERE id='assets'")) == []


def test_verify_refuses_content_edited_after_it_was_modeled(seeded, config):
    repo, conn = seeded
    lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
    md = repo.specs / "assets" / "spec.md"
    md.write_text(md.read_text(encoding="utf-8") + "\nA post-model edit.\n", encoding="utf-8")
    scan.scan(conn, repo)

    with pytest.raises(RuntimeError, match="changed since it was last modeled"):
        lifecycle.verify(conn, repo, config, "assets", by="jesus", prune=[], commit="abc123")


def test_verify_reports_a_never_recorded_audit_hash_accurately(seeded, config):
    """A row with modeled_at set but NULL frozen hashes predates the modeled_* columns (or
    was replayed from a pre-Task-1 dump). Nothing about its content changed — the audited
    hash was simply never recorded — so verify must not claim it "has changed since it was
    last modeled"; that would be false. Python `!=` against None is always True, so the old
    drift comparison alone would produce exactly that false claim."""
    repo, conn = seeded
    conn.execute(
        "UPDATE spec SET modeled_at=?, modeled_by='writer', ontology_version='1.0.0'"
        " WHERE id='assets'",
        (db.now(),),
    )
    with pytest.raises(RuntimeError, match="never had its audited hash recorded"):
        lifecycle.verify(conn, repo, config, "assets", by="jesus", prune=[], commit="abc123")


def test_model_freezes_the_audited_hash_separately_from_the_live_one(seeded):
    repo, conn = seeded
    lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
    row = list(conn.execute(
        "SELECT md_hash, ttl_hash, modeled_md_hash, modeled_ttl_hash"
        " FROM spec WHERE id='assets'"
    ))[0]
    md_hash, ttl_hash, modeled_md_hash, modeled_ttl_hash = row
    assert md_hash == modeled_md_hash
    assert ttl_hash == modeled_ttl_hash
    assert md_hash is not None and ttl_hash is not None
