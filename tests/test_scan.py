from knowledge import db, lifecycle, scan
from knowledge import paths as paths_mod


def test_scan_adds_a_row_per_spec_folder(repo):
    conn = db.connect(repo)
    report = scan.scan(conn, repo)
    assert sorted(report.added) == ["assets", "concepts"]
    rows = list(conn.execute("SELECT id, status, wiki_page FROM spec ORDER BY id"))
    assert rows == [
        ("assets", "draft", "Assets"),
        ("concepts", "draft", "Concepts"),
    ]


def test_scan_is_idempotent(repo):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    report = scan.scan(conn, repo)
    assert report.added == []
    assert sorted(report.unchanged) == ["assets", "concepts"]


def test_scan_follows_a_renamed_folder_by_its_id(repo):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    conn.execute("UPDATE spec SET status='verified', verified_by='jesus' WHERE id='assets'")

    (repo.specs / "assets").rename(repo.specs / "assets-renamed")
    report = scan.scan(conn, repo)

    assert report.moved == [("assets", "specs/assets", "specs/assets-renamed")]
    row = list(conn.execute("SELECT path, status, verified_by FROM spec WHERE id='assets'"))
    assert row == [("specs/assets-renamed", "verified", "jesus")]


def test_a_rename_preserves_the_ttl_hash_and_the_resources(repo):
    """The one operation the id design exists to survive must not corrupt anything."""
    resources = repo.specs / "assets" / "resources"
    resources.mkdir()
    (resources / "rates.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    conn = db.connect(repo)
    scan.scan(conn, repo)
    before = list(conn.execute("SELECT ttl_hash FROM spec WHERE id='assets'"))[0][0]
    assert before is not None

    (repo.specs / "assets").rename(repo.specs / "assets-renamed")
    scan.scan(conn, repo)

    after = list(conn.execute("SELECT ttl_hash FROM spec WHERE id='assets'"))[0][0]
    assert after == before
    rows = list(conn.execute("SELECT path FROM spec_resource WHERE spec_id='assets'"))
    assert rows == [("resources/rates.csv",)]
    conn.close()


def test_a_hand_set_note_on_a_resource_survives_a_rescan(repo):
    resources = repo.specs / "assets" / "resources"
    resources.mkdir()
    (resources / "rates.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    conn = db.connect(repo)
    scan.scan(conn, repo)
    conn.execute(
        "UPDATE spec_resource SET note = 'from the 2026 filing' WHERE spec_id = 'assets'"
    )
    scan.scan(conn, repo)
    note = list(conn.execute("SELECT note FROM spec_resource WHERE spec_id='assets'"))[0][0]
    assert note == "from the 2026 filing"
    conn.close()


def test_scan_reports_a_row_whose_files_are_gone(repo):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    for child in (repo.specs / "concepts").iterdir():
        child.unlink()
    (repo.specs / "concepts").rmdir()
    report = scan.scan(conn, repo)
    assert report.missing == ["concepts"]
    row = list(conn.execute("SELECT id FROM spec WHERE id='concepts'"))
    assert row == [("concepts",)]


def test_scan_records_hashes_and_notices_a_prose_edit(repo):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    before = list(conn.execute("SELECT md_hash FROM spec WHERE id='assets'"))[0][0]

    md = repo.specs / "assets" / "spec.md"
    md.write_text(md.read_text(encoding="utf-8") + "\nA new sentence.\n", encoding="utf-8")
    scan.scan(conn, repo)

    after = list(conn.execute("SELECT md_hash FROM spec WHERE id='assets'"))[0][0]
    assert before != after


def test_scan_enumerates_resources(repo):
    resources = repo.specs / "assets" / "resources"
    resources.mkdir()
    (resources / "rates.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    conn = db.connect(repo)
    scan.scan(conn, repo)
    rows = list(conn.execute("SELECT spec_id, path, kind FROM spec_resource"))
    assert rows == [("assets", "resources/rates.csv", "data")]


def test_title_comes_from_the_first_heading(repo):
    md = repo.specs / "assets" / "spec.md"
    md.write_text("---\nid: assets\n---\n\n# Assets\n\nProse.\n", encoding="utf-8")
    conn = db.connect(repo)
    scan.scan(conn, repo)
    assert list(conn.execute("SELECT title FROM spec WHERE id='assets'"))[0][0] == "Assets"


def test_scan_returns_an_empty_report_when_there_are_no_specs(tmp_path):
    (tmp_path / "knowledge.toml").write_text(
        '[repo]\ncode_repo = "../code"\n\n[wiki]\nremote = "x"\n', encoding="utf-8"
    )
    (tmp_path / ".metadata").mkdir()
    empty = paths_mod.get_paths(tmp_path)
    conn = db.connect(empty)
    report = scan.scan(conn, empty)
    assert report.added == [] and report.missing == []


def test_a_scan_that_changes_nothing_does_not_touch_the_dump(repo):
    """CI asserts the dump is unchanged by a scan. A scan that always rewrites it makes
    that gate permanently red, and a gate nobody can pass is one nobody reads."""
    conn = db.connect(repo)
    scan.scan(conn, repo)
    first = repo.dump.read_bytes()
    scan.scan(conn, repo)
    assert repo.dump.read_bytes() == first
    conn.close()


def test_a_real_edit_still_updates_the_row(repo):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    before = list(conn.execute("SELECT updated_at, md_hash FROM spec WHERE id='assets'"))[0]

    md = repo.specs / "assets" / "spec.md"
    md.write_text(md.read_text(encoding="utf-8") + "\nAnother sentence.\n", encoding="utf-8")
    scan.scan(conn, repo)

    after = list(conn.execute("SELECT updated_at, md_hash FROM spec WHERE id='assets'"))[0]
    assert after[1] != before[1]        # the hash moved
    conn.close()


def test_scan_demotes_a_verified_spec_whose_content_drifted_past_its_audit(repo):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
    conn.execute(
        "UPDATE spec SET status='verified', verified_by='jesus' WHERE id='assets'"
    )

    md = repo.specs / "assets" / "spec.md"
    md.write_text(md.read_text(encoding="utf-8") + "\nEdited after verification.\n",
                  encoding="utf-8")
    report = scan.scan(conn, repo)

    assert report.demoted == ["assets"]
    row = list(conn.execute(
        "SELECT status, demoted_reason, modeled_at IS NOT NULL FROM spec WHERE id='assets'"
    ))[0]
    assert row[0] == "draft"
    assert "content changed" in row[1]
    assert row[2] == 1  # demotion invalidates verification, not the writer's audit


def test_scan_does_not_demote_a_verified_spec_that_was_never_modeled(repo):
    """A spec verified before this feature shipped has no frozen hash to compare against —
    treat it as unknown, not as drifted. (This is exactly the state of the 21 specs Spec A
    produced, until Task 10's migration pass models each one.)"""
    conn = db.connect(repo)
    scan.scan(conn, repo)
    conn.execute("UPDATE spec SET status='verified', verified_by='jesus' WHERE id='assets'")

    report = scan.scan(conn, repo)

    assert report.demoted == []
    assert list(conn.execute("SELECT status FROM spec WHERE id='assets'"))[0][0] == "verified"


def test_scan_leaves_a_verified_spec_alone_when_content_is_unchanged(repo):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
    conn.execute("UPDATE spec SET status='verified', verified_by='jesus' WHERE id='assets'")

    report = scan.scan(conn, repo)

    assert report.demoted == []
    assert list(conn.execute("SELECT status FROM spec WHERE id='assets'"))[0][0] == "verified"
