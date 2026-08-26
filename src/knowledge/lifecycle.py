"""Status transitions. Two statuses only: draft and verified.

Verification is a human act, so `verify` takes a name and refuses shortcuts: a spec whose
graph nobody has audited cannot be verified, because confirming prose while the graph says
something else is how the graph quietly becomes wrong. An open question blocks verification
too — pruning one is possible but deliberate, and lands in the event log.
"""

from __future__ import annotations

from pathlib import Path

from knowledge import db, gitcmd
from knowledge.config import Config
from knowledge.paths import Paths, spec_dir, spec_md, spec_ttl

SPEC_TEMPLATE = """\
---
id: {spec_id}
---

# {title}

Prose first, Turtle second. Describe what the product does today, and say *why* wherever a
rule exists — the reason is the part the code does not record.
"""


def head_commit(code_repo: Path) -> str:
    result = gitcmd.run(
        ["-C", str(code_repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def new_spec(paths: Paths, spec_id: str, title: str) -> Path:
    directory = spec_dir(paths, spec_id)
    if directory.exists():
        raise RuntimeError(f"specs/{spec_id} already exists")
    directory.mkdir(parents=True)
    md = spec_md(paths, spec_id)
    md.write_text(
        SPEC_TEMPLATE.format(spec_id=spec_id, title=title), encoding="utf-8", newline="\n"
    )
    spec_ttl(paths, spec_id).write_text(f"# {spec_id}\n", encoding="utf-8", newline="\n")
    return md


def open_question(conn, spec_id: str, question: str, asked_by: str,
                  claim_iri: str | None = None) -> int:
    cursor = conn.execute(
        "INSERT INTO open_question (spec_id, claim_iri, question, asked_by, asked_at, status)"
        " VALUES (?,?,?,?,?,'open')",
        (spec_id, claim_iri, question, asked_by, db.now()),
    )
    db.record_event(conn, spec_id, "question_opened", asked_by, question)
    return int(cursor.lastrowid)


def _spec_of(conn, question_id: int) -> str:
    rows = list(conn.execute("SELECT spec_id FROM open_question WHERE id = ?", (question_id,)))
    if not rows:
        raise RuntimeError(f"no question #{question_id}")
    return rows[0][0]


def answer_question(conn, question_id: int, answer: str, actor: str) -> None:
    spec_id = _spec_of(conn, question_id)
    conn.execute(
        "UPDATE open_question SET status='answered', answer=?, answered_at=? WHERE id=?",
        (answer, db.now(), question_id),
    )
    db.record_event(conn, spec_id, "question_answered", actor, answer)


def prune_question(conn, question_id: int, reason: str, actor: str) -> None:
    spec_id = _spec_of(conn, question_id)
    conn.execute(
        "UPDATE open_question SET status='dropped', answer=?, answered_at=? WHERE id=?",
        (reason, db.now(), question_id),
    )
    db.record_event(conn, spec_id, "question_dropped", actor, reason)


def _spec_directory(conn, paths: Paths, spec_id: str) -> Path:
    """Resolve a spec's folder from its `path` column, kept current by `scan`, rather than
    reconstructing `paths.specs / spec_id`. The id and the folder name are only guaranteed
    to match at creation time — a rename keeps the id but changes the folder — and this id
    comes straight from the database, which is exactly when the two can differ. (The other
    caller with the same shape is `publish._spec_directory`; `graph.py` is not affected
    because it iterates folder names directly.)"""
    rows = list(conn.execute("SELECT path FROM spec WHERE id = ?", (spec_id,)))
    if not rows:
        raise RuntimeError(f"no spec with id {spec_id!r}")
    return paths.root / rows[0][0]


def mark_modeled(conn, paths: Paths, spec_id: str, by: str, ontology_version: str) -> None:
    from knowledge.scan import file_hash

    directory = _spec_directory(conn, paths, spec_id)
    md_hash = file_hash(directory / "spec.md")
    ttl_hash = file_hash(directory / "spec.ttl")
    conn.execute(
        "UPDATE spec SET modeled_at=?, modeled_by=?, ontology_version=?, ttl_hash=?,"
        " md_hash=?, modeled_ttl_hash=?, modeled_md_hash=?, updated_at=? WHERE id=?",
        (db.now(), by, ontology_version, ttl_hash, md_hash, ttl_hash, md_hash,
         db.now(), spec_id),
    )
    db.record_event(conn, spec_id, "modeled", by, f"ontology {ontology_version}")


def verify(conn, paths: Paths, config: Config, spec_id: str, by: str,
           prune: list[tuple[int, str]], commit: str | None = None) -> None:
    rows = list(conn.execute(
        "SELECT modeled_at, md_hash, ttl_hash, modeled_md_hash, modeled_ttl_hash"
        " FROM spec WHERE id = ?", (spec_id,)
    ))
    if not rows:
        raise RuntimeError(f"no spec with id {spec_id!r}")
    modeled_at, md_hash, ttl_hash, modeled_md_hash, modeled_ttl_hash = rows[0]
    if modeled_at is None:
        raise RuntimeError(
            f"{spec_id} has not been modeled — run the writer agent, then `knowledge model`"
        )
    if modeled_md_hash is None or modeled_ttl_hash is None:
        # modeled_at is set but no frozen hash was ever recorded — a row written before
        # modeled_md_hash/modeled_ttl_hash existed, or replayed from a pre-Task-1 dump.
        # Python `!=` against None is always True, so the drift comparison below would
        # "catch" this too, but with a false message: nothing changed, the hash was simply
        # never taken. Refuse with the truthful reason instead of falling through — verify
        # confirms a spec whose audit state is known, and this one's is not.
        raise RuntimeError(
            f"{spec_id} has never had its audited hash recorded — run `knowledge model` "
            "before verifying"
        )
    if md_hash != modeled_md_hash or ttl_hash != modeled_ttl_hash:
        raise RuntimeError(
            f"{spec_id} has changed since it was last modeled — run the writer agent again, "
            "then `knowledge model`, before verifying"
        )

    for question_id, reason in prune:
        owner = _spec_of(conn, question_id)
        if owner != spec_id:
            raise RuntimeError(
                f"question #{question_id} belongs to {owner!r}, not {spec_id!r} — "
                "prune it while verifying that spec instead"
            )
        prune_question(conn, question_id, reason, by)

    still_open = [
        row[0] for row in conn.execute(
            "SELECT id FROM open_question WHERE spec_id = ? AND status = 'open'", (spec_id,)
        )
    ]
    if still_open:
        listed = ", ".join(f"#{qid}" for qid in still_open)
        raise RuntimeError(
            f"{spec_id} has {len(still_open)} open question(s): {listed}. "
            "Answer them, or drop one deliberately with --prune <id> \"reason\"."
        )

    sha = commit if commit is not None else head_commit(config.code_repo)
    conn.execute(
        "UPDATE spec SET status='verified', verified_at=?, verified_by=?,"
        " verified_against_commit=?, demoted_at=NULL, demoted_reason=NULL, updated_at=?"
        " WHERE id=?",
        (db.now(), by, sha, db.now(), spec_id),
    )
    db.record_event(conn, spec_id, "verified", by, f"against {sha}")


def forget(conn, paths: Paths, spec_id: str, by: str) -> None:
    """Remove a spec's row entirely — the only recovery path after `rm -rf specs/<id>`.

    Refuses if the folder still exists: forgetting a spec that is still on disk is almost
    always a mistake, and `publishes_to_wiki = 0` is the right tool for "keep it, stop
    publishing it". Foreign keys cascade the row's dependencies, resources and open
    questions. `spec_event` has no FK to `spec` on purpose — the audit trail is meant to
    outlive the spec it was about, so forgetting a spec does not erase the fact that it
    once existed and was worked on.
    """
    # Resolved through spec.path, not `specs/<id>` — a renamed folder keeps the id but
    # moves the path, and this guard exists specifically to check the folder that is
    # actually there. _spec_directory also serves as the existence check.
    directory = _spec_directory(conn, paths, spec_id)
    if directory.exists():
        raise RuntimeError(
            f"{directory.relative_to(paths.root).as_posix()} still exists on disk — "
            "forget is only for a spec whose folder is already gone. If you want to keep "
            "the folder but stop publishing it, set publishes_to_wiki = 0 for it instead."
        )

    db.record_event(conn, spec_id, "forgotten", by, None)
    conn.execute("DELETE FROM spec WHERE id = ?", (spec_id,))


def demote(conn, spec_id: str, reason: str, actor: str) -> None:
    """Staleness is a demotion, not a third status. The writer's audit survives it."""
    conn.execute(
        "UPDATE spec SET status='draft', demoted_at=?, demoted_reason=?, updated_at=?"
        " WHERE id=?",
        (db.now(), reason, db.now(), spec_id),
    )
    db.record_event(conn, spec_id, "demoted", actor, reason)
