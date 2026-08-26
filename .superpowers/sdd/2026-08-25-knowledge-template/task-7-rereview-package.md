# Task 7 fix-round 2 scoped diff

FIX_BASE: 7169aed
HEAD: 7ab0b21

## Commits
```
7ab0b21 refactor: share one render-to-directory path between dry-run and the directory target
```

## Stat (should touch cli.py only)
```
 src/knowledge/cli.py | 51 ++++++++++++++++++++++++++++-----------------------
 1 file changed, 28 insertions(+), 23 deletions(-)
```

## Full diff (-U20)
```diff
diff --git a/src/knowledge/cli.py b/src/knowledge/cli.py
index 1361a4b..ff32c4b 100644
--- a/src/knowledge/cli.py
+++ b/src/knowledge/cli.py
@@ -1,37 +1,37 @@
 """The knowledge CLI.
 
 Every subcommand opens the repository, does one thing and returns an exit code. Mutating
 commands go through db.save so the tracked dump.sql is always current.
 """
 
 from __future__ import annotations
 
 import argparse
 import sqlite3
 import subprocess
 import sys
 from collections.abc import Sequence
 from pathlib import Path
 
 from knowledge import db, gitcmd, graph, scan
-from knowledge.config import Config, load_config
+from knowledge.config import Config, Sidebar, load_config
 from knowledge.paths import Paths, find_root, get_paths
 
 VERSION = "0.1.0"
 
 
 def open_repo(_args: argparse.Namespace) -> tuple[Paths, Config, sqlite3.Connection]:
     root = find_root()
     config = load_config(root)
     paths = get_paths(root, config.vocabulary.ontology_file)
     return paths, config, db.connect(paths)
 
 
 def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[tuple]:
     return list(conn.execute(sql, params))
 
 
 def _print_table(headers: list[str], rows: list[tuple]) -> None:
     if not rows:
         print("(nothing)")
         return
@@ -453,100 +453,105 @@ def cmd_stale(args: argparse.Namespace) -> int:
         print(f"\n{len(gaps)} verified spec(s) have no dependencies and cannot be checked:")
         print("   ", ", ".join(gaps))
         print('  Add one with: knowledge dep add <spec> "<glob>"')
     return 0
 
 
 def _clear_markdown(out_dir: Path) -> list[str]:
     """Unlink every top-level *.md in out_dir, returning what was removed.
 
     --dry-run and the real push must not diverge on this: the real path drops whatever the
     wiki currently has before writing fresh pages, which is how a dropped or renamed spec
     actually disappears from the wiki. Both call this same helper so a preview stays a
     faithful preview of the one irreversible step.
     """
     removed = sorted(p.name for p in out_dir.glob("*.md"))
     for stale in out_dir.glob("*.md"):
         stale.unlink()
     return removed
 
 
+def _render_to(conn, paths: Paths, out_dir: Path, sidebar: Sidebar, *, list_pages: bool) -> int:
+    """Render every published spec into out_dir, clearing pages that no longer have a spec.
+
+    Shared by --dry-run and the directory target: both render locally and push nothing, so
+    a difference between them could only ever be a bug — round 1 of this task's review found
+    exactly that, when the directory target was missing the clear-and-report half dry-run
+    already had. One implementation means there is nothing left to keep in sync by hand.
+    """
+    from knowledge import publish
+
+    out_dir.mkdir(parents=True, exist_ok=True)
+    existing = set(_clear_markdown(out_dir))
+    written = publish.write_pages(conn, paths, out_dir, sidebar)
+    print(f"{len(written)} page(s) written to {out_dir}")
+    if list_pages:
+        for name in sorted(written):
+            print("   ", name)
+    stale = sorted(existing - set(written))
+    if stale:
+        print(f"{len(stale)} stale page(s) removed: {', '.join(stale)}")
+    return 0
+
+
 def cmd_publish(args: argparse.Namespace) -> int:
     import shutil
     import tempfile
 
     paths, config, conn = open_repo(args)
     from knowledge import publish
 
     # --dry-run means "render locally, push nothing" — it is not a mode of publishing, it is
     # the thing you do *instead* of publishing. So it runs regardless of publish.target,
     # including "none": a fresh template user can preview what would be published before
     # they have decided (or configured) where it would go.
     if args.dry_run:
         out = Path(args.output) if args.output else paths.root / "build" / "wiki"
-        out.mkdir(parents=True, exist_ok=True)
-        existing = set(_clear_markdown(out))
-        written = publish.write_pages(conn, paths, out, config.publish.sidebar)
-        print(f"{len(written)} page(s) written to {out}")
-        for name in sorted(written):
-            print("   ", name)
-        stale = sorted(existing - set(written))
-        if stale:
-            print(f"{len(stale)} stale page(s) removed: {', '.join(stale)}")
-        return 0
+        return _render_to(conn, paths, out, config.publish.sidebar, list_pages=True)
 
     target = config.publish.target
     if target == "none":
         # "none" is the shipped default, and it guards only a real publish — --dry-run above
         # already handles the "just show me" case regardless of this. A freshly-templated
         # repository has no wiki, no publish directory — nothing this tooling could safely
         # guess — so it refuses to publish rather than picking a destination (e.g. assuming
         # github-wiki) that the project never asked for.
         print(
             "publishing is not configured — set publish.target in knowledge.toml"
             " to 'directory' or 'github-wiki'",
             file=sys.stderr,
         )
         return 1
     if target == "directory":
         # Emptiness is checked on the raw string, before it becomes a Path: Path("")
         # normalises to Path("."), whose str() is "." — truthy — so the same check made
         # after wrapping in Path could never fire.
         raw_out_dir = args.out_dir or config.publish.out_dir
         if not raw_out_dir:
             print(
                 "publish.out_dir is required when publish.target is 'directory'",
                 file=sys.stderr,
             )
             return 1
-        out_dir = Path(raw_out_dir)
-        out_dir.mkdir(parents=True, exist_ok=True)
-        # Same reason the dry-run and github-wiki paths both clear first: a directory publish
-        # is a standing output a reader opens later and trusts. A renamed or dropped spec has
-        # to actually lose its stale page, not leave one sitting there looking current.
-        existing = set(_clear_markdown(out_dir))
-        written = publish.write_pages(conn, paths, out_dir, config.publish.sidebar)
-        print(f"{len(written)} page(s) written to {out_dir}")
-        stale = sorted(existing - set(written))
-        if stale:
-            print(f"{len(stale)} stale page(s) removed: {', '.join(stale)}")
-        return 0
+        return _render_to(
+            conn, paths, Path(raw_out_dir), config.publish.sidebar, list_pages=False
+        )
 
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
```
