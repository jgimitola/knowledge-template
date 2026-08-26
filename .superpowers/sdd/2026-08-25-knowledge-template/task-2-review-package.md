# Task 2 review package

BASE: 2976990
HEAD: 901c7b8

## Commits
```
901c7b8 fix: ship working vocabulary defaults so the template loads before init
e341c15 feat: read the full project configuration from knowledge.toml
```

## Stat
```
 knowledge.toml            |  61 +++++++++++++++++-
 src/knowledge/cli.py      |  52 +++++++--------
 src/knowledge/config.py   | 157 +++++++++++++++++++++++++++++++++++++++++++---
 src/knowledge/vocab.py    |  79 +++++++++++++++++++++++
 tests/conftest.py         |  58 +++++++++++++++--
 tests/test_cli_deps.py    |   6 +-
 tests/test_cli_publish.py |   8 +--
 tests/test_cli_write.py   |   6 +-
 tests/test_config.py      | 110 ++++++++++++++++++++++++++++++++
 tests/test_deps.py        |  13 ++--
 tests/test_lifecycle.py   |   4 +-
 tests/test_paths.py       |   8 ---
 tests/test_round_trip.py  |   4 +-
 tests/test_vocab.py       |  43 +++++++++++++
 14 files changed, 533 insertions(+), 76 deletions(-)
```

