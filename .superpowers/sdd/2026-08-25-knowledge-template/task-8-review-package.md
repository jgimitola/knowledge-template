# Task 8 review package

BASE: 7ab0b21
HEAD: d2d4c16

## Commits
```
d2d4c16 feat: remove the last project-specific strings from the CLI
```

## Stat
```
 src/knowledge/__init__.py |  2 +-
 src/knowledge/cli.py      | 41 ++++++++++++++++++++++++++++++++++++-----
 tests/test_cli_deps.py    | 34 ++++++++++++++++++++++++++++++++++
 tests/test_cli_read.py    | 23 +++++++++++++++++++++++
 4 files changed, 94 insertions(+), 6 deletions(-)
```

## Regression check: no project-specific strings
```
tests/test_cli_read.py:199:    assert "monicords" not in text.lower()
tests/test_cli_read.py:200:    # A description that only avoids the string "monicords" would still pass for any other
```

## Parser description as shipped
```
Author, track and publish a knowledge base.
```

## Full diff (-U10)
```diff
diff --git a/src/knowledge/__init__.py b/src/knowledge/__init__.py
index 5b1ad14..d45e34a 100644
--- a/src/knowledge/__init__.py
+++ b/src/knowledge/__init__.py
@@ -1 +1 @@
-"""Authoring, tracking and publishing for a project's knowledge base."""
+"""Authoring, tracking and publishing for a knowledge base."""
diff --git a/src/knowledge/cli.py b/src/knowledge/cli.py
index ff32c4b..d389bc0 100644
--- a/src/knowledge/cli.py
+++ b/src/knowledge/cli.py
@@ -7,21 +7,21 @@ commands go through db.save so the tracked dump.sql is always current.
 from __future__ import annotations
 
 import argparse
 import sqlite3
 import subprocess
 import sys
 from collections.abc import Sequence
 from pathlib import Path
 
 from knowledge import db, gitcmd, graph, scan
-from knowledge.config import Config, Sidebar, load_config
+from knowledge.config import Config, ConfigError, Sidebar, load_config
 from knowledge.paths import Paths, find_root, get_paths
 
 VERSION = "0.1.0"
 
 
 def open_repo(_args: argparse.Namespace) -> tuple[Paths, Config, sqlite3.Connection]:
     root = find_root()
     config = load_config(root)
     paths = get_paths(root, config.vocabulary.ontology_file)
     return paths, config, db.connect(paths)
@@ -413,20 +413,32 @@ def cmd_verify(args: argparse.Namespace) -> int:
         print(f"   {exc}")
         return 1
     db.save(conn, paths)
     print(f"{args.id} verified by {args.by}")
     return 0
 
 
 def cmd_stale(args: argparse.Namespace) -> int:
     paths, config, conn = open_repo(args)
     from knowledge import deps
+    # deps.check raises RuntimeError for the same condition, which main_argv would turn
+    # into an equivalent "error: ..." line — but that message is written for library
+    # callers, not this command's output. Guarding here means `stale` fails with its own
+    # clean, dedicated message before doing any of the git work, rather than borrowing
+    # deps.check's wording as a side effect of exception propagation.
+    if config.code_repo is None and not getattr(args, "code_repo", None):
+        print(
+            "no code repository configured — set repo.code_repo in knowledge.toml,"
+            " or pass --code-repo",
+            file=sys.stderr,
+        )
+        return 1
     override = Path(args.code_repo).resolve() if args.code_repo else None
     try:
         findings = deps.check(conn, paths, config, demote=args.demote, code_repo=override)
     except subprocess.CalledProcessError as exc:
         print(
             "error: git could not compare against the verified commit — either the "
             "verified_against_commit is not reachable in this checkout (a shallow clone "
             "missing history, or a ref other than the one the spec was verified against), "
             "or the commit no longer exists at all. In CI, check the code repository out "
             "with `fetch-depth: 0` and the right `ref:` so the full, correct history is "
@@ -574,20 +586,33 @@ def cmd_publish(args: argparse.Namespace) -> int:
     return 0
 
 
 def cmd_dep(args: argparse.Namespace) -> int:
     paths, config, conn = open_repo(args)
     from knowledge import deps
     if args.action in ("add", "remove") and not args.glob:
         print(f'usage: knowledge dep {args.action} <spec> "<glob>"')
         return 1
     if args.action == "add":
+        # Unlike `list`/`remove`, which only touch the database, `add` checks the new glob
+        # against the code repository's tracked files below — so it needs one configured.
+        # Without this guard a missing code_repo reached deps.tracked_files as None, which
+        # surfaced as a swallowed git error ("could not change to 'None'") reported as a
+        # mere warning after the dependency had already been inserted; fail clearly first,
+        # the same way `stale` does for the same condition.
+        if config.code_repo is None and not getattr(args, "code_repo", None):
+            print(
+                "no code repository configured — set repo.code_repo in knowledge.toml,"
+                " or pass --code-repo",
+                file=sys.stderr,
+            )
+            return 1
         if not list(conn.execute("SELECT 1 FROM spec WHERE id = ?", (args.spec,))):
             print(f"refused: no spec with id {args.spec!r}")
             return 1
         conn.execute(
             "INSERT OR REPLACE INTO spec_dependency (spec_id, glob, note) VALUES (?,?,?)",
             (args.spec, args.glob, args.note),
         )
         db.record_event(conn, args.spec, "dependency_added", "cli", args.glob)
         db.save(conn, paths)
         print(f"{args.spec} now depends on {args.glob}")
@@ -613,21 +638,21 @@ def cmd_dep(args: argparse.Namespace) -> int:
             print("   ", glob)
         print(f"manual ({len(manual)}):")
         for glob in sorted(manual):
             print("   ", glob)
     return 0
 
 
 def build_parser() -> argparse.ArgumentParser:
     parser = argparse.ArgumentParser(
         prog="knowledge",
-        description="Author, track and publish a project's knowledge base.",
+        description="Author, track and publish a knowledge base.",
     )
     parser.add_argument("--version", action="version", version=VERSION)
     parser.set_defaults(handler=None)
     sub = parser.add_subparsers(dest="command")
 
     scan_p = sub.add_parser("scan", help="reconcile spec files against the database")
     scan_p.set_defaults(handler=cmd_scan)
 
     list_p = sub.add_parser("list", help="list specs")
     list_p.add_argument("--status", choices=["draft", "verified"])
@@ -733,25 +758,31 @@ def build_parser() -> argparse.ArgumentParser:
     pub_p.add_argument(
         "--out-dir",
         help="where to write pages when publish.target is 'directory'"
         " (overrides knowledge.toml's publish.out_dir)",
     )
     pub_p.set_defaults(handler=cmd_publish)
 
     return parser
 
 
-def main() -> int:
+def main_argv(argv: Sequence[str] | None = None) -> int:
+    """The testable half of the entry point: drives the parser and handler from an explicit
+    argv instead of sys.argv, so tests can call it directly instead of shelling out."""
     parser = build_parser()
-    args = parser.parse_args()
+    args = parser.parse_args(argv)
     if args.handler is None:
         parser.print_help()
         return 1
     try:
         return args.handler(args)
-    except RuntimeError as exc:
+    except (RuntimeError, ConfigError) as exc:
         print(f"error: {exc}", file=sys.stderr)
         return 1
 
 
+def main() -> int:
+    return main_argv()
+
+
 if __name__ == "__main__":
     raise SystemExit(main())
diff --git a/tests/test_cli_deps.py b/tests/test_cli_deps.py
index a5b1f60..f5cd390 100644
--- a/tests/test_cli_deps.py
+++ b/tests/test_cli_deps.py
@@ -90,20 +90,54 @@ def test_dep_add_without_a_glob_returns_a_usage_message(working, capsys):
     )) == []
 
 
 def test_dep_remove_without_a_glob_returns_a_usage_message(working, capsys):
     args = run(["dep", "remove", "assets"])
     assert args.handler(args) == 1
     out = capsys.readouterr().out
     assert "usage: knowledge dep remove" in out
 
 
+def test_dep_add_without_a_configured_code_repo_fails_clearly(repo, capsys, monkeypatch):
+    """`dep add` validates the glob against the code repository's tracked files, so unlike
+    `list`/`remove` it needs one configured. Guard it the same way `stale` is guarded rather
+    than letting the git call underneath run against a nonexistent path."""
+    monkeypatch.chdir(repo.root)
+    write_knowledge_toml(repo.root, code_repo="")
+    conn = db.connect(repo)
+    scan.scan(conn, repo)
+    db.save(conn, repo)
+
+    args = run(["dep", "add", "assets", "app/**/assets/page.tsx"])
+    assert args.handler(args) == 1
+    assert "no code repository configured" in capsys.readouterr().err
+
+    conn = db.connect(repo)
+    assert list(conn.execute(
+        "SELECT glob FROM spec_dependency WHERE spec_id='assets'"
+    )) == []
+
+
+def test_dep_list_works_without_a_configured_code_repo(repo, capsys, monkeypatch):
+    """`list` only reads the graph and the database — it must keep working even when
+    repo.code_repo is unset, unlike `add`."""
+    monkeypatch.chdir(repo.root)
+    write_knowledge_toml(repo.root, code_repo="")
+    conn = db.connect(repo)
+    scan.scan(conn, repo)
+    db.save(conn, repo)
+
+    args = run(["dep", "list", "assets"])
+    assert args.handler(args) == 0
+    assert "derived from the graph" in capsys.readouterr().out
+
+
 def test_stale_reports_verified_specs_with_no_dependencies(working, capsys):
     conn = db.connect(working)
     conn.execute(
         "UPDATE spec SET status='verified', verified_by='jesus',"
         " verified_at='2026-01-01T00:00:00Z' WHERE id='concepts'"
     )
     db.save(conn, working)
 
     args = run(["stale"])
     assert args.handler(args) == 0
diff --git a/tests/test_cli_read.py b/tests/test_cli_read.py
index 78a1bd7..396c8df 100644
--- a/tests/test_cli_read.py
+++ b/tests/test_cli_read.py
@@ -171,10 +171,33 @@ def test_contradictions_summary_accounts_for_skipped_checks(seeded, capsys):
     assert "no mechanical contradictions found" not in out
     assert "2 skipped" in out
 
 
 def test_contradictions_reports_a_functional_conflict(seeded, write_spec, capsys):
     write_spec(seeded.root, "duplicate-route",
                'app:Assets a ex:View ; ex:route "/somewhere-else" .\n')
     args = run(["contradictions", "--include-drafts"])
     args.handler(args)
     assert "route" in capsys.readouterr().out
+
+
+def test_stale_without_a_configured_code_repo_fails_clearly(repo, capsys, monkeypatch):
+    from knowledge import cli
+    (repo.root / "knowledge.toml").write_text(
+        (repo.root / "knowledge.toml").read_text(encoding="utf-8").replace(
+            'code_repo = "../code"', 'code_repo = ""'
+        ),
+        encoding="utf-8",
+    )
+    monkeypatch.chdir(repo.root)
+    assert cli.main_argv(["stale"]) == 1
+    assert "no code repository configured" in capsys.readouterr().err
+
+
+def test_the_parser_description_names_no_project(capsys):
+    from knowledge import cli
+    text = cli.build_parser().format_help()
+    assert "monicords" not in text.lower()
+    # A description that only avoids the string "monicords" would still pass for any other
+    # project's name substituted in — pin the exact generic text so this test can actually
+    # fail for the reason it exists.
+    assert "Author, track and publish a knowledge base." in text
```
