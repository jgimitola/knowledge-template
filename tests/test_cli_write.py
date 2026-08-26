import pytest

from knowledge import cli, db, lifecycle, scan
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


def test_new_scaffolds_a_folder_and_appears_in_list(working, capsys):
    args = run(["new", "budgets", "--title", "Budgets"])
    assert args.handler(args) == 0
    capsys.readouterr()

    assert (working.specs / "budgets" / "spec.md").is_file()
    assert (working.specs / "budgets" / "spec.ttl").is_file()

    args = run(["list"])
    args.handler(args)
    assert "budgets" in capsys.readouterr().out

    conn = db.connect(working)
    assert list(conn.execute("SELECT status FROM spec WHERE id='budgets'")) == [("draft",)]


def test_ask_question_opens_and_shows_in_open_questions(working, capsys):
    args = run(["ask-question", "assets", "Can it be negative?", "--by", "writer"])
    assert args.handler(args) == 0
    assert "opened question #" in capsys.readouterr().out

    args = run(["questions", "--open"])
    args.handler(args)
    assert "Can it be negative?" in capsys.readouterr().out

    conn = db.connect(working)
    row = list(conn.execute(
        "SELECT spec_id, status, asked_by FROM open_question WHERE question='Can it be negative?'"
    ))
    assert row == [("assets", "open", "writer")]


def test_answer_closes_the_question(working, capsys):
    conn = db.connect(working)
    qid = lifecycle.open_question(conn, "assets", "Can it be negative?", asked_by="writer")
    db.save(conn, working)

    args = run(["answer", str(qid), "No, clamped at zero.", "--by", "jesus"])
    assert args.handler(args) == 0
    capsys.readouterr()

    conn = db.connect(working)
    row = list(conn.execute("SELECT status, answer FROM open_question WHERE id=?", (qid,)))
    assert row == [("answered", "No, clamped at zero.")]


def test_model_sets_modeled_at(working, capsys):
    args = run(["model", "assets", "--by", "writer"])
    assert args.handler(args) == 0
    assert "assets modeled by writer" in capsys.readouterr().out

    conn = db.connect(working)
    row = list(conn.execute(
        "SELECT modeled_by, ontology_version, modeled_at IS NOT NULL FROM spec WHERE id='assets'"
    ))
    assert row == [("writer", "1.0.0", 1)]


def test_verify_refuses_while_a_question_is_open_and_names_it(working, capsys):
    conn = db.connect(working)
    lifecycle.mark_modeled(conn, working, "assets", by="writer", ontology_version="1.0.0")
    qid = lifecycle.open_question(conn, "assets", "Can it be negative?", asked_by="writer")
    db.save(conn, working)

    args = run(["verify", "assets", "--by", "jesus"])
    assert args.handler(args) == 1
    out = capsys.readouterr().out
    assert "refused" in out
    assert f"#{qid}" in out

    conn = db.connect(working)
    assert list(conn.execute("SELECT status FROM spec WHERE id='assets'")) == [("draft",)]


def test_verify_succeeds_after_prune(working, monkeypatch, capsys):
    conn = db.connect(working)
    lifecycle.mark_modeled(conn, working, "assets", by="writer", ontology_version="1.0.0")
    qid = lifecycle.open_question(conn, "assets", "Unanswerable?", asked_by="writer")
    db.save(conn, working)

    monkeypatch.setattr(lifecycle, "head_commit", lambda code_repo: "cafefeed")

    args = run(["verify", "assets", "--by", "jesus", "--prune", str(qid), "no longer relevant"])
    assert args.handler(args) == 0
    assert "assets verified by jesus" in capsys.readouterr().out

    conn = db.connect(working)
    row = list(conn.execute(
        "SELECT status, verified_by, verified_against_commit FROM spec WHERE id='assets'"
    ))
    assert row == [("verified", "jesus", "cafefeed")]
    assert list(conn.execute("SELECT status FROM open_question WHERE id=?", (qid,))) == [
        ("dropped",)
    ]


