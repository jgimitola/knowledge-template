# Task 7 review package

BASE: b3f8401
HEAD: 7169aed

## Commits
```
7169aed fix: render with --dry-run regardless of target, and clear stale pages in a directory publish
9118e93 feat: configure the sidebar and the publishing target
```

## Stat
```
 src/knowledge/cli.py      |  56 ++++++++++++++++++++++--
 src/knowledge/publish.py  | 101 ++++++++++---------------------------------
 tests/conftest.py         |  22 +++++++++-
 tests/test_cli_publish.py | 107 ++++++++++++++++++++++++++++++++++++++++++++++
 tests/test_publish.py     |  52 +++++++++++++++++-----
 5 files changed, 245 insertions(+), 93 deletions(-)
```

## Project-wide constraint: no monicords strings in src/ or tests/
```
(none — this task closes the constraint)
```

## Full diff (-U10)
```diff
diff --git a/src/knowledge/cli.py b/src/knowledge/cli.py
index 90ac87d..1361a4b 100644
--- a/src/knowledge/cli.py
+++ b/src/knowledge/cli.py
@@ -470,56 +470,101 @@ def _clear_markdown(out_dir: Path) -> list[str]:
     return removed
 
 
 def cmd_publish(args: argparse.Namespace) -> int:
     import shutil
     import tempfile
 
     paths, config, conn = open_repo(args)
     from knowledge import publish
 
+    # --dry-run means "render locally, push nothing" — it is not a mode of publishing, it is
+    # the thing you do *instead* of publishing. So it runs regardless of publish.target,
+    # including "none": a fresh template user can preview what would be published before
+    # they have decided (or configured) where it would go.
     if args.dry_run:
         out = Path(args.output) if args.output else paths.root / "build" / "wiki"
         out.mkdir(parents=True, exist_ok=True)
         existing = set(_clear_markdown(out))
-        written = publish.write_pages(conn, paths, out)
+        written = publish.write_pages(conn, paths, out, config.publish.sidebar)
         print(f"{len(written)} page(s) written to {out}")
         for name in sorted(written):
             print("   ", name)
         stale = sorted(existing - set(written))
         if stale:
             print(f"{len(stale)} stale page(s) removed: {', '.join(stale)}")
         return 0
 
+    target = config.publish.target
+    if target == "none":
+        # "none" is the shipped default, and it guards only a real publish — --dry-run above
+        # already handles the "just show me" case regardless of this. A freshly-templated
+        # repository has no wiki, no publish directory — nothing this tooling could safely
+        # guess — so it refuses to publish rather than picking a destination (e.g. assuming
+        # github-wiki) that the project never asked for.
+        print(
+            "publishing is not configured — set publish.target in knowledge.toml"
+            " to 'directory' or 'github-wiki'",
+            file=sys.stderr,
+        )
+        return 1
+    if target == "directory":
+        # Emptiness is checked on the raw string, before it becomes a Path: Path("")
+        # normalises to Path("."), whose str() is "." — truthy — so the same check made
+        # after wrapping in Path could never fire.
+        raw_out_dir = args.out_dir or config.publish.out_dir
+        if not raw_out_dir:
+            print(
+                "publish.out_dir is required when publish.target is 'directory'",
+                file=sys.stderr,
+            )
+            return 1
+        out_dir = Path(raw_out_dir)
+        out_dir.mkdir(parents=True, exist_ok=True)
+        # Same reason the dry-run and github-wiki paths both clear first: a directory publish
+        # is a standing output a reader opens later and trusts. A renamed or dropped spec has
+        # to actually lose its stale page, not leave one sitting there looking current.
+        existing = set(_clear_markdown(out_dir))
+        written = publish.write_pages(conn, paths, out_dir, config.publish.sidebar)
+        print(f"{len(written)} page(s) written to {out_dir}")
+        stale = sorted(existing - set(written))
+        if stale:
+            print(f"{len(stale)} stale page(s) removed: {', '.join(stale)}")
+        return 0
+
     workdir = Path(tempfile.mkdtemp(prefix="knowledge-wiki-"))
     try:
         clone = workdir / "wiki"
         try:
             gitcmd.run(
                 ["clone", config.publish.remote, str(clone)],
                 check=True, capture_output=True, text=True,
             )
         except subprocess.CalledProcessError as exc:
             print("error: could not clone the wiki repository")
             print(f"   {exc.stderr.strip()}")
             print(
                 "   A GitHub wiki repository does not exist until at least one page has been "
                 "created through the web UI — if this is a brand-new wiki, create a page "
                 "there first, then retry."
             )
             return 1
 
         _clear_markdown(clone)
-        written = publish.write_pages(conn, paths, clone)
+        written = publish.write_pages(conn, paths, clone, config.publish.sidebar)
         try:
             pushed = publish.push(
-                clone, config.publish.remote, f"docs: sync {len(written)} page(s)"
+                clone,
+                config.publish.remote,
+                f"docs: sync {len(written)} page(s)",
+                config.publish.committer_name,
+                config.publish.committer_email,
             )
         except subprocess.CalledProcessError as exc:
             print("error: could not push to the wiki repository")
             print(f"   {exc.stderr.strip()}")
             return 1
         print(f"{len(written)} page(s) {'pushed' if pushed else 'already current'}")
     finally:
         shutil.rmtree(workdir, ignore_errors=True)
     return 0
 
@@ -673,20 +718,25 @@ def build_parser() -> argparse.ArgumentParser:
     dep_p = sub.add_parser("dep", help="inspect or edit a spec's manual dependencies")
     dep_p.add_argument("action", choices=["list", "add", "remove"])
     dep_p.add_argument("spec")
     dep_p.add_argument("glob", nargs="?")
     dep_p.add_argument("--note")
     dep_p.set_defaults(handler=cmd_dep)
 
     pub_p = sub.add_parser("publish", help="render the specs and push them to the wiki")
     pub_p.add_argument("--dry-run", action="store_true", help="write locally, do not push")
     pub_p.add_argument("-o", "--output", help="where --dry-run writes (default build/wiki)")
+    pub_p.add_argument(
+        "--out-dir",
+        help="where to write pages when publish.target is 'directory'"
+        " (overrides knowledge.toml's publish.out_dir)",
+    )
     pub_p.set_defaults(handler=cmd_publish)
 
     return parser
 
 
 def main() -> int:
     parser = build_parser()
     args = parser.parse_args()
     if args.handler is None:
         parser.print_help()
diff --git a/src/knowledge/publish.py b/src/knowledge/publish.py
index 3947f09..273efad 100644
--- a/src/knowledge/publish.py
+++ b/src/knowledge/publish.py
@@ -1,88 +1,30 @@
 """Render specs into wiki pages and push them.
 
 Turtle is not inlined: the wiki carries prose, and the graph is available as an exported
-artifact. Only _Sidebar.md is generated — Home carries the product description and its own
-mon:Actor declarations, so it stays an ordinary spec and publishes like any other page.
+artifact. Only _Sidebar.md is generated — Home carries the project description and whatever
+vocabulary declarations its own spec.ttl holds, so it stays an ordinary spec and publishes
+like any other page.
 """
 
 from __future__ import annotations
 
 import re
 from pathlib import Path
 
 from knowledge import gitcmd
+from knowledge.config import Sidebar
 from knowledge.graph import page_name
 from knowledge.paths import Paths
 
 FRONTMATTER = re.compile(r"\A---\n.*?\n---\n\s*", re.S)
 
-# Reading order, not alphabetical. Anything not named here is appended alphabetically, so a
-# new spec appears in the sidebar without this list having to be edited first.
-SIDEBAR_ORDER = [
-    "home",
-    "concepts",
-    "onboarding",
-    "onboarding-landing",
-    "onboarding-workspace",
-    "onboarding-welcome",
-    "profile",
-    "profile-account",
-    "profile-password",
-    "profile-workspaces",
-    "profile-categories",
-    "profile-settings",
-    "assets",
-    "incomes",
-    "incomes-detail",
-    "expenses",
-    "expenses-calendar",
-    "expenses-log",
-    "expenses-plan",
-    "loans-out",
-]
-
-# Filed under **Reference** rather than the module list: contributor documentation about the
-# codebase, not something the product does. Ontology has no spec row of its own — it renders
-# from ontology/README.md — so it is emitted directly, ahead of anything named here; every
-# entry in this list must be an actual spec id so it can carry its own title.
-SIDEBAR_REFERENCE = ["architecture"]
-
-# A page's title is usually the right nav label. Home is the exception: its H1 is the
-# product name, which says nothing in a sidebar that is already the product's wiki.
-SIDEBAR_LABELS = {"home": "Home"}
-
-# A bold section header inserted right before the named spec's entry, so the grouping
-# survives a reordering of SIDEBAR_ORDER instead of being pinned to a hardcoded index.
-SIDEBAR_HEADER_BEFORE = {"onboarding": "Modules"}
-
-# The retired wiki-sync.yml workflow's committer identity, kept so the wiki's history doesn't
-# suddenly change authors. A fresh clone has no local identity, and CI runners frequently have
-# none globally either, so this is set on the clone itself rather than assumed.
-BOT_NAME = "github-actions[bot]"
-BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"
-
-NESTED_UNDER = {
-    "onboarding-landing": "onboarding",
-    "onboarding-workspace": "onboarding",
-    "onboarding-welcome": "onboarding",
-    "profile-account": "profile",
-    "profile-password": "profile",
-    "profile-workspaces": "profile",
-    "profile-categories": "profile",
-    "profile-settings": "profile",
-    "incomes-detail": "incomes",
-    "expenses-calendar": "expenses",
-    "expenses-log": "expenses",
-    "expenses-plan": "expenses",
-}
-
 
 def strip_frontmatter(text: str) -> str:
     return FRONTMATTER.sub("", text)
 
 
 def _spec_directory(conn, paths: Paths, spec_id: str) -> Path:
     """Resolve a spec's folder from its `path` column, kept current by `scan`, rather than
     reconstructing `paths.specs / spec_id`. The id and the folder name are only required to
     match at creation time — a rename keeps the id but changes the folder — and this is one
     of two places (with `lifecycle.mark_modeled`) that took an id straight from the database,
@@ -98,48 +40,47 @@ def render_page(conn, paths: Paths, spec_id: str) -> str:
     return strip_frontmatter((directory / "spec.md").read_text(encoding="utf-8"))
 
 
 def _published(conn) -> list[tuple[str, str, str]]:
     return list(conn.execute(
         "SELECT id, title, COALESCE(wiki_page, id) FROM spec"
         " WHERE publishes_to_wiki = 1 ORDER BY id"
     ))
 
 
-def render_sidebar(conn) -> str:
+def render_sidebar(conn, sidebar: Sidebar) -> str:
     rows = {spec_id: (title, page) for spec_id, title, page in _published(conn)}
-    reference = set(SIDEBAR_REFERENCE)
-    ordered = [s for s in SIDEBAR_ORDER if s in rows and s not in reference]
-    ordered += sorted(s for s in rows if s not in SIDEBAR_ORDER and s not in reference)
+    reference = set(sidebar.reference)
+    ordered = [s for s in sidebar.order if s in rows and s not in reference]
+    ordered += sorted(s for s in rows if s not in sidebar.order and s not in reference)
 
-    lines = ["### Monicords", ""]
+    lines = [f"### {sidebar.title}", ""] if sidebar.title else []
     for spec_id in ordered:
-        header = SIDEBAR_HEADER_BEFORE.get(spec_id)
+        header = sidebar.header_before.get(spec_id)
         if header:
             lines += ["", f"**{header}**", ""]
         title, page = rows[spec_id]
-        label = SIDEBAR_LABELS.get(spec_id, title)
-        indent = "  " if spec_id in NESTED_UNDER else ""
+        label = sidebar.labels.get(spec_id, title)
+        indent = "  " if spec_id in sidebar.nested_under else ""
         lines.append(f"{indent}- [{label}]({page})")
 
     lines += ["", "**Reference**", "", "- [Ontology](Ontology)"]
-    for spec_id in SIDEBAR_REFERENCE:
+    for spec_id in sidebar.reference:
         if spec_id not in rows:
             continue
         title, page = rows[spec_id]
-        label = SIDEBAR_LABELS.get(spec_id, title)
-        lines.append(f"- [{label}]({page})")
+        lines.append(f"- [{sidebar.labels.get(spec_id, title)}]({page})")
     lines.append("")
     return "\n".join(lines)
 
 
-def write_pages(conn, paths: Paths, out_dir: Path) -> list[str]:
+def write_pages(conn, paths: Paths, out_dir: Path, sidebar: Sidebar) -> list[str]:
     out_dir.mkdir(parents=True, exist_ok=True)
     written: list[str] = []
     for spec_id, _title, page in _published(conn):
         directory = _spec_directory(conn, paths, spec_id)
         if not (directory / "spec.md").is_file():
             # A row without a folder — usually `rm -rf specs/<id>` without `knowledge
             # forget`. Skip it rather than crash: a publish that omits one page and says
             # so beats one that fails entirely and publishes nothing.
             print(
                 f"warning: {spec_id} has a row but no spec.md — skipping it. "
@@ -154,37 +95,41 @@ def write_pages(conn, paths: Paths, out_dir: Path) -> list[str]:
         (out_dir / name).write_text(
             render_page(conn, paths, spec_id), encoding="utf-8", newline="\n"
         )
         written.append(name)
 
     (out_dir / "Ontology.md").write_text(
         paths.ontology_readme.read_text(encoding="utf-8"), encoding="utf-8", newline="\n"
     )
     written.append("Ontology.md")
 
-    (out_dir / "_Sidebar.md").write_text(render_sidebar(conn), encoding="utf-8", newline="\n")
+    (out_dir / "_Sidebar.md").write_text(
+        render_sidebar(conn, sidebar), encoding="utf-8", newline="\n"
+    )
     written.append("_Sidebar.md")
     return written
 
 
-def push(out_dir: Path, remote: str, message: str) -> bool:
+def push(
+    out_dir: Path, remote: str, message: str, committer_name: str, committer_email: str
+) -> bool:
     """Returns True when something was pushed, False when the wiki was already current.
 
     Raises subprocess.CalledProcessError on any git failure; the caller is responsible for
     turning that into a clean CLI error rather than a traceback.
     """
     gitcmd.run(
-        ["-C", str(out_dir), "config", "user.name", BOT_NAME],
+        ["-C", str(out_dir), "config", "user.name", committer_name],
         check=True, capture_output=True, text=True,
     )
     gitcmd.run(
-        ["-C", str(out_dir), "config", "user.email", BOT_EMAIL],
+        ["-C", str(out_dir), "config", "user.email", committer_email],
         check=True, capture_output=True, text=True,
     )
     gitcmd.run(
         ["-C", str(out_dir), "add", "-A"], check=True, capture_output=True, text=True
     )
     staged = gitcmd.run(
         ["-C", str(out_dir), "diff", "--staged", "--quiet"], check=False
     )
     if staged.returncode == 0:
         return False
diff --git a/tests/conftest.py b/tests/conftest.py
index a7bcd3a..a857fb2 100644
--- a/tests/conftest.py
+++ b/tests/conftest.py
@@ -127,20 +127,28 @@ def _write_spec(root, spec_id, ttl, prose="Some prose.\n"):
     (directory / "spec.ttl").write_text(ttl, encoding="utf-8")
     return directory
 
 
 @pytest.fixture
 def write_spec():
     """Tasks 4-7 request this as a fixture rather than importing it."""
     return _write_spec
 
 
+@pytest.fixture
+def seeded_conn(repo):
+    from knowledge import db, scan
+    conn = db.connect(repo)
+    scan.scan(conn, repo)
+    return conn
+
+
 # A separate template from CONFIG_TOML above: knowledge.toml's [repo]/[publish] values
 # overridden for one test, with the rest of the vocabulary/dependencies configuration a
 # working repository still needs. Kept distinct from the fixture ontology's namespace/prefix
 # so a caller only overrides what a given test actually cares about.
 KNOWLEDGE_TOML = """\
 [project]
 name = "Example"
 
 [vocabulary]
 ontology_file = "ontology.ttl"
@@ -161,27 +169,37 @@ verbatim_string_properties = ["emptyState"]
 code_repo = "{code_repo}"
 
 [dependencies]
 route_property = "route"
 endpoint_property = "endpoint"
 route_glob = "app/**/{{segments}}/page.tsx"
 endpoint_glob = "app/{{path}}/**/route.ts"
 absorbed_prefixes = ["platform"]
 
 [publish]
+target = "{target}"
 remote = "{remote}"
+out_dir = "{out_dir}"
 """
 
 
-def write_knowledge_toml(root, *, code_repo="../code", remote="https://example.com/x.wiki.git"):
+def write_knowledge_toml(
+    root,
+    *,
+    code_repo="../code",
+    remote="https://example.com/x.wiki.git",
+    target="github-wiki",
+    out_dir="",
+):
     (root / "knowledge.toml").write_text(
-        KNOWLEDGE_TOML.format(code_repo=code_repo, remote=remote), encoding="utf-8"
+        KNOWLEDGE_TOML.format(code_repo=code_repo, remote=remote, target=target, out_dir=out_dir),
+        encoding="utf-8",
     )
     return root
 
 
 def make_config(code_repo, remote="https://example.com/x.wiki.git"):
     """A Config for tests that exercise lifecycle/deps functions directly, without going
     through load_config. Same example vocabulary as KNOWLEDGE_TOML above."""
     return Config(
         project_name="Example",
         vocabulary=Vocabulary(
diff --git a/tests/test_cli_publish.py b/tests/test_cli_publish.py
index 2f79b21..5689f7b 100644
--- a/tests/test_cli_publish.py
+++ b/tests/test_cli_publish.py
@@ -86,10 +86,117 @@ def test_publish_skips_a_spec_whose_folder_is_gone_instead_of_crashing(working,
     (working.specs / "concepts").rmdir()
 
     out = tmp_path / "wiki-out"
     args = run(["publish", "--dry-run", "-o", str(out)])
     assert args.handler(args) == 0
     printed = capsys.readouterr().out
     assert "concepts" in printed
     assert "knowledge forget" in printed
     assert not (out / "Concepts.md").exists()
     assert (out / "Assets.md").is_file()
+
+
+def test_publish_target_none_fails_with_a_readable_message_instead_of_a_traceback(
+    working, capsys
+):
+    """'none' is the shipped default — a template cannot know where its user publishes, and
+    guessing a destination is worse than requiring one. This must be a clean, actionable
+    error, not an attempt to clone an empty remote."""
+    write_knowledge_toml(working.root, target="none")
+
+    args = run(["publish"])
+    exit_code = args.handler(args)
+
+    assert exit_code == 1
+    err = capsys.readouterr().err
+    assert "publish.target" in err
+    assert "directory" in err
+    assert "github-wiki" in err
+
+
+def test_publish_directory_target_writes_pages_without_pushing(working, tmp_path, capsys):
+    out = tmp_path / "docs-out"
+    write_knowledge_toml(working.root, target="directory", out_dir=out.as_posix())
+
+    args = run(["publish"])
+    exit_code = args.handler(args)
+
+    assert exit_code == 0
+    assert (out / "Assets.md").is_file()
+    printed = capsys.readouterr().out
+    assert "page(s) written to" in printed
+    assert out.name in printed
+
+
+def test_publish_directory_target_out_dir_flag_overrides_the_config(working, tmp_path, capsys):
+    configured = tmp_path / "cfg-out"
+    write_knowledge_toml(working.root, target="directory", out_dir=configured.as_posix())
+    cli_out = tmp_path / "cli-out"
+
+    args = run(["publish", "--out-dir", str(cli_out)])
+    exit_code = args.handler(args)
+
+    assert exit_code == 0
+    assert (cli_out / "Assets.md").is_file()
+    assert not configured.exists()
+
+
+def test_publish_directory_target_without_an_out_dir_fails_cleanly(working, capsys):
+    """Regression guard for a `Path("")` trap: `Path("")` normalises to `Path(".")`, whose
+    `str()` is `"."` — truthy — so checking emptiness *after* wrapping in `Path` can never
+    catch a missing out_dir. The check has to happen on the raw string first."""
+    write_knowledge_toml(working.root, target="directory")
+
+    args = run(["publish"])
+    exit_code = args.handler(args)
+
+    assert exit_code == 1
+    err = capsys.readouterr().err
+    assert "publish.out_dir is required" in err
+
+
+def test_dry_run_succeeds_when_publish_target_is_none(working, tmp_path, capsys):
+    """--dry-run is a preview, not a mode of publishing — a fresh template user with nothing
+    configured yet must still be able to see what would be published."""
+    write_knowledge_toml(working.root, target="none")
+    out = tmp_path / "preview"
+
+    args = run(["publish", "--dry-run", "-o", str(out)])
+    exit_code = args.handler(args)
+
+    assert exit_code == 0
+    assert (out / "Assets.md").is_file()
+
+
+def test_dry_run_takes_the_dry_run_path_even_under_a_directory_target(working, tmp_path, capsys):
+    """A directory-target publish never lists individual pages; the dry-run path always does
+    (see test_dry_run_removes_a_stale_page_before_writing). That listing is the distinguishing
+    signal that --dry-run was honoured rather than silently ignored in favour of a real
+    directory write — which would skip -o's target entirely and write to the configured
+    out_dir instead."""
+    configured = tmp_path / "cfg-out"
+    write_knowledge_toml(working.root, target="directory", out_dir=configured.as_posix())
+    preview = tmp_path / "preview-out"
+
+    args = run(["publish", "--dry-run", "-o", str(preview)])
+    exit_code = args.handler(args)
+
+    assert exit_code == 0
+    assert (preview / "Assets.md").is_file()
+    assert not configured.exists()
+    printed = capsys.readouterr().out
+    assert "    Assets.md" in printed  # the dry-run path's per-page listing
+
+
+def test_publish_directory_target_removes_a_page_whose_spec_is_gone(working, tmp_path, capsys):
+    out = tmp_path / "docs-out"
+    out.mkdir()
+    (out / "Old-Name.md").write_text("stale content\n", encoding="utf-8")
+    write_knowledge_toml(working.root, target="directory", out_dir=out.as_posix())
+
+    args = run(["publish"])
+    exit_code = args.handler(args)
+
+    assert exit_code == 0
+    assert not (out / "Old-Name.md").exists()
+    printed = capsys.readouterr().out
+    assert "stale page(s) removed: Old-Name.md" in printed
diff --git a/tests/test_publish.py b/tests/test_publish.py
index e981cae..6e1b5d2 100644
--- a/tests/test_publish.py
+++ b/tests/test_publish.py
@@ -1,94 +1,126 @@
 from knowledge import db, publish, scan
+from knowledge.config import Sidebar
 
 
 def test_strip_frontmatter_removes_only_the_leading_block():
     text = "---\nid: assets\n---\n\n# Assets\n\nProse with --- inside.\n"
     assert publish.strip_frontmatter(text) == "# Assets\n\nProse with --- inside.\n"
 
 
 def test_render_page_has_no_frontmatter_and_no_turtle(repo):
     conn = db.connect(repo)
     scan.scan(conn, repo)
     page = publish.render_page(conn, repo, "assets")
     assert not page.startswith("---")
     assert "```turtle" not in page
     assert "# Assets" in page
 
 
 def test_write_pages_names_files_by_wiki_page(repo, tmp_path):
     conn = db.connect(repo)
     scan.scan(conn, repo)
-    written = publish.write_pages(conn, repo, tmp_path)
+    written = publish.write_pages(conn, repo, tmp_path, Sidebar())
     assert sorted(written) == ["Assets.md", "Concepts.md", "Ontology.md", "_Sidebar.md"]
     assert (tmp_path / "Assets.md").is_file()
 
 
 def test_write_pages_skips_a_spec_that_does_not_publish(repo, tmp_path):
     conn = db.connect(repo)
     scan.scan(conn, repo)
     conn.execute("UPDATE spec SET publishes_to_wiki = 0 WHERE id = 'concepts'")
-    written = publish.write_pages(conn, repo, tmp_path)
+    written = publish.write_pages(conn, repo, tmp_path, Sidebar())
     assert "Concepts.md" not in written
     assert "Assets.md" in written
 
 
 def test_the_sidebar_is_generated_and_lists_published_pages(repo, tmp_path):
     conn = db.connect(repo)
     scan.scan(conn, repo)
-    publish.write_pages(conn, repo, tmp_path)
+    publish.write_pages(conn, repo, tmp_path, Sidebar())
     sidebar = (tmp_path / "_Sidebar.md").read_text(encoding="utf-8")
     assert "[Assets](Assets)" in sidebar
     assert "[Ontology](Ontology)" in sidebar
 
 
-def test_the_sidebar_labels_home_as_home_not_its_page_title(repo, tmp_path):
+def test_the_sidebar_labels_home_using_the_configured_override(repo, tmp_path):
     home_dir = repo.specs / "home"
     home_dir.mkdir()
     (home_dir / "spec.md").write_text(
-        "---\nid: home\n---\n\n# Monicords\n\nProse.\n", encoding="utf-8"
+        "---\nid: home\n---\n\n# Example\n\nProse.\n", encoding="utf-8"
     )
     (home_dir / "spec.ttl").write_text("", encoding="utf-8")
     conn = db.connect(repo)
     scan.scan(conn, repo)
-    publish.write_pages(conn, repo, tmp_path)
+    publish.write_pages(conn, repo, tmp_path, Sidebar(labels={"home": "Home"}))
     sidebar = (tmp_path / "_Sidebar.md").read_text(encoding="utf-8")
     assert "[Home](Home)" in sidebar
-    assert "[Monicords](Home)" not in sidebar
+    assert "[Example](Home)" not in sidebar
 
 
 def test_the_reference_section_files_architecture_after_ontology(repo, tmp_path):
     arch_dir = repo.specs / "architecture"
     arch_dir.mkdir()
     (arch_dir / "spec.md").write_text(
         "---\nid: architecture\n---\n\n# Architecture\n\nProse.\n", encoding="utf-8"
     )
     (arch_dir / "spec.ttl").write_text("", encoding="utf-8")
     conn = db.connect(repo)
     scan.scan(conn, repo)
-    publish.write_pages(conn, repo, tmp_path)
+    bar = Sidebar(reference=("architecture",))
+    publish.write_pages(conn, repo, tmp_path, bar)
     sidebar = (tmp_path / "_Sidebar.md").read_text(encoding="utf-8")
 
     before_reference, _, after_reference = sidebar.partition("**Reference**")
     assert "[Architecture](Architecture)" not in before_reference
 
     ontology_index = after_reference.index("[Ontology](Ontology)")
     architecture_index = after_reference.index("[Architecture](Architecture)")
     assert ontology_index < architecture_index
 
 
 def test_write_pages_writes_lf_line_endings_on_every_platform(repo, tmp_path):
     """The wiki is a git repo; alternating CRLF (Windows) and LF (CI) publishes would rewrite
     every line of every page on every run."""
     conn = db.connect(repo)
     scan.scan(conn, repo)
-    written = publish.write_pages(conn, repo, tmp_path)
+    written = publish.write_pages(conn, repo, tmp_path, Sidebar())
     assert written
     for name in written:
         assert b"\r" not in (tmp_path / name).read_bytes()
 
 
 def test_the_ontology_page_comes_from_its_readme(repo, tmp_path):
     conn = db.connect(repo)
     scan.scan(conn, repo)
-    publish.write_pages(conn, repo, tmp_path)
+    publish.write_pages(conn, repo, tmp_path, Sidebar())
     assert "The vocabulary." in (tmp_path / "Ontology.md").read_text(encoding="utf-8")
+
+
+def test_sidebar_uses_the_configured_title_and_order(seeded_conn):
+    bar = Sidebar(title="Example", order=("concepts",), labels={"concepts": "Concepts"})
+    text = publish.render_sidebar(seeded_conn, bar)
+    assert text.startswith("### Example")
+    assert "- [Concepts](Concepts)" in text
+
+
+def test_unlisted_specs_are_appended_alphabetically(seeded_conn):
+    text = publish.render_sidebar(seeded_conn, Sidebar(title="Example", order=("concepts",)))
+    assert text.index("Concepts") < text.index("Assets")
+
+
+def test_nesting_and_headers_come_from_the_config(seeded_conn):
+    bar = Sidebar(
+        title="Example",
+        order=("concepts", "assets"),
+        nested_under={"assets": "concepts"},
+        header_before={"concepts": "Modules"},
+    )
+    text = publish.render_sidebar(seeded_conn, bar)
+    assert "**Modules**" in text
+    assert "  - [Assets](Assets)" in text
+
+
+def test_an_empty_sidebar_config_renders_every_spec_flat_and_alphabetical(seeded_conn):
+    text = publish.render_sidebar(seeded_conn, Sidebar(title="Example"))
+    assert "  - [" not in text
+    assert "**" not in text.split("**Reference**")[0].replace("### Example", "")
```
