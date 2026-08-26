import subprocess

import pytest

from knowledge import db, deps, lifecycle, scan
from knowledge.config import Config
from tests.conftest import write_spec


def test_route_to_glob_ignores_route_groups():
    # /platform/assets lives at app/platform/(menuLayout)/assets/page.tsx
    assert deps.route_to_glob("/platform/assets") == "app/**/assets/page.tsx"
    assert deps.route_to_glob("/landing") == "app/**/landing/page.tsx"
    assert deps.route_to_glob("/platform/expenses/calendar") == (
        "app/**/expenses/calendar/page.tsx"
    )


def test_route_to_glob_handles_a_dynamic_segment():
    # A dynamic segment becomes *, not [*] — [*] is a character class matching one literal
    # asterisk, while the real directory is named [incomeSourceId].
    assert deps.route_to_glob("/platform/incomes/{incomeSourceId}") == (
        "app/**/incomes/*/page.tsx"
    )


def test_a_dynamic_glob_matches_a_real_nextjs_directory():
    globs = {deps.route_to_glob("/platform/incomes/{incomeSourceId}")}
    changed = ["app/platform/(menuLayout)/incomes/[incomeSourceId]/page.tsx"]
    assert deps.matches(globs, changed) == changed


def test_endpoint_to_glob():
    assert deps.endpoint_to_glob("/api/cron") == "app/api/cron/**/route.ts"
    assert deps.endpoint_to_glob("/api/loans-out/summary") == (
        "app/api/loans-out/summary/**/route.ts"
    )


def test_an_endpoint_glob_matches_a_route_handler_directly_beneath_it():
    globs = {deps.endpoint_to_glob("/api/cron")}
    assert deps.matches(globs, ["app/api/cron/route.ts"]) == ["app/api/cron/route.ts"]


def test_derived_globs_come_from_the_specs_own_triples(repo):
    assert deps.derived_globs(repo, "assets") == {"app/**/assets/page.tsx"}
    assert deps.derived_globs(repo, "concepts") == set()


def test_manual_globs_are_added_to_derived_ones(repo):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    conn.execute(
        "INSERT INTO spec_dependency (spec_id, glob, note)"
        " VALUES ('assets','modules/server/submodules/assets/**','the service layer')"
    )
    assert deps.spec_globs(conn, repo, "assets") == {
        "app/**/assets/page.tsx",
        "modules/server/submodules/assets/**",
    }


def test_matches_uses_full_glob_semantics():
    globs = {"app/**/assets/page.tsx", "modules/server/submodules/assets/**"}
    changed = [
        "app/platform/(menuLayout)/assets/page.tsx",
        "modules/server/submodules/assets/services/create/index.ts",
        "modules/ui/components/Button/index.tsx",
    ]
    assert deps.matches(globs, changed) == [
        "app/platform/(menuLayout)/assets/page.tsx",
        "modules/server/submodules/assets/services/create/index.ts",
    ]


@pytest.fixture
def code_repo(tmp_path):
    root = tmp_path / "code"
    (root / "app" / "platform" / "(menuLayout)" / "assets").mkdir(parents=True)
    (root / "app" / "platform" / "(menuLayout)" / "assets" / "page.tsx").write_text("x\n")
    (root / "README.md").write_text("hello\n")
    subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "T"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", "init"], check=True,
                   capture_output=True)
    return root


def test_check_demotes_a_spec_whose_dependency_changed(repo, code_repo):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    config = Config(code_repo=code_repo, wiki_remote="x")
    base = lifecycle.head_commit(code_repo)

    lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
    lifecycle.verify(conn, repo, config, "assets", by="jesus", prune=[], commit=base)

    page = code_repo / "app" / "platform" / "(menuLayout)" / "assets" / "page.tsx"
    page.write_text("changed\n")
    subprocess.run(["git", "-C", str(code_repo), "commit", "-am", "change"], check=True,
                   capture_output=True)

    findings = deps.check(conn, repo, config, demote=True)
    assert findings == [("assets", ["app/platform/(menuLayout)/assets/page.tsx"])]
    assert list(conn.execute("SELECT status FROM spec WHERE id='assets'")) == [("draft",)]


