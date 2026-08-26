# Task 8 fix-round 1 scoped diff

FIX_BASE: d2d4c16
HEAD: e7f8443

## Commits
```
e7f8443 fix: drop the stale guard that duplicated deps.check's message verbatim
```

## Stat
```
 src/knowledge/cli.py   | 12 ------------
 tests/test_cli_read.py | 12 ++++++++++--
 2 files changed, 10 insertions(+), 14 deletions(-)
```

## Remaining no-code-repo guards in cli.py (expect: cmd_dep add only)
```
src/knowledge/cli.py:592:                "no code repository configured — set repo.code_repo in knowledge.toml,"
src/knowledge/deps.py:140:            "no code repository configured — set repo.code_repo in knowledge.toml,"
```

## Full diff (-U20)
```diff
diff --git a/src/knowledge/cli.py b/src/knowledge/cli.py
index d389bc0..9787c38 100644
--- a/src/knowledge/cli.py
+++ b/src/knowledge/cli.py
@@ -403,52 +403,40 @@ def cmd_verify(args: argparse.Namespace) -> int:
         lifecycle.verify(conn, paths, config, args.id, args.by, prune)
     except RuntimeError as exc:
         print(f"refused: {exc}")
         return 1
     except subprocess.CalledProcessError as exc:
         print(
             "error: git could not read the code repository's current commit — check "
             "the `code_repo` path in knowledge.toml. This is the day-one experience if "
             "the code repository is not checked out beside this one."
         )
         print(f"   {exc}")
         return 1
     db.save(conn, paths)
     print(f"{args.id} verified by {args.by}")
     return 0
 
 
 def cmd_stale(args: argparse.Namespace) -> int:
     paths, config, conn = open_repo(args)
     from knowledge import deps
-    # deps.check raises RuntimeError for the same condition, which main_argv would turn
-    # into an equivalent "error: ..." line — but that message is written for library
-    # callers, not this command's output. Guarding here means `stale` fails with its own
-    # clean, dedicated message before doing any of the git work, rather than borrowing
-    # deps.check's wording as a side effect of exception propagation.
-    if config.code_repo is None and not getattr(args, "code_repo", None):
-        print(
-            "no code repository configured — set repo.code_repo in knowledge.toml,"
-            " or pass --code-repo",
-            file=sys.stderr,
-        )
-        return 1
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
             "available."
         )
         print(f"   {exc}")
         return 1
 
     if not findings:
         print("nothing has gone stale")
     else:
         for spec_id, hits in findings:
             print(f"{spec_id}: {len(hits)} dependency change(s)")
diff --git a/tests/test_cli_read.py b/tests/test_cli_read.py
index 396c8df..4fccc85 100644
--- a/tests/test_cli_read.py
+++ b/tests/test_cli_read.py
@@ -163,41 +163,49 @@ def test_contradictions_summary_accounts_for_skipped_checks(seeded, capsys):
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
 
 
-def test_stale_without_a_configured_code_repo_fails_clearly(repo, capsys, monkeypatch):
+def test_stale_surfaces_deps_checks_missing_code_repo_error(repo, capsys, monkeypatch):
+    """cmd_stale has no guard of its own for this — deps.check raises RuntimeError when
+    neither config.code_repo nor --code-repo is set, and main_argv's except clause turns
+    that into the "error: ..." line asserted below. Delete deps.check's own
+    `if root is None: raise` and this fails (exit 0, "nothing has gone stale" instead),
+    which is what makes this test genuinely test that guard rather than duplicate one in
+    the CLI layer that would pass identically either way."""
     from knowledge import cli
     (repo.root / "knowledge.toml").write_text(
         (repo.root / "knowledge.toml").read_text(encoding="utf-8").replace(
             'code_repo = "../code"', 'code_repo = ""'
         ),
         encoding="utf-8",
     )
     monkeypatch.chdir(repo.root)
     assert cli.main_argv(["stale"]) == 1
-    assert "no code repository configured" in capsys.readouterr().err
+    err = capsys.readouterr().err
+    assert err.startswith("error: ")
+    assert "no code repository configured" in err
 
 
 def test_the_parser_description_names_no_project(capsys):
     from knowledge import cli
     text = cli.build_parser().format_help()
     assert "monicords" not in text.lower()
     # A description that only avoids the string "monicords" would still pass for any other
     # project's name substituted in — pin the exact generic text so this test can actually
     # fail for the reason it exists.
     assert "Author, track and publish a knowledge base." in text
```