def test_verify_prune_refuses_a_question_belonging_to_another_spec(working, capsys):
    conn = db.connect(working)
    lifecycle.mark_modeled(conn, working, "assets", by="writer", ontology_version="1.0.0")
    other_qid = lifecycle.open_question(conn, "concepts", "Unrelated?", asked_by="writer")
    db.save(conn, working)

    args = run(["verify", "assets", "--by", "jesus", "--prune", str(other_qid), "wrong spec"])
    assert args.handler(args) == 1
    out = capsys.readouterr().out
    assert "refused" in out
    assert "concepts" in out

    conn = db.connect(working)
    assert list(conn.execute("SELECT status FROM open_question WHERE id=?", (other_qid,))) == [
        ("open",)
    ]
    assert list(conn.execute("SELECT status FROM spec WHERE id='assets'")) == [("draft",)]


def test_verify_prune_with_nonnumeric_id_refuses_cleanly(working, capsys):
    conn = db.connect(working)
    lifecycle.mark_modeled(conn, working, "assets", by="writer", ontology_version="1.0.0")
    db.save(conn, working)

    args = run(["verify", "assets", "--by", "jesus", "--prune", "notanumber", "reason"])
    assert args.handler(args) == 1
    out = capsys.readouterr().out
    assert "refused" in out
    assert "numeric" in out

    conn = db.connect(working)
    assert list(conn.execute("SELECT status FROM spec WHERE id='assets'")) == [("draft",)]


def test_model_with_an_unknown_id_refuses_cleanly(working, capsys):
    args = run(["model", "nope", "--by", "writer"])
    assert args.handler(args) == 1
    out = capsys.readouterr().out
    assert "refused" in out
    assert "no spec with id" in out


def test_deleting_a_specs_folder_then_forget_recovers_the_repository(working, capsys):
    """`rm -rf specs/<id>` used to wedge the repo: `scan` would exit 1 forever with no CLI
    path to recovery. `forget` is that path."""
    for child in (working.specs / "concepts").iterdir():
        child.unlink()
    (working.specs / "concepts").rmdir()

    args = run(["scan"])
    assert args.handler(args) == 1
    capsys.readouterr()

    args = run(["forget", "concepts", "--by", "jesus"])
    assert args.handler(args) == 0
    assert "forgot concepts" in capsys.readouterr().out

    args = run(["scan"])
    assert args.handler(args) == 0
    capsys.readouterr()

    conn = db.connect(working)
    assert list(conn.execute("SELECT id FROM spec WHERE id='concepts'")) == []


def test_forget_refuses_cleanly_when_the_folder_still_exists(working, capsys):
    args = run(["forget", "assets", "--by", "jesus"])
    assert args.handler(args) == 1
    out = capsys.readouterr().out
    assert "refused" in out
    assert "specs/assets" in out

    conn = db.connect(working)
    assert list(conn.execute("SELECT id FROM spec WHERE id='assets'")) == [("assets",)]


def test_dep_add_with_an_unknown_spec_refuses_cleanly(working, capsys):
    args = run(["dep", "add", "nope", "app/**"])
    assert args.handler(args) == 1
    out = capsys.readouterr().out
    assert "refused" in out
    assert "no spec with id" in out

    conn = db.connect(working)
    assert list(conn.execute("SELECT * FROM spec_dependency WHERE spec_id='nope'")) == []


def test_ask_question_with_an_unknown_spec_refuses_cleanly(working, capsys):
    args = run(["ask-question", "nope", "Is this real?", "--by", "writer"])
    assert args.handler(args) == 1
    out = capsys.readouterr().out
    assert "refused" in out
    assert "no spec with id" in out

    conn = db.connect(working)
    assert list(conn.execute("SELECT * FROM open_question WHERE spec_id='nope'")) == []


def test_verify_with_no_code_repository_refuses_cleanly(working, capsys):
    """The day-one experience for anyone who clones this repo alone: knowledge.toml's
    code_repo does not exist yet, so `git rev-parse HEAD` fails inside it."""
    conn = db.connect(working)
    lifecycle.mark_modeled(conn, working, "assets", by="writer", ontology_version="1.0.0")
    db.save(conn, working)

    write_knowledge_toml(working.root, code_repo="does-not-exist")

    args = run(["verify", "assets", "--by", "jesus"])
    assert args.handler(args) == 1
    out, err = capsys.readouterr()
    assert "Traceback" not in out and "Traceback" not in err
    assert "code_repo" in out
    assert "knowledge.toml" in out
