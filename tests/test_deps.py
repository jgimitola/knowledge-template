import subprocess
from dataclasses import replace

import pytest

from knowledge import db, deps, lifecycle, scan
from knowledge.config import Dependencies
from tests.conftest import make_config

NEXTJS = Dependencies(
    route_property="route",
    endpoint_property="endpoint",
    route_glob="app/**/{segments}/page.tsx",
    endpoint_glob="app/{path}/**/route.ts",
    absorbed_prefixes=("platform",),
)


def test_route_glob_absorbs_the_configured_prefix():
    assert deps.route_to_glob("/platform/assets", NEXTJS) == "app/**/assets/page.tsx"


def test_route_glob_replaces_dynamic_segments():
    assert (
        deps.route_to_glob("/platform/incomes/{incomeSourceId}", NEXTJS)
        == "app/**/incomes/*/page.tsx"
    )


def test_route_glob_leaves_unabsorbed_prefixes_alone():
    assert deps.route_to_glob("/settings/profile", NEXTJS) == "app/**/settings/profile/page.tsx"


def test_endpoint_glob_tolerates_a_leading_method():
    assert deps.endpoint_to_glob("GET /api/cron", NEXTJS) == "app/api/cron/**/route.ts"


def test_a_different_framework_needs_no_code_change():
    django = Dependencies(
        route_property="route",
        route_glob="apps/**/{segments}/views.py",
        dynamic_segment="<...>",
    )
    assert deps.route_to_glob("/reports/<year>", django) == "apps/**/reports/*/views.py"


def test_derived_globs_are_empty_when_nothing_is_configured(repo, config):
    plain = replace(config, dependencies=Dependencies())
    assert deps.derived_globs(repo, plain, "assets") == set()


def test_a_dynamic_glob_matches_a_real_nextjs_directory():
    globs = {deps.route_to_glob("/platform/incomes/{incomeSourceId}", NEXTJS)}
    changed = ["app/platform/(menuLayout)/incomes/[incomeSourceId]/page.tsx"]
    assert deps.matches(globs, changed) == changed


def test_an_endpoint_glob_matches_a_route_handler_directly_beneath_it():
    globs = {deps.endpoint_to_glob("/api/cron", NEXTJS)}
    assert deps.matches(globs, ["app/api/cron/route.ts"]) == ["app/api/cron/route.ts"]


def test_derived_globs_come_from_the_specs_own_triples(repo, config):
    assert deps.derived_globs(repo, config, "assets") == {"app/**/assets/page.tsx"}
    assert deps.derived_globs(repo, config, "concepts") == set()


def test_manual_globs_are_added_to_derived_ones(repo, config):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    conn.execute(
        "INSERT INTO spec_dependency (spec_id, glob, note)"
        " VALUES ('assets','modules/server/submodules/assets/**','the service layer')"
    )
    assert deps.spec_globs(conn, repo, config, "assets") == {
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
    config = replace(make_config(code_repo, remote="x"), dependencies=NEXTJS)
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
    config = replace(make_config(code_repo, remote="x"), dependencies=NEXTJS)
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
    config = replace(make_config(code_repo, remote="x"), dependencies=NEXTJS)
    # assets is left as a draft; nothing to demote regardless of what changed.
    assert deps.check(conn, repo, config, demote=True) == []


def test_check_demotes_a_spec_whose_dependency_was_renamed(repo, code_repo):
    """git reports only the destination of a rename by default. If changed_files did not
    also report the source path, this manual glob (which names the old directory) would
    match nothing and the spec would never be flagged."""
    conn = db.connect(repo)
    scan.scan(conn, repo)
    config = replace(make_config(code_repo, remote="x"), dependencies=NEXTJS)

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
    config = replace(make_config(tmp_path / "nonexistent", remote="x"), dependencies=NEXTJS)
    base = lifecycle.head_commit(code_repo)

    lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
    lifecycle.verify(conn, repo, config, "assets", by="jesus", prune=[], commit=base)

    page = code_repo / "app" / "platform" / "(menuLayout)" / "assets" / "page.tsx"
    page.write_text("changed\n")
    subprocess.run(["git", "-C", str(code_repo), "commit", "-am", "change"], check=True,
                   capture_output=True)

    findings = deps.check(conn, repo, config, demote=True, code_repo=code_repo)
    assert findings == [("assets", ["app/platform/(menuLayout)/assets/page.tsx"])]


def test_check_refuses_when_no_code_repository_is_configured(repo, config):
    """config.code_repo is Optional; without this guard a spec that was never compared
    against any code repository would silently report zero findings, indistinguishable
    from a spec that was actually checked and found clean."""
    conn = db.connect(repo)
    scan.scan(conn, repo)
    no_repo = replace(config, code_repo=None)
    with pytest.raises(RuntimeError, match="no code repository configured"):
        deps.check(conn, repo, no_repo, demote=False)


def test_uncheckable_lists_a_verified_spec_with_no_dependencies(repo, config):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    conn.execute("UPDATE spec SET status='verified' WHERE id IN ('assets','concepts')")
    # assets has a derived glob from its route; concepts has neither a route/endpoint nor a
    # manual dependency, so only concepts is uncheckable.
    assert deps.uncheckable(conn, repo, config) == ["concepts"]


def test_uncheckable_excludes_a_spec_once_it_has_a_manual_glob(repo, config):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    conn.execute("UPDATE spec SET status='verified' WHERE id IN ('assets','concepts')")
    conn.execute(
        "INSERT INTO spec_dependency (spec_id, glob, note)"
        " VALUES ('concepts','prisma/schema.prisma','the data model')"
    )
    assert deps.uncheckable(conn, repo, config) == []
