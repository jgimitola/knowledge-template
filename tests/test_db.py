import os
import sqlite3
import time

from knowledge import db


def test_connect_creates_every_table(repo):
    conn = db.connect(repo)
    names = {
        row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert set(db.TABLES) <= names


def test_status_is_constrained_to_two_values(repo):
    conn = db.connect(repo)
    try:
        conn.execute(
            "INSERT INTO spec (id,title,path,status,created_at,updated_at)"
            " VALUES ('x','X','specs/x','stale','t','t')"
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("status should reject anything but draft or verified")


def test_dump_is_deterministic_and_round_trips(repo):
    conn = db.connect(repo)
    conn.execute(
        "INSERT INTO spec (id,title,path,status,created_at,updated_at)"
        " VALUES ('assets','Assets','specs/assets','draft','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO spec (id,title,path,status,created_at,updated_at)"
        " VALUES ('concepts','Concepts','specs/concepts','verified','2026-01-01T00:00:00Z','2026-01-01T00:00:00Z')"
    )
    db.save(conn, repo)
    first = repo.dump.read_text(encoding="utf-8")

    db.save(conn, repo)
    assert repo.dump.read_text(encoding="utf-8") == first

    conn.close()          # release the handle before deleting the file it points at
    repo.db.unlink()
    reloaded = db.connect(repo)
    rows = list(reloaded.execute("SELECT id, status FROM spec ORDER BY id"))
    assert rows == [("assets", "draft"), ("concepts", "verified")]

    db.save(reloaded, repo)
    assert repo.dump.read_text(encoding="utf-8") == first
    reloaded.close()


def test_a_value_containing_a_quote_survives_the_round_trip(repo):
    conn = db.connect(repo)
    conn.execute(
        "INSERT INTO spec (id,title,path,status,created_at,updated_at)"
        " VALUES ('q','It''s fine','specs/q','draft','t','t')"
    )
    db.save(conn, repo)
    conn.close()
    repo.db.unlink()
    reloaded = db.connect(repo)
    assert list(reloaded.execute("SELECT title FROM spec"))[0][0] == "It's fine"
    reloaded.close()


def test_record_event_appends(repo):
    conn = db.connect(repo)
    conn.execute(
        "INSERT INTO spec (id,title,path,status,created_at,updated_at)"
        " VALUES ('a','A','specs/a','draft','t','t')"
    )
    db.record_event(conn, "a", "created", "jesus", None)
    db.record_event(conn, "a", "verified", "jesus", "against abc123")
    rows = list(conn.execute("SELECT event, actor, detail FROM spec_event ORDER BY id"))
    assert rows == [("created", "jesus", None), ("verified", "jesus", "against abc123")]


def test_the_dump_is_written_with_lf_endings_on_every_platform(repo):
    """dump.sql is a tracked artifact compared byte-for-byte by CI on Linux."""
    conn = db.connect(repo)
    conn.execute(
        "INSERT INTO spec (id,title,path,status,created_at,updated_at)"
        " VALUES ('a','A','specs/a','draft','t','t')"
    )
    db.save(conn, repo)
    assert b"\r\n" not in repo.dump.read_bytes()


def test_a_connection_bootstrapped_from_the_dump_still_enforces_foreign_keys(repo):
    """PRAGMA foreign_keys is connection-scoped, and the dump turns it off to restore."""
    conn = db.connect(repo)
    conn.execute(
        "INSERT INTO spec (id,title,path,status,created_at,updated_at)"
        " VALUES ('a','A','specs/a','draft','t','t')"
    )
    conn.execute("INSERT INTO spec_dependency (spec_id, glob) VALUES ('a','app/**')")
    db.save(conn, repo)
    conn.close()

    repo.db.unlink()
    reloaded = db.connect(repo)
    assert list(reloaded.execute("PRAGMA foreign_keys"))[0][0] == 1

    # The cascade must actually fire, not merely be configured.
    reloaded.execute("DELETE FROM spec WHERE id = 'a'")
    assert list(reloaded.execute("SELECT COUNT(*) FROM spec_dependency"))[0][0] == 0
    reloaded.close()


def test_a_carriage_return_in_a_value_is_normalised_out_of_the_dump(repo):
    conn = db.connect(repo)
    conn.execute(
        "INSERT INTO spec (id,title,path,status,created_at,updated_at)"
        " VALUES ('a','A','specs/a','draft','t','t')"
    )
    conn.execute(
        "INSERT INTO open_question (spec_id, question, asked_by, asked_at, status)"
        " VALUES ('a','First line.\r\nSecond line.','writer','t','open')"
    )
    db.save(conn, repo)
    assert b"\r" not in repo.dump.read_bytes()

    conn.close()
    repo.db.unlink()
    reloaded = db.connect(repo)
    stored = list(reloaded.execute("SELECT question FROM open_question"))[0][0]
    assert stored == "First line.\nSecond line."
    reloaded.close()


def test_connect_reloads_from_a_dump_that_is_newer_than_the_local_database(repo, capsys):
    """A nightly CI job commits demotions to dump.sql; the author pulls, but their local
    knowledge.db still reflects the old state. Without this, the next `db.save` from that
    stale database would rewrite dump.sql back over the bot's commit. connect() must notice
    the dump moved forward and reload from it instead of trusting the local file blindly."""
    conn = db.connect(repo)
    conn.execute(
        "INSERT INTO spec (id,title,path,status,created_at,updated_at)"
        " VALUES ('a','A','specs/a','draft','t','t')"
    )
    db.save(conn, repo)
    conn.close()
    capsys.readouterr()

    # Simulate a bot commit: a dump.sql with a row absent from the local database, and a
    # newer mtime than knowledge.db — exactly what `git pull` produces. Build it with a
    # real in-memory connection, the same way `db.dump` would, rather than hand-writing SQL.
    fresh = sqlite3.connect(":memory:")
    fresh.executescript(db.SCHEMA)
    fresh.execute(
        "INSERT INTO spec (id,title,path,status,created_at,updated_at)"
        " VALUES ('a','A','specs/a','draft','t','t')"
    )
    fresh.execute(
        "INSERT INTO spec (id,title,path,status,created_at,updated_at)"
        " VALUES ('b','B','specs/b','draft','t','t')"
    )
    db.dump(fresh, repo.dump)
    fresh.close()

    # Make sure the dump is unambiguously newer than knowledge.db on filesystems with
    # coarse mtime resolution.
    now = time.time() + 2
    os.utime(repo.dump, (now, now))

    reloaded = db.connect(repo)
    rows = sorted(r[0] for r in reloaded.execute("SELECT id FROM spec"))
    assert rows == ["a", "b"]
    assert "reloading the database from the dump" in capsys.readouterr().out
    reloaded.close()