## Full diff (-U10)
```diff
diff --git a/knowledge.toml b/knowledge.toml
index 825d395..be5737e 100644
--- a/knowledge.toml
+++ b/knowledge.toml
@@ -1,5 +1,60 @@
+# Written by `knowledge init`. Remove the [template] table to unlock a re-run.
+[template]
+unconfigured = true
+
+[project]
+name = "{{PROJECT_NAME}}"
+
+# namespace, instances and prefix are parsed, not just read — by load_config here, and by
+# rdflib's Turtle parser for the ontology file's own @prefix line. A token would break both
+# before `init` ever ran, so these three ship as working defaults and `init` rewrites them in
+# place. The [template] table above is what actually marks the repository unconfigured.
+[vocabulary]
+ontology_file   = "ontology.ttl"
+namespace       = "https://example.com/ontology#"
+instances       = "https://example.com/id/"
+prefix          = "ex"
+instance_prefix = "app"
+
+# Terms the mechanical checks need to know about. An empty value disables its check,
+# and `validate` reports it as skipped rather than passed.
+rule_class                 = "Rule"
+concept_class              = ""
+concept_spec               = "concepts"
+field_class                = ""
+field_name_pattern         = ""
+underscore_reserved        = false
+functional_properties      = []
+verbatim_string_properties = []
+
+# The `ask` presets. Each becomes one named survey.
+[[ask]]
+name  = "everything with a label"
+query = "SELECT ?s ?l WHERE { ?s rdfs:label ?l } ORDER BY ?l"
+
 [repo]
-code_repo = ""
+code_repo = "{{CODE_REPO}}"     # empty disables `stale` and `dep`
+
+[dependencies]
+route_property      = ""
+endpoint_property   = ""
+route_glob          = ""
+endpoint_glob       = ""
+absorbed_prefixes   = []
+dynamic_segment     = "{...}"
+dynamic_replacement = "*"
+
+[publish]
+target  = "none"                # "none" | "directory" | "github-wiki"
+remote  = ""
+out_dir = ""
+committer_name  = "github-actions[bot]"
+committer_email = "41898282+github-actions[bot]@users.noreply.github.com"
 
-[wiki]
-remote = ""
+[publish.sidebar]
+title         = "{{PROJECT_NAME}}"
+order         = []              # anything unlisted is appended alphabetically
+reference     = []
+nested_under  = {}
+header_before = {}
+labels        = {}
diff --git a/src/knowledge/cli.py b/src/knowledge/cli.py
index 06c1868..223ce98 100644
--- a/src/knowledge/cli.py
+++ b/src/knowledge/cli.py
@@ -7,29 +7,29 @@ commands go through db.save so the tracked dump.sql is always current.
 from __future__ import annotations
 
 import argparse
 import sqlite3
 import subprocess
 import sys
 from collections.abc import Sequence
 from pathlib import Path
 
 from knowledge import db, gitcmd, graph, scan
-from knowledge.config import load_config
+from knowledge.config import Config, load_config
 from knowledge.paths import Paths, get_paths
 
 VERSION = "0.1.0"
 
 
-def open_repo(_args: argparse.Namespace) -> tuple[Paths, sqlite3.Connection]:
+def open_repo(_args: argparse.Namespace) -> tuple[Paths, Config, sqlite3.Connection]:
     paths = get_paths()
-    return paths, db.connect(paths)
+    return paths, load_config(paths.root), db.connect(paths)
 
 
 def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[tuple]:
     return list(conn.execute(sql, params))
 
 
 def _print_table(headers: list[str], rows: list[tuple]) -> None:
     if not rows:
         print("(nothing)")
         return
@@ -38,38 +38,38 @@ def _print_table(headers: list[str], rows: list[tuple]) -> None:
         for i in range(len(headers))
     ]
     line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
     print(line)
     print("  ".join("-" * w for w in widths))
     for row in rows:
         print("  ".join(str(value).ljust(widths[i]) for i, value in enumerate(row)))
 
 
 def cmd_scan(args: argparse.Namespace) -> int:
-    paths, conn = open_repo(args)
+    paths, _config, conn = open_repo(args)
     report = scan.scan(conn, paths)
     print(f"added {len(report.added)}, moved {len(report.moved)}, "
           f"unchanged {len(report.unchanged)}, missing {len(report.missing)}, "
           f"demoted {len(report.demoted)}")
     for spec_id in report.added:
         print("  + ", spec_id)
     for spec_id, old, new in report.moved:
         print("  ~ ", f"{spec_id}: {old} -> {new}")
     for spec_id in report.demoted:
         print("  v ", f"{spec_id}: content changed since it was last modeled")
     for spec_id in report.missing:
         print("  ! ", f"{spec_id} has a row but no files")
     return 1 if report.missing else 0
 
 
 def cmd_list(args: argparse.Namespace) -> int:
-    paths, conn = open_repo(args)
+    paths, _config, conn = open_repo(args)
     where: list[str] = []
     params: list[str] = []
     if args.status:
         where.append("status = ?")
         params.append(args.status)
     if args.confidence:
         where.append("confidence = ?")
         params.append(args.confidence)
     if args.unmodeled:
         version = paths.ontology_version.read_text(encoding="utf-8").strip()
@@ -98,21 +98,21 @@ def cmd_list(args: argparse.Namespace) -> int:
         "SELECT id, status, COALESCE(confidence,'-'), COALESCE(verified_by,'-'),"
         f" COALESCE(modeled_at,'-') FROM spec{clause} ORDER BY id",
         tuple(params),
     )
     _print_table(["id", "status", "confidence", "verified by", "modeled at"], rows)
     print(f"\n{len(rows)} spec(s)")
     return 0
 
 
 def cmd_show(args: argparse.Namespace) -> int:
-    _, conn = open_repo(args)
+    _, _config, conn = open_repo(args)
     rows = _rows(conn, "SELECT * FROM spec WHERE id = ?", (args.id,))
     if not rows:
         print(f"no spec with id {args.id!r}")
         return 1
     columns = [d[0] for d in conn.execute("SELECT * FROM spec LIMIT 0").description]
     for name, value in zip(columns, rows[0], strict=True):
         print(f"{name:24} {value if value is not None else '-'}")
 
     questions = _rows(
         conn,
@@ -132,21 +132,21 @@ def cmd_show(args: argparse.Namespace) -> int:
         " WHERE spec_id = ? ORDER BY id",
         (args.id,),
     )
     print(f"\nhistory ({len(events)}):")
     for at, event, actor, detail in events:
         print(f"  {at}  {event:18} {actor:10} {detail}")
     return 0
 
 
 def cmd_questions(args: argparse.Namespace) -> int:
-    _, conn = open_repo(args)
+    _, _config, conn = open_repo(args)
     where: list[str] = []
     params: list[str] = []
     if args.spec:
         where.append("spec_id = ?")
         params.append(args.spec)
     if args.claim:
         where.append("claim_iri = ?")
         params.append(args.claim)
     if args.open:
         where.append("status = 'open'")
@@ -179,21 +179,21 @@ def _check(name: str, items: Sequence[str], ok_message: str, strict: bool) -> bo
     if not items:
         print(ok_message)
         return False
     print(f"\n{len(items)} {name}:")
     for item in items:
         print("  -", item)
     return strict
 
 
 def cmd_validate(args: argparse.Namespace) -> int:
-    paths, _ = open_repo(args)
+    paths, _config, _ = open_repo(args)
     from knowledge import lint
     ids = graph.spec_ids(paths)
     print(f"{len(ids)} spec(s)")
     try:
         g = graph.load_graph(paths, ids)
     except Exception as exc:  # noqa: BLE001 - the parser's message is the useful part
         print(f"\nPARSE FAILED: {exc}")
         return 1
     print(f"parsed OK: {len(g)} triples")
 
@@ -218,65 +218,65 @@ def cmd_validate(args: argparse.Namespace) -> int:
                lint.domain_range_violations(g),
                "every predicate stays inside its declared domain and range", strict),
         _check("empty-state string(s) no prose states",
                lint.ungrounded_empty_states(paths, ids),
                "every empty state appears in its spec's prose", strict),
     ]
     return 1 if any(failures) else 0
 
 
 def cmd_graph(args: argparse.Namespace) -> int:
-    paths, conn = open_repo(args)
+    paths, _config, conn = open_repo(args)
     ids = _selected_ids(conn, paths, args.include_drafts)
     g = graph.load_graph(paths, ids)
     output = Path(args.output)
     output.write_text(g.serialize(format="turtle"), encoding="utf-8", newline="\n")
     print(f"{len(g)} triples from {len(ids)} spec(s) written to {output}")
     return 0
 
 
 def cmd_query(args: argparse.Namespace) -> int:
-    paths, conn = open_repo(args)
+    paths, _config, conn = open_repo(args)
     g = graph.load_graph(paths, _selected_ids(conn, paths, args.include_drafts))
     rows = graph.run_query(g, args.sparql)
     print(f"{len(rows)} result(s)")
     for row in rows:
         print("   ", "  ".join(row))
     return 0
 
 
 def cmd_describe(args: argparse.Namespace) -> int:
-    paths, _ = open_repo(args)
+    paths, _config, _ = open_repo(args)
     g = graph.load_graph(paths)
     term = args.term if ":" in args.term else f"app:{args.term}"
     print(f"--- {term} as subject ---")
     for row in graph.run_query(g, f"SELECT ?p ?o WHERE {{ {term} ?p ?o }}"):
         print("   ", "  ".join(row))
     print(f"\n--- {term} as object ---")
     for row in graph.run_query(g, f"SELECT ?s ?p WHERE {{ ?s ?p {term} }}"):
         print("   ", "  ".join(row))
     return 0
 
 
 def cmd_ask(args: argparse.Namespace) -> int:
-    paths, conn = open_repo(args)
+    paths, _config, conn = open_repo(args)
     g = graph.load_graph(paths, _selected_ids(conn, paths, args.include_drafts))
     for title, sparql in graph.SANITY_QUERIES.items():
         rows = graph.run_query(g, sparql)
         print(f"\n{title} - {len(rows)} result(s)")
         for row in rows:
             print("   ", "  ".join(row))
     return 0
 
 
 def cmd_contradictions(args: argparse.Namespace) -> int:
-    paths, conn = open_repo(args)
+    paths, _config, conn = open_repo(args)
     from knowledge import contradictions, lint
     ids = _selected_ids(conn, paths, args.include_drafts)
     g = graph.load_graph(paths, ids)
     found = False
 
     conflicts = contradictions.functional_conflicts(g)
     if conflicts:
         found = True
         print(f"{len(conflicts)} functional-property conflict(s):")
         for subject, prop, values in conflicts:
@@ -295,80 +295,79 @@ def cmd_contradictions(args: argparse.Namespace) -> int:
         print(f"\n{len(redeclared)} concept(s) redeclared locally instead of referenced:")
         for msg in redeclared:
             print("  -", msg)
 
     if not found:
         print("no mechanical contradictions found")
     return 0
 
 
 def cmd_new(args: argparse.Namespace) -> int:
-    paths, conn = open_repo(args)
+    paths, _config, conn = open_repo(args)
     from knowledge import lifecycle
     md = lifecycle.new_spec(paths, args.id, args.title or args.id.replace("-", " ").title())
     scan.scan(conn, paths)
     print(f"created {md}")
     return 0
 
 
 def cmd_model(args: argparse.Namespace) -> int:
-    paths, conn = open_repo(args)
+    paths, _config, conn = open_repo(args)
     from knowledge import lifecycle
     version = paths.ontology_version.read_text(encoding="utf-8").strip()
     try:
         lifecycle.mark_modeled(conn, paths, args.id, args.by, version)
     except RuntimeError as exc:
         print(f"refused: {exc}")
         return 1
     db.save(conn, paths)
     print(f"{args.id} modeled by {args.by} against ontology {version}")
     return 0
 
 
 def cmd_forget(args: argparse.Namespace) -> int:
-    paths, conn = open_repo(args)
+    paths, _config, conn = open_repo(args)
     from knowledge import lifecycle
     try:
         lifecycle.forget(conn, paths, args.id, args.by)
     except RuntimeError as exc:
         print(f"refused: {exc}")
         return 1
     db.save(conn, paths)
     print(f"forgot {args.id}")
     return 0
 
 
 def cmd_ask_question(args: argparse.Namespace) -> int:
-    paths, conn = open_repo(args)
+    paths, _config, conn = open_repo(args)
     from knowledge import lifecycle
     if not list(conn.execute("SELECT 1 FROM spec WHERE id = ?", (args.spec,))):
         print(f"refused: no spec with id {args.spec!r}")
         return 1
     qid = lifecycle.open_question(conn, args.spec, args.question, args.by, args.claim)
     db.save(conn, paths)
     print(f"opened question #{qid} on {args.spec}")
     return 0
 
 
 def cmd_answer(args: argparse.Namespace) -> int:
-    paths, conn = open_repo(args)
+    paths, _config, conn = open_repo(args)
     from knowledge import lifecycle
     lifecycle.answer_question(conn, args.question_id, args.answer, args.by)
     db.save(conn, paths)
     print(f"answered #{args.question_id}")
     return 0
 
 
 def cmd_verify(args: argparse.Namespace) -> int:
-    paths, conn = open_repo(args)
+    paths, config, conn = open_repo(args)
     from knowledge import lifecycle
-    config = load_config(paths.root)
     try:
         prune = [(int(qid), reason) for qid, reason in (args.prune or [])]
     except ValueError:
         print("refused: --prune takes a numeric question id, e.g. --prune 7 \"reason\"")
         return 1
     try:
         lifecycle.verify(conn, paths, config, args.id, args.by, prune)
     except RuntimeError as exc:
         print(f"refused: {exc}")
         return 1
@@ -379,23 +378,22 @@ def cmd_verify(args: argparse.Namespace) -> int:
             "the code repository is not checked out beside this one."
         )
         print(f"   {exc}")
         return 1
     db.save(conn, paths)
     print(f"{args.id} verified by {args.by}")
     return 0
 
 
 def cmd_stale(args: argparse.Namespace) -> int:
-    paths, conn = open_repo(args)
+    paths, config, conn = open_repo(args)
     from knowledge import deps
-    config = load_config(paths.root)
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
@@ -436,89 +434,87 @@ def _clear_markdown(out_dir: Path) -> list[str]:
     removed = sorted(p.name for p in out_dir.glob("*.md"))
     for stale in out_dir.glob("*.md"):
         stale.unlink()
     return removed
 
 
 def cmd_publish(args: argparse.Namespace) -> int:
     import shutil
     import tempfile
 
-    paths, conn = open_repo(args)
+    paths, config, conn = open_repo(args)
     from knowledge import publish
-    config = load_config(paths.root)
 
     if args.dry_run:
         out = Path(args.output) if args.output else paths.root / "build" / "wiki"
         out.mkdir(parents=True, exist_ok=True)
         existing = set(_clear_markdown(out))
         written = publish.write_pages(conn, paths, out)
         print(f"{len(written)} page(s) written to {out}")
         for name in sorted(written):
             print("   ", name)
         stale = sorted(existing - set(written))
         if stale:
             print(f"{len(stale)} stale page(s) removed: {', '.join(stale)}")
         return 0
 
     workdir = Path(tempfile.mkdtemp(prefix="knowledge-wiki-"))
     try:
         clone = workdir / "wiki"
         try:
             gitcmd.run(
-                ["clone", config.wiki_remote, str(clone)],
+                ["clone", config.publish.remote, str(clone)],
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
         written = publish.write_pages(conn, paths, clone)
         try:
             pushed = publish.push(
-                clone, config.wiki_remote, f"docs: sync {len(written)} page(s)"
+                clone, config.publish.remote, f"docs: sync {len(written)} page(s)"
             )
         except subprocess.CalledProcessError as exc:
             print("error: could not push to the wiki repository")
             print(f"   {exc.stderr.strip()}")
             return 1
         print(f"{len(written)} page(s) {'pushed' if pushed else 'already current'}")
     finally:
         shutil.rmtree(workdir, ignore_errors=True)
     return 0
 
 
 def cmd_dep(args: argparse.Namespace) -> int:
-    paths, conn = open_repo(args)
+    paths, config, conn = open_repo(args)
     from knowledge import deps
     if args.action in ("add", "remove") and not args.glob:
         print(f'usage: knowledge dep {args.action} <spec> "<glob>"')
         return 1
     if args.action == "add":
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
-        config = load_config(paths.root)
         try:
             tracked = deps.tracked_files(config.code_repo)
         except subprocess.CalledProcessError as exc:
             print(f"  warning: could not check the code repository ({exc})")
         else:
             if not deps.matches({args.glob}, tracked):
                 print("  warning: this glob matches no file in the code repository today")
     elif args.action == "remove":
         conn.execute(
             "DELETE FROM spec_dependency WHERE spec_id = ? AND glob = ?", (args.spec, args.glob)
diff --git a/src/knowledge/config.py b/src/knowledge/config.py
index 99eaa4b..7fd07d3 100644
--- a/src/knowledge/config.py
+++ b/src/knowledge/config.py
@@ -1,26 +1,167 @@
-"""knowledge.toml — the paths and remotes this repository needs to reach outside itself.
+"""knowledge.toml — every value that is about this project rather than about the tooling.
 
-Editor settings grant permission to read the code repository; this supplies its location,
-so the staleness check does not depend on how the editor was launched.
+The namespaces, the terms the mechanical checks are about, the preset surveys, where the
+code repository lives, how a route becomes a file glob, and where pages publish to. None of
+it is hardcoded, so the same tooling serves a knowledge base about anything.
 """
 
 from __future__ import annotations
 
+import re
 import tomllib
-from dataclasses import dataclass
+from dataclasses import dataclass, field
 from pathlib import Path
 
+from knowledge.vocab import Checks, Vocabulary
+
+PLACEHOLDER = re.compile(r"^\{\{[A-Z_]+\}\}$")
+TARGETS = ("none", "directory", "github-wiki")
+
+
+class ConfigError(RuntimeError):
+    """knowledge.toml is missing a required key, or holds a value it cannot hold."""
+
+
+@dataclass(frozen=True)
+class Survey:
+    name: str
+    query: str
+
+
+@dataclass(frozen=True)
+class Dependencies:
+    route_property: str = ""
+    endpoint_property: str = ""
+    route_glob: str = ""
+    endpoint_glob: str = ""
+    absorbed_prefixes: tuple[str, ...] = ()
+    dynamic_segment: str = "{...}"
+    dynamic_replacement: str = "*"
+
+    @property
+    def derives(self) -> bool:
+        """Whether any glob can be derived from the graph at all. False leaves manual
+        globs as the only dependency source, which is the shipped default."""
+        return bool(self.route_property and self.route_glob) or bool(
+            self.endpoint_property and self.endpoint_glob
+        )
+
+
+@dataclass(frozen=True)
+class Sidebar:
+    title: str = ""
+    order: tuple[str, ...] = ()
+    reference: tuple[str, ...] = ()
+    nested_under: dict[str, str] = field(default_factory=dict)
+    header_before: dict[str, str] = field(default_factory=dict)
+    labels: dict[str, str] = field(default_factory=dict)
+
+
+@dataclass(frozen=True)
+class Publish:
+    target: str = "none"
+    remote: str = ""
+    out_dir: str = ""
+    committer_name: str = "github-actions[bot]"
+    committer_email: str = "41898282+github-actions[bot]@users.noreply.github.com"
+    sidebar: Sidebar = field(default_factory=Sidebar)
+
 
 @dataclass(frozen=True)
 class Config:
-    code_repo: Path
-    wiki_remote: str
+    project_name: str
+    vocabulary: Vocabulary
+    surveys: tuple[Survey, ...]
+    code_repo: Path | None
+    dependencies: Dependencies
+    publish: Publish
+    unconfigured: bool
+
+
+def _clean(value) -> str:
+    """An unsubstituted {{PLACEHOLDER}} reads as empty, so the shipped template loads."""
+    text = str(value or "")
+    return "" if PLACEHOLDER.match(text) else text
+
+
+def _required(table: dict, section: str, key: str) -> str:
+    value = _clean(table.get(key))
+    if not value:
+        raise ConfigError(f"knowledge.toml: {section}.{key} is required")
+    return value
+
+
+def _vocabulary(data: dict) -> Vocabulary:
+    table = data.get("vocabulary", {})
+    checks = Checks(
+        rule_class=_clean(table.get("rule_class")),
+        concept_class=_clean(table.get("concept_class")),
+        concept_spec=_clean(table.get("concept_spec")),
+        field_class=_clean(table.get("field_class")),
+        field_name_pattern=_clean(table.get("field_name_pattern")),
+        underscore_reserved=bool(table.get("underscore_reserved", False)),
+        functional_properties=tuple(table.get("functional_properties", ())),
+        verbatim_string_properties=tuple(table.get("verbatim_string_properties", ())),
+    )
+    return Vocabulary(
+        ontology_file=_clean(table.get("ontology_file")) or "ontology.ttl",
+        namespace=_required(table, "vocabulary", "namespace"),
+        instances=_required(table, "vocabulary", "instances"),
+        prefix=_required(table, "vocabulary", "prefix"),
+        instance_prefix=_clean(table.get("instance_prefix")) or "app",
+        checks=checks,
+    )
+
+
+def _publish(data: dict) -> Publish:
+    table = data.get("publish", {})
+    target = _clean(table.get("target")) or "none"
+    if target not in TARGETS:
+        raise ConfigError(
+            f"knowledge.toml: publish.target is {target!r}; expected one of {', '.join(TARGETS)}"
+        )
+    bar = table.get("sidebar", {})
+    return Publish(
+        target=target,
+        remote=_clean(table.get("remote")),
+        out_dir=_clean(table.get("out_dir")),
+        committer_name=_clean(table.get("committer_name")) or Publish.committer_name,
+        committer_email=_clean(table.get("committer_email")) or Publish.committer_email,
+        sidebar=Sidebar(
+            title=_clean(bar.get("title")),
+            order=tuple(bar.get("order", ())),
+            reference=tuple(bar.get("reference", ())),
+            nested_under=dict(bar.get("nested_under", {})),
+            header_before=dict(bar.get("header_before", {})),
+            labels=dict(bar.get("labels", {})),
+        ),
+    )
 
 
 def load_config(root: Path) -> Config:
     with (root / "knowledge.toml").open("rb") as handle:
         data = tomllib.load(handle)
+
+    code_repo = _clean(data.get("repo", {}).get("code_repo"))
+    deps = data.get("dependencies", {})
+
     return Config(
-        code_repo=(root / data["repo"]["code_repo"]).resolve(),
-        wiki_remote=data["wiki"]["remote"],
+        project_name=_clean(data.get("project", {}).get("name")),
+        vocabulary=_vocabulary(data),
+        surveys=tuple(
+            Survey(name=_clean(row.get("name")), query=_clean(row.get("query")))
+            for row in data.get("ask", ())
+        ),
+        code_repo=(root / code_repo).resolve() if code_repo else None,
+        dependencies=Dependencies(
+            route_property=_clean(deps.get("route_property")),
+            endpoint_property=_clean(deps.get("endpoint_property")),
+            route_glob=_clean(deps.get("route_glob")),
+            endpoint_glob=_clean(deps.get("endpoint_glob")),
+            absorbed_prefixes=tuple(deps.get("absorbed_prefixes", ())),
+            dynamic_segment=_clean(deps.get("dynamic_segment")) or "{...}",
+            dynamic_replacement=_clean(deps.get("dynamic_replacement")) or "*",
+        ),
+        publish=_publish(data),
+        unconfigured=bool(data.get("template", {}).get("unconfigured", False)),
     )
diff --git a/src/knowledge/vocab.py b/src/knowledge/vocab.py
new file mode 100644
index 0000000..e2fe9cf
--- /dev/null
+++ b/src/knowledge/vocab.py
@@ -0,0 +1,79 @@
+"""The project's vocabulary, as configuration rather than as constants.
+
+Every namespace, prefix and check-term the tooling needs is here, so a knowledge base can
+declare whatever vocabulary its domain calls for and the mechanical checks still know which
+of its terms they are about.
+"""
+
+from __future__ import annotations
+
+from dataclasses import dataclass, field
+
+from rdflib import URIRef
+
+# Standard vocabularies every knowledge base gets for free. Not configurable: a project
+# that redefines rdfs: is not a project this tooling can help.
+FIXED_PREFIXES = {
+    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
+    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
+    "xsd": "http://www.w3.org/2001/XMLSchema#",
+    "skos": "http://www.w3.org/2004/02/skos/core#",
+    "dcterms": "http://purl.org/dc/terms/",
+}
+
+
+@dataclass(frozen=True)
+class Checks:
+    """Which of the project's own terms each configurable check is about.
+
+    An empty value disables its check. The check then returns None rather than an empty
+    list, so a caller can print "skipped" instead of a pass nobody earned.
+    """
+
+    rule_class: str = ""
+    concept_class: str = ""
+    concept_spec: str = ""
+    field_class: str = ""
+    field_name_pattern: str = ""
+    underscore_reserved: bool = False
+    functional_properties: tuple[str, ...] = ()
+    verbatim_string_properties: tuple[str, ...] = ()
+
+
+@dataclass(frozen=True)
+class Vocabulary:
+    ontology_file: str
+    namespace: str
+    instances: str
+    prefix: str
+    instance_prefix: str
+    checks: Checks = field(default_factory=Checks)
+
+    def term(self, local: str) -> URIRef:
+        return URIRef(self.namespace + local)
+
+    def instance(self, local: str) -> URIRef:
+        return URIRef(self.instances + local)
+
+    def is_term(self, iri) -> bool:
+        return str(iri).startswith(self.namespace)
+
+    def is_instance(self, iri) -> bool:
+        return str(iri).startswith(self.instances)
+
+    def qname(self, iri) -> str:
+        text = str(iri)
+        if text.startswith(self.namespace):
+            return f"{self.prefix}:{text[len(self.namespace):]}"
+        if text.startswith(self.instances):
+            return f"{self.instance_prefix}:{text[len(self.instances):]}"
+        return text
+
+    @property
+    def sparql_prefixes(self) -> str:
+        lines = [
+            f"PREFIX {self.prefix}: <{self.namespace}>",
+            f"PREFIX {self.instance_prefix}: <{self.instances}>",
+        ]
+        lines += [f"PREFIX {name}: <{iri}>" for name, iri in FIXED_PREFIXES.items()]
+        return "\n".join(lines) + "\n"
diff --git a/tests/conftest.py b/tests/conftest.py
index f856760..5b8a159 100644
--- a/tests/conftest.py
+++ b/tests/conftest.py
@@ -1,16 +1,18 @@
 import os
 
 import pytest
 
 from knowledge import gitcmd
 from knowledge import paths as paths_mod
+from knowledge.config import Config, Dependencies, Publish
+from knowledge.vocab import Checks, Vocabulary
 
 
 @pytest.fixture(autouse=True)
 def isolate_git_env(monkeypatch):
     """No test inherits the caller's repository.
 
     git exports GIT_DIR to every hook it runs — a linked worktree's gitdir, absolutely
     pathed — and hands GIT_INDEX_FILE and the GIT_AUTHOR_*/GIT_COMMITTER_* identity to
     commit hooks and rebases on top of that. Subprocesses inherit all of it, and GIT_DIR
     outranks `-C <path>`, so a fixture building a throwaway repository in tmp_path would
@@ -85,27 +87,75 @@ def write_spec(root, spec_id, ttl, prose="Some prose.\n"):
     directory = root / "specs" / spec_id
     directory.mkdir(parents=True, exist_ok=True)
     (directory / "spec.md").write_text(
         f"---\nid: {spec_id}\n---\n\n# {spec_id.replace('-', ' ').title()}\n\n{prose}",
         encoding="utf-8",
     )
     (directory / "spec.ttl").write_text(ttl, encoding="utf-8")
     return directory
 
 
+# knowledge.toml now requires a full [vocabulary] table (Task 2). These stay the monicords
+# namespaces on purpose — graph.py still has MON as a module constant at this point, so a
+# fixture using different namespaces would break every test that parses ONTOLOGY/ASSETS_TTL
+# above. Task 3 rewrites the fixture and the constant together.
+KNOWLEDGE_TOML = """\
+[project]
+name = "Monicords"
+
+[vocabulary]
+ontology_file = "monicords.ttl"
+namespace = "https://monicords.com/ontology#"
+instances = "https://monicords.com/id/"
+prefix = "mon"
+instance_prefix = "app"
+
+[repo]
+code_repo = "{code_repo}"
+
+[publish]
+remote = "{remote}"
+"""
+
+
+def write_knowledge_toml(root, *, code_repo="../code", remote="https://example.com/x.wiki.git"):
+    (root / "knowledge.toml").write_text(
+        KNOWLEDGE_TOML.format(code_repo=code_repo, remote=remote), encoding="utf-8"
+    )
+    return root
+
+
+def make_config(code_repo, remote="https://example.com/x.wiki.git"):
+    """A Config for tests that exercise lifecycle/deps functions directly, without going
+    through load_config. Same monicords vocabulary as KNOWLEDGE_TOML above."""
+    return Config(
+        project_name="Monicords",
+        vocabulary=Vocabulary(
+            ontology_file="monicords.ttl",
+            namespace="https://monicords.com/ontology#",
+            instances="https://monicords.com/id/",
+            prefix="mon",
+            instance_prefix="app",
+            checks=Checks(),
+        ),
+        surveys=(),
+        code_repo=code_repo,
+        dependencies=Dependencies(),
+        publish=Publish(remote=remote),
+        unconfigured=False,
+    )
+
+
 @pytest.fixture
 def repo(tmp_path):
     """A knowledge repository with an ontology and two specs."""
-    (tmp_path / "knowledge.toml").write_text(
-        '[repo]\ncode_repo = "../code"\n\n[wiki]\nremote = "https://example.com/x.wiki.git"\n',
-        encoding="utf-8",
-    )
+    write_knowledge_toml(tmp_path)
     ontology = tmp_path / "ontology"
     ontology.mkdir()
     (ontology / "monicords.ttl").write_text(ONTOLOGY, encoding="utf-8")
     (ontology / "README.md").write_text("# Ontology\n\nThe vocabulary.\n", encoding="utf-8")
     (ontology / "VERSION").write_text("1.0.0\n", encoding="utf-8")
     (tmp_path / ".metadata").mkdir()
 
     write_spec(tmp_path, "assets", ASSETS_TTL, "The Assets screen. See [Concepts](Concepts).\n")
     write_spec(tmp_path, "concepts", CONCEPTS_TTL)
     return paths_mod.get_paths(tmp_path)
diff --git a/tests/test_cli_deps.py b/tests/test_cli_deps.py
index 445ba37..a5b1f60 100644
--- a/tests/test_cli_deps.py
+++ b/tests/test_cli_deps.py
@@ -1,40 +1,38 @@
 import subprocess
 
 import pytest
 
 from knowledge import cli, db, lifecycle, scan
 from knowledge.config import load_config
+from tests.conftest import write_knowledge_toml
 
 
 def _init_code_repo(root):
     root.mkdir(parents=True, exist_ok=True)
     subprocess.run(["git", "init", "-b", "main", str(root)], check=True, capture_output=True)
     subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t"], check=True)
     subprocess.run(["git", "-C", str(root), "config", "user.name", "T"], check=True)
     (root / "app" / "platform" / "(menuLayout)" / "assets").mkdir(parents=True)
     (root / "app" / "platform" / "(menuLayout)" / "assets" / "page.tsx").write_text("x\n")
     subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
     subprocess.run(["git", "-C", str(root), "commit", "-m", "init"], check=True,
                    capture_output=True)
 
 
 @pytest.fixture
 def working(repo, monkeypatch):
     """The shared `repo` fixture's knowledge.toml points code_repo at "../code" — a
     sibling of tmp_path that would collide with every other test sharing the same pytest
     basetemp. Point it at a real git repo living inside tmp_path instead."""
     monkeypatch.chdir(repo.root)
-    (repo.root / "knowledge.toml").write_text(
-        '[repo]\ncode_repo = "code"\n\n[wiki]\nremote = "https://example.com/x.wiki.git"\n',
-        encoding="utf-8",
-    )
+    write_knowledge_toml(repo.root, code_repo="code")
     _init_code_repo(repo.root / "code")
     conn = db.connect(repo)
     scan.scan(conn, repo)
     db.save(conn, repo)
     return repo
 
 
 def run(argv):
     return cli.build_parser().parse_args(argv)
 
diff --git a/tests/test_cli_publish.py b/tests/test_cli_publish.py
index 55b3b67..2f79b21 100644
--- a/tests/test_cli_publish.py
+++ b/tests/test_cli_publish.py
@@ -1,13 +1,14 @@
 import pytest
 
 from knowledge import cli, db, scan
+from tests.conftest import write_knowledge_toml
 
 
 @pytest.fixture
 def working(repo, monkeypatch):
     monkeypatch.chdir(repo.root)
     conn = db.connect(repo)
     scan.scan(conn, repo)
     db.save(conn, repo)
     return repo
 
@@ -15,26 +16,21 @@ def working(repo, monkeypatch):
 def run(argv):
     return cli.build_parser().parse_args(argv)
 
 
 def test_publish_reports_a_clone_failure_cleanly_instead_of_a_traceback(working, capsys):
     """The wiki remote does not exist (a plain nonexistent local path stands in for an
     unreachable or not-yet-created GitHub wiki, so this stays offline and deterministic).
     cmd_publish must catch CalledProcessError itself rather than let it escape as a
     traceback — main() only catches RuntimeError."""
     bogus_remote = working.root / "no-such-wiki"
-    (working.root / "knowledge.toml").write_text(
-        '[repo]\ncode_repo = "../code"\n\n[wiki]\nremote = "'
-        + bogus_remote.as_posix()
-        + '"\n',
-        encoding="utf-8",
-    )
+    write_knowledge_toml(working.root, remote=bogus_remote.as_posix())
 
     args = run(["publish"])
     exit_code = args.handler(args)
 
     assert exit_code == 1
     out = capsys.readouterr().out
     assert "error:" in out
     assert "could not clone" in out
     assert "web UI" in out  # the uninitialised-wiki hint
 
diff --git a/tests/test_cli_write.py b/tests/test_cli_write.py
index 0cd25d3..e71f0b5 100644
--- a/tests/test_cli_write.py
+++ b/tests/test_cli_write.py
@@ -1,13 +1,14 @@
 import pytest
 
 from knowledge import cli, db, lifecycle, scan
+from tests.conftest import write_knowledge_toml
 
 
 @pytest.fixture
 def working(repo, monkeypatch):
     monkeypatch.chdir(repo.root)
     conn = db.connect(repo)
     scan.scan(conn, repo)
     db.save(conn, repo)
     return repo
 
@@ -210,21 +211,18 @@ def test_ask_question_with_an_unknown_spec_refuses_cleanly(working, capsys):
     assert list(conn.execute("SELECT * FROM open_question WHERE spec_id='nope'")) == []
 
 
 def test_verify_with_no_code_repository_refuses_cleanly(working, capsys):
     """The day-one experience for anyone who clones this repo alone: knowledge.toml's
     code_repo does not exist yet, so `git rev-parse HEAD` fails inside it."""
     conn = db.connect(working)
     lifecycle.mark_modeled(conn, working, "assets", by="writer", ontology_version="1.0.0")
     db.save(conn, working)
 
-    (working.root / "knowledge.toml").write_text(
-        '[repo]\ncode_repo = "does-not-exist"\n\n[wiki]\nremote = "https://example.com/x.wiki.git"\n',
-        encoding="utf-8",
-    )
+    write_knowledge_toml(working.root, code_repo="does-not-exist")
 
     args = run(["verify", "assets", "--by", "jesus"])
     assert args.handler(args) == 1
     out, err = capsys.readouterr()
     assert "Traceback" not in out and "Traceback" not in err
     assert "code_repo" in out
     assert "knowledge.toml" in out
diff --git a/tests/test_config.py b/tests/test_config.py
new file mode 100644
index 0000000..aa72865
--- /dev/null
+++ b/tests/test_config.py
@@ -0,0 +1,110 @@
+import pytest
+
+from knowledge.config import ConfigError, load_config
+
+FULL = """\
+[project]
+name = "Example"
+
+[vocabulary]
+ontology_file = "example.ttl"
+namespace = "https://example.com/ontology#"
+instances = "https://example.com/id/"
+prefix = "ex"
+instance_prefix = "app"
+rule_class = "Rule"
+concept_class = "Concept"
+concept_spec = "concepts"
+field_class = "Field"
+field_name_pattern = "^[A-Z][A-Za-z0-9]*_[a-z][A-Za-z0-9]*$"
+underscore_reserved = true
+functional_properties = ["route", "editable"]
+verbatim_string_properties = ["emptyState"]
+
+[[ask]]
+name = "modules"
+query = "SELECT ?l WHERE { ?m a ex:Module ; rdfs:label ?l }"
+
+[repo]
+code_repo = "../code"
+
+[dependencies]
+route_property = "route"
+route_glob = "app/**/{segments}/page.tsx"
+absorbed_prefixes = ["platform"]
+
+[publish]
+target = "github-wiki"
+remote = "https://example.com/x.wiki.git"
+
+[publish.sidebar]
+title = "Example"
+order = ["home", "concepts"]
+nested_under = { "concepts" = "home" }
+"""
+
+MINIMAL = """\
+[project]
+name = "Example"
+
+[vocabulary]
+ontology_file = "ontology.ttl"
+namespace = "https://example.com/ontology#"
+instances = "https://example.com/id/"
+prefix = "ex"
+instance_prefix = "app"
+"""
+
+
+def write(tmp_path, text):
+    (tmp_path / "knowledge.toml").write_text(text, encoding="utf-8")
+    return tmp_path
+
+
+def test_full_config_round_trips(tmp_path):
+    config = load_config(write(tmp_path, FULL))
+    assert config.project_name == "Example"
+    assert config.vocabulary.prefix == "ex"
+    assert config.vocabulary.checks.functional_properties == ("route", "editable")
+    assert config.vocabulary.checks.underscore_reserved is True
+    assert [s.name for s in config.surveys] == ["modules"]
+    assert config.code_repo is not None and config.code_repo.name == "code"
+    assert config.dependencies.absorbed_prefixes == ("platform",)
+    assert config.publish.target == "github-wiki"
+    assert config.publish.sidebar.nested_under == {"concepts": "home"}
+
+
+def test_minimal_config_defaults_every_optional_section(tmp_path):
+    config = load_config(write(tmp_path, MINIMAL))
+    assert config.vocabulary.checks.rule_class == ""
+    assert config.surveys == ()
+    assert config.code_repo is None
+    assert config.dependencies.derives is False
+    assert config.publish.target == "none"
+    assert config.publish.sidebar.order == ()
+
+
+def test_placeholders_read_as_empty(tmp_path):
+    text = MINIMAL + '\n[repo]\ncode_repo = "{{CODE_REPO}}"\n'
+    config = load_config(write(tmp_path, text))
+    assert config.code_repo is None
+
+
+def test_template_marker_is_reported(tmp_path):
+    text = "[template]\nunconfigured = true\n\n" + MINIMAL
+    assert load_config(write(tmp_path, text)).unconfigured is True
+    assert load_config(write(tmp_path, MINIMAL)).unconfigured is False
+
+
+def test_missing_required_key_names_it(tmp_path):
+    text = '[project]\nname = "Example"\n\n[vocabulary]\nprefix = "ex"\n'
+    with pytest.raises(ConfigError) as exc:
+        load_config(write(tmp_path, text))
+    assert "vocabulary.namespace" in str(exc.value)
+
+
+def test_unknown_publish_target_is_rejected(tmp_path):
+    text = MINIMAL + '\n[publish]\ntarget = "carrier-pigeon"\n'
+    with pytest.raises(ConfigError) as exc:
+        load_config(write(tmp_path, text))
+    assert "carrier-pigeon" in str(exc.value)
diff --git a/tests/test_deps.py b/tests/test_deps.py
index 4985dfc..5ea75be 100644
--- a/tests/test_deps.py
+++ b/tests/test_deps.py
@@ -1,17 +1,16 @@
 import subprocess
 
 import pytest
 
 from knowledge import db, deps, lifecycle, scan
-from knowledge.config import Config
-from tests.conftest import write_spec
+from tests.conftest import make_config, write_spec
 
 
 def test_route_to_glob_ignores_route_groups():
     # /platform/assets lives at app/platform/(menuLayout)/assets/page.tsx
     assert deps.route_to_glob("/platform/assets") == "app/**/assets/page.tsx"
     assert deps.route_to_glob("/landing") == "app/**/landing/page.tsx"
     assert deps.route_to_glob("/platform/expenses/calendar") == (
         "app/**/expenses/calendar/page.tsx"
     )
 
@@ -84,68 +83,68 @@ def code_repo(tmp_path):
     subprocess.run(["git", "-C", str(root), "config", "user.name", "T"], check=True)
     subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
     subprocess.run(["git", "-C", str(root), "commit", "-m", "init"], check=True,
                    capture_output=True)
     return root
 
 
 def test_check_demotes_a_spec_whose_dependency_changed(repo, code_repo):
     conn = db.connect(repo)
     scan.scan(conn, repo)
-    config = Config(code_repo=code_repo, wiki_remote="x")
+    config = make_config(code_repo, remote="x")
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
-    config = Config(code_repo=code_repo, wiki_remote="x")
+    config = make_config(code_repo, remote="x")
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
-    config = Config(code_repo=code_repo, wiki_remote="x")
+    config = make_config(code_repo, remote="x")
     # assets is left as a draft; nothing to demote regardless of what changed.
     assert deps.check(conn, repo, config, demote=True) == []
 
 
 def test_check_demotes_a_spec_whose_dependency_was_renamed(repo, code_repo):
     """git reports only the destination of a rename by default. If changed_files did not
     also report the source path, this manual glob (which names the old directory) would
     match nothing and the spec would never be flagged."""
     conn = db.connect(repo)
     scan.scan(conn, repo)
-    config = Config(code_repo=code_repo, wiki_remote="x")
+    config = make_config(code_repo, remote="x")
 
     conn.execute(
         "INSERT INTO spec_dependency (spec_id, glob, note)"
         " VALUES ('assets','modules/server/submodules/assets/**','the service layer')"
     )
     service_dir = code_repo / "modules" / "server" / "submodules" / "assets"
     service_dir.mkdir(parents=True)
     (service_dir / "index.ts").write_text("export {}\n")
     subprocess.run(["git", "-C", str(code_repo), "add", "-A"], check=True, capture_output=True)
     subprocess.run(["git", "-C", str(code_repo), "commit", "-m", "add service"], check=True,
@@ -166,21 +165,21 @@ def test_check_demotes_a_spec_whose_dependency_was_renamed(repo, code_repo):
     findings = deps.check(conn, repo, config, demote=True)
     assert findings == [("assets", ["modules/server/submodules/assets/index.ts"])]
     assert list(conn.execute("SELECT status FROM spec WHERE id='assets'")) == [("draft",)]
 
 
 def test_check_accepts_a_code_repo_override(repo, code_repo, tmp_path):
     """CI checks the code repo out inside the workspace, not where knowledge.toml points."""
     conn = db.connect(repo)
     scan.scan(conn, repo)
     # A config pointing somewhere that does not exist, to prove the override is what is used.
-    config = Config(code_repo=tmp_path / "nonexistent", wiki_remote="x")
+    config = make_config(tmp_path / "nonexistent", remote="x")
     base = lifecycle.head_commit(code_repo)
 
     lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
     lifecycle.verify(conn, repo, config, "assets", by="jesus", prune=[], commit=base)
 
     page = code_repo / "app" / "platform" / "(menuLayout)" / "assets" / "page.tsx"
     page.write_text("changed\n")
     subprocess.run(["git", "-C", str(code_repo), "commit", "-am", "change"], check=True,
                    capture_output=True)
 
diff --git a/tests/test_lifecycle.py b/tests/test_lifecycle.py
index 344bdfe..eafaed0 100644
--- a/tests/test_lifecycle.py
+++ b/tests/test_lifecycle.py
@@ -1,26 +1,26 @@
 import pytest
 
 from knowledge import db, lifecycle, scan
-from knowledge.config import Config
+from tests.conftest import make_config
 
 
 @pytest.fixture
 def seeded(repo):
     conn = db.connect(repo)
     scan.scan(conn, repo)
     return repo, conn
 
 
 @pytest.fixture
 def config(tmp_path):
-    return Config(code_repo=tmp_path / "code", wiki_remote="https://example.com/x.wiki.git")
+    return make_config(tmp_path / "code")
 
 
 def test_verify_refuses_an_unmodeled_spec(seeded, config):
     repo, conn = seeded
     with pytest.raises(RuntimeError, match="not been modeled"):
         lifecycle.verify(conn, repo, config, "assets", by="jesus", prune=[], commit="abc123")
 
 
 def test_verify_refuses_while_a_question_is_open(seeded, config):
     repo, conn = seeded
diff --git a/tests/test_paths.py b/tests/test_paths.py
index 92b9f60..3a49044 100644
--- a/tests/test_paths.py
+++ b/tests/test_paths.py
@@ -1,14 +1,13 @@
 import pytest
 
 from knowledge import paths
-from knowledge.config import load_config
 
 
 def make_repo(tmp_path):
     (tmp_path / "knowledge.toml").write_text(
         '[repo]\ncode_repo = "../monicords_app"\n\n'
         '[wiki]\nremote = "https://example.com/x.wiki.git"\n',
         encoding="utf-8",
     )
     (tmp_path / "specs" / "assets").mkdir(parents=True)
     return tmp_path
@@ -26,17 +25,10 @@ def test_find_root_raises_when_there_is_no_marker(tmp_path):
 
 def test_paths_are_derived_from_the_root(tmp_path):
     root = make_repo(tmp_path)
     p = paths.get_paths(root)
     assert p.specs == root / "specs"
     assert p.ontology_ttl == root / "ontology" / "monicords.ttl"
     assert p.db == root / ".metadata" / "knowledge.db"
     assert p.dump == root / ".metadata" / "dump.sql"
     assert paths.spec_md(p, "assets") == root / "specs" / "assets" / "spec.md"
     assert paths.spec_ttl(p, "assets") == root / "specs" / "assets" / "spec.ttl"
-
-
-def test_config_resolves_the_code_repo_relative_to_the_root(tmp_path):
-    root = make_repo(tmp_path)
-    cfg = load_config(root)
-    assert cfg.code_repo == (root / ".." / "monicords_app").resolve()
-    assert cfg.wiki_remote == "https://example.com/x.wiki.git"
diff --git a/tests/test_round_trip.py b/tests/test_round_trip.py
index aaf05be..9b82d71 100644
--- a/tests/test_round_trip.py
+++ b/tests/test_round_trip.py
@@ -1,20 +1,20 @@
 """A spec moves from scaffold to modeled to verified, exercising every CLI-backing
 function an agent calls, in the order an agent calls them. Design's "Round trip" testing
 item: extract (scaffold), model, validate, and confirm the graph parses and its claims
 resolve.
 """
 
 from __future__ import annotations
 
 from knowledge import db, graph, lifecycle, lint, scan
-from knowledge.config import Config
+from tests.conftest import make_config
 
 FIXTURE_TTL = """\
 app:Budgets a mon:Module ;
     rdfs:label   "Budgets"@en ;
     rdfs:comment "Monthly spending limits per category."@en ;
     mon:contains app:BudgetsList .
 
 app:BudgetsList a mon:View ;
     rdfs:label "Budgets"@en ;
     mon:partOf app:Budgets ;
@@ -39,17 +39,17 @@ def test_a_spec_can_be_scaffolded_modeled_and_verified(repo):
 
     lifecycle.mark_modeled(conn, repo, "budgets", by="writer", ontology_version="1.0.0")
 
     g = graph.load_graph(repo, ["budgets"])
     assert graph.dangling_terms(g) == []
     assert lint.invented_predicates(g) == []
     assert lint.invented_types(g) == []
     assert lint.restated_rule_comments(g) == []
     assert lint.naming_violations(g) == []
 
-    config = Config(code_repo=repo.root, wiki_remote="https://example.com/x.wiki.git")
+    config = make_config(repo.root)
     lifecycle.verify(conn, repo, config, "budgets", by="jesus", prune=[], commit="abc123")
 
     row = list(conn.execute(
         "SELECT status, modeled_by, verified_by FROM spec WHERE id='budgets'"
     ))
     assert row == [("verified", "writer", "jesus")]
diff --git a/tests/test_vocab.py b/tests/test_vocab.py
new file mode 100644
index 0000000..17e15e2
--- /dev/null
+++ b/tests/test_vocab.py
@@ -0,0 +1,43 @@
+from rdflib import URIRef
+
+from knowledge.vocab import Checks, Vocabulary
+
+
+def make() -> Vocabulary:
+    return Vocabulary(
+        ontology_file="ontology.ttl",
+        namespace="https://example.com/ontology#",
+        instances="https://example.com/id/",
+        prefix="ex",
+        instance_prefix="app",
+        checks=Checks(),
+    )
+
+
+def test_term_and_instance_build_iris():
+    v = make()
+    assert v.term("Rule") == URIRef("https://example.com/ontology#Rule")
+    assert v.instance("Assets") == URIRef("https://example.com/id/Assets")
+
+
+def test_is_term_and_is_instance_discriminate():
+    v = make()
+    assert v.is_term(v.term("Rule"))
+    assert not v.is_term(v.instance("Assets"))
+    assert v.is_instance(v.instance("Assets"))
+    assert not v.is_instance(URIRef("http://elsewhere.test/x"))
+
+
+def test_qname_shortens_known_namespaces_and_passes_others_through():
+    v = make()
+    assert v.qname(v.term("Rule")) == "ex:Rule"
+    assert v.qname(v.instance("Assets")) == "app:Assets"
+    assert v.qname(URIRef("http://elsewhere.test/x")) == "http://elsewhere.test/x"
+
+
+def test_sparql_prefixes_declare_both_project_namespaces_and_the_fixed_ones():
+    block = make().sparql_prefixes
+    assert "PREFIX ex: <https://example.com/ontology#>" in block
+    assert "PREFIX app: <https://example.com/id/>" in block
+    assert "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>" in block
+    assert "PREFIX skos:" in block
```