def test_check_ignores_an_unrelated_change(repo, code_repo):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    config = Config(code_repo=code_repo, wiki_remote="x")
    base = lifecycle.head_commit(code_repo)

    lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
    lifecycle.verify(conn, repo, config, "assets", by="jesus", prune=[], commit=base)

    (code_repo / "README.md").write_text("goodbye\n")
    subprocess.run(["git", "-C", str(code_repo), "commit", "-am", "readme"], check=True,
                   capture_output=True)

    assert deps.check(conn, repo, config, demote=True) == []
    assert list(conn.execute("SELECT status FROM spec WHERE id='assets'")) == [("verified",)]


def test_check_only_looks_at_verified_specs(repo, code_repo):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    config = Config(code_repo=code_repo, wiki_remote="x")
    # assets is left as a draft; nothing to demote regardless of what changed.
    assert deps.check(conn, repo, config, demote=True) == []


def test_check_demotes_a_spec_whose_dependency_was_renamed(repo, code_repo):
    """git reports only the destination of a rename by default. If changed_files did not
    also report the source path, this manual glob (which names the old directory) would
    match nothing and the spec would never be flagged."""
    conn = db.connect(repo)
    scan.scan(conn, repo)
    config = Config(code_repo=code_repo, wiki_remote="x")

    conn.execute(
        "INSERT INTO spec_dependency (spec_id, glob, note)"
        " VALUES ('assets','modules/server/submodules/assets/**','the service layer')"
    )
    service_dir = code_repo / "modules" / "server" / "submodules" / "assets"
    service_dir.mkdir(parents=True)
    (service_dir / "index.ts").write_text("export {}\n")
    subprocess.run(["git", "-C", str(code_repo), "add", "-A"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(code_repo), "commit", "-m", "add service"], check=True,
                   capture_output=True)

    lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
    base = lifecycle.head_commit(code_repo)
    lifecycle.verify(conn, repo, config, "assets", by="jesus", prune=[], commit=base)

    subprocess.run(
        ["git", "-C", str(code_repo), "mv",
         "modules/server/submodules/assets", "modules/server/submodules/assets2"],
        check=True, capture_output=True,
    )
    subprocess.run(["git", "-C", str(code_repo), "commit", "-m", "rename"], check=True,
                   capture_output=True)

    findings = deps.check(conn, repo, config, demote=True)
    assert findings == [("assets", ["modules/server/submodules/assets/index.ts"])]
    assert list(conn.execute("SELECT status FROM spec WHERE id='assets'")) == [("draft",)]


def test_check_accepts_a_code_repo_override(repo, code_repo, tmp_path):
    """CI checks the code repo out inside the workspace, not where knowledge.toml points."""
    conn = db.connect(repo)
    scan.scan(conn, repo)
    # A config pointing somewhere that does not exist, to prove the override is what is used.
    config = Config(code_repo=tmp_path / "nonexistent", wiki_remote="x")
    base = lifecycle.head_commit(code_repo)

    lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
    lifecycle.verify(conn, repo, config, "assets", by="jesus", prune=[], commit=base)

    page = code_repo / "app" / "platform" / "(menuLayout)" / "assets" / "page.tsx"
    page.write_text("changed\n")
    subprocess.run(["git", "-C", str(code_repo), "commit", "-am", "change"], check=True,
                   capture_output=True)

    findings = deps.check(conn, repo, config, demote=True, code_repo=code_repo)
    assert findings == [("assets", ["app/platform/(menuLayout)/assets/page.tsx"])]


def test_uncheckable_lists_a_verified_spec_with_no_dependencies(repo):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    conn.execute("UPDATE spec SET status='verified' WHERE id IN ('assets','concepts')")
    # assets has a derived glob from its mon:route; concepts has neither a route/endpoint
    # nor a manual dependency, so only concepts is uncheckable.
    assert deps.uncheckable(conn, repo) == ["concepts"]


def test_uncheckable_excludes_a_spec_once_it_has_a_manual_glob(repo):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    conn.execute("UPDATE spec SET status='verified' WHERE id IN ('assets','concepts')")
    conn.execute(
        "INSERT INTO spec_dependency (spec_id, glob, note)"
        " VALUES ('concepts','prisma/schema.prisma','the data model')"
    )
    assert deps.uncheckable(conn, repo) == []
