import pytest

from knowledge import cli, db, lifecycle, scan


@pytest.fixture
def seeded(repo, monkeypatch):
    monkeypatch.chdir(repo.root)
    conn = db.connect(repo)
    scan.scan(conn, repo)
    conn.execute(
        "UPDATE spec SET status='verified', verified_by='jesus',"
        " verified_at='2026-01-01T00:00:00Z' WHERE id='concepts'"
    )
    conn.execute(
        "INSERT INTO open_question (spec_id, claim_iri, question, asked_by, asked_at, status)"
        " VALUES ('assets','https://example.test/id/Assets','Can an amount be negative?',"
        "'interviewer','2026-01-01T00:00:00Z','open')"
    )
    db.save(conn, repo)
    return repo


def run(argv):
    return cli.build_parser().parse_args(argv)


def test_list_shows_every_spec(seeded, capsys):
    args = run(["list"])
    assert args.handler(args) == 0
    out = capsys.readouterr().out
    assert "assets" in out and "concepts" in out


def test_list_filters_by_status(seeded, capsys):
    args = run(["list", "--status", "verified"])
    args.handler(args)
    out = capsys.readouterr().out
    assert "concepts" in out and "assets" not in out


def test_list_filters_to_specs_with_open_questions(seeded, capsys):
    args = run(["list", "--has-questions"])
    args.handler(args)
    out = capsys.readouterr().out
    assert "assets" in out and "concepts" not in out


def test_list_filters_to_unmodeled_specs(seeded, capsys):
    conn = db.connect(seeded)
    lifecycle.mark_modeled(conn, seeded, "concepts", by="writer", ontology_version="1.0.0")
    db.save(conn, seeded)

    args = run(["list", "--unmodeled"])
    args.handler(args)
    out = capsys.readouterr().out
    assert "assets" in out and "concepts" not in out


def test_list_unmodeled_catches_content_drift_after_modeling(seeded, capsys):
    conn = db.connect(seeded)
    lifecycle.mark_modeled(conn, seeded, "concepts", by="writer", ontology_version="1.0.0")
    db.save(conn, seeded)

    md = seeded.specs / "concepts" / "spec.md"
    md.write_text(md.read_text(encoding="utf-8") + "\nEdited after modeling.\n",
                  encoding="utf-8")
    scan.scan(conn, seeded)

    args = run(["list", "--unmodeled"])
    args.handler(args)
    assert "concepts" in capsys.readouterr().out


def test_list_unmodeled_catches_an_outdated_ontology_version(seeded, capsys):
    conn = db.connect(seeded)
    lifecycle.mark_modeled(conn, seeded, "concepts", by="writer", ontology_version="0.0.1")
    db.save(conn, seeded)

    args = run(["list", "--unmodeled"])
    args.handler(args)
    assert "concepts" in capsys.readouterr().out


def test_list_unmodeled_catches_a_row_with_no_recorded_audit_hash(seeded, capsys):
    """modeled_at set but modeled_md_hash/modeled_ttl_hash NULL: a row written before the
    frozen-hash columns existed, or replayed from a pre-Task-1 dump. `modeled_at IS NULL`
    does not fire (it is set) and neither does the drift comparison (SQL NULL != anything is
    NULL, not true) — the worklist must catch this with an explicit NULL check instead."""
    conn = db.connect(seeded)
    conn.execute(
        "UPDATE spec SET modeled_at='2026-01-01T00:00:00Z', modeled_by='writer',"
        " ontology_version='1.0.0' WHERE id='assets'"
    )
    db.save(conn, seeded)

    args = run(["list", "--unmodeled"])
    args.handler(args)
    assert "assets" in capsys.readouterr().out


def test_show_prints_the_row_and_its_questions(seeded, capsys):
    args = run(["show", "assets"])
    assert args.handler(args) == 0
    out = capsys.readouterr().out
    assert "draft" in out
    assert "Can an amount be negative?" in out


def test_show_reports_an_unknown_id(seeded, capsys):
    args = run(["show", "nope"])
    assert args.handler(args) == 1
    assert "nope" in capsys.readouterr().out


def test_questions_lists_open_ones(seeded, capsys):
    args = run(["questions", "--open"])
    args.handler(args)
    assert "Can an amount be negative?" in capsys.readouterr().out


def test_validate_passes_on_a_clean_graph(seeded, capsys):
    args = run(["validate", "--strict"])
    assert args.handler(args) == 0
    assert "no dangling references" in capsys.readouterr().out


def test_graph_writes_a_turtle_file(seeded, tmp_path, capsys):
    out = tmp_path / "g.ttl"
    args = run(["graph", "-o", str(out)])
    assert args.handler(args) == 0
    assert "@prefix ex:" in out.read_text(encoding="utf-8")
    assert b"\r" not in out.read_bytes()


def test_graph_defaults_to_verified_specs_only(seeded, tmp_path):
    out = tmp_path / "verified.ttl"
    args = run(["graph", "-o", str(out)])
    args.handler(args)
    text = out.read_text(encoding="utf-8")
    assert "Workspace" in text
    assert "/platform/assets" not in text

    both = tmp_path / "all.ttl"
    args = run(["graph", "--include-drafts", "-o", str(both)])
    args.handler(args)
    assert "/platform/assets" in both.read_text(encoding="utf-8")


def test_contradictions_reports_none_on_a_clean_graph(seeded, capsys):
    args = run(["contradictions", "--include-drafts"])
    assert args.handler(args) == 0
    assert "no mechanical contradictions found" in capsys.readouterr().out


def test_contradictions_summary_accounts_for_skipped_checks(seeded, capsys):
    """With every configurable check unconfigured, only dangling_terms actually ran. The
    summary must not read as a verdict on the checks that were skipped."""
    toml_path = seeded.root / "knowledge.toml"
    text = toml_path.read_text(encoding="utf-8")
    text = text.replace('concept_class = "Concept"\nconcept_spec = "concepts"\n', "")
    text = text.replace(
        'functional_properties = ["route", "editable", "required", "viewport", "defaultsTo"]\n',
        "",
    )
    toml_path.write_text(text, encoding="utf-8")

    args = run(["contradictions", "--include-drafts"])
    assert args.handler(args) == 0
    out = capsys.readouterr().out
    assert "no mechanical contradictions found" not in out
    assert "2 skipped" in out


def test_contradictions_reports_a_functional_conflict(seeded, write_spec, capsys):
    write_spec(seeded.root, "duplicate-route",
               'app:Assets a ex:View ; ex:route "/somewhere-else" .\n')
    args = run(["contradictions", "--include-drafts"])
    args.handler(args)
    assert "route" in capsys.readouterr().out


def test_stale_without_a_configured_code_repo_fails_clearly(repo, capsys, monkeypatch):
    from knowledge import cli
    (repo.root / "knowledge.toml").write_text(
        (repo.root / "knowledge.toml").read_text(encoding="utf-8").replace(
            'code_repo = "../code"', 'code_repo = ""'
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(repo.root)
    assert cli.main_argv(["stale"]) == 1
    assert "no code repository configured" in capsys.readouterr().err


def test_the_parser_description_names_no_project(capsys):
    from knowledge import cli
    text = cli.build_parser().format_help()
    assert "monicords" not in text.lower()
    # A description that only avoids the string "monicords" would still pass for any other
    # project's name substituted in — pin the exact generic text so this test can actually
    # fail for the reason it exists.
    assert "Author, track and publish a knowledge base." in text
