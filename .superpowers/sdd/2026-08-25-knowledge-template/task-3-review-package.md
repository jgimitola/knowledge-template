# Task 3 review package

BASE: 901c7b8
HEAD: 58d9446

## Commits
```
58d9446 feat: build the graph from the configured vocabulary
```

## Stat
```
 src/knowledge/__init__.py       |   2 +-
 src/knowledge/cli.py            |  84 ++++++++++--------
 src/knowledge/contradictions.py |  16 ++--
 src/knowledge/deps.py           |  34 +++++---
 src/knowledge/graph.py          |  67 ++++-----------
 src/knowledge/lint.py           |  89 +++++++++----------
 src/knowledge/paths.py          |   4 +-
 src/knowledge/publish.py        |   6 +-
 src/knowledge/scan.py           |   4 +-
 tests/conftest.py               | 180 ++++++++++++++++++++++++++------------
 tests/test_cli_read.py          |   9 +-
 tests/test_contradictions.py    |  16 ++--
 tests/test_deps.py              |  24 +++---
 tests/test_graph.py             |  90 +++++++++++++------
 tests/test_lint.py              | 186 +++++++++++++++++++++-------------------
 tests/test_paths.py             |   4 +-
 tests/test_round_trip.py        |  29 ++++---
 17 files changed, 471 insertions(+), 373 deletions(-)
```

## Residual monicords references at HEAD (expected: publish.py + test_publish.py only, owned by Task 7)
```
src/knowledge/publish.py:5:mon:Actor declarations, so it stays an ordinary spec and publishes like any other page.
src/knowledge/publish.py:114:    lines = ["### Monicords", ""]
Binary file src/knowledge/__pycache__/publish.cpython-313.pyc matches
tests/test_publish.py:48:        "---\nid: home\n---\n\n# Monicords\n\nProse.\n", encoding="utf-8"
tests/test_publish.py:56:    assert "[Monicords](Home)" not in sidebar
Binary file tests/__pycache__/test_extraction.cpython-313-pytest-8.3.4.pyc matches
Binary file tests/__pycache__/test_publish.cpython-313-pytest-8.3.4.pyc matches
```

## Full diff (-U10)
```diff
diff --git a/src/knowledge/__init__.py b/src/knowledge/__init__.py
index 1d05fb5..5b1ad14 100644
--- a/src/knowledge/__init__.py
+++ b/src/knowledge/__init__.py
@@ -1 +1 @@
-"""Authoring, tracking and publishing for the monicords knowledge base."""
+"""Authoring, tracking and publishing for a project's knowledge base."""
diff --git a/src/knowledge/cli.py b/src/knowledge/cli.py
index 223ce98..c6fd2a7 100644
--- a/src/knowledge/cli.py
+++ b/src/knowledge/cli.py
@@ -8,28 +8,30 @@ from __future__ import annotations
 
 import argparse
 import sqlite3
 import subprocess
 import sys
 from collections.abc import Sequence
 from pathlib import Path
 
 from knowledge import db, gitcmd, graph, scan
 from knowledge.config import Config, load_config
-from knowledge.paths import Paths, get_paths
+from knowledge.paths import Paths, find_root, get_paths
 
 VERSION = "0.1.0"
 
 
 def open_repo(_args: argparse.Namespace) -> tuple[Paths, Config, sqlite3.Connection]:
-    paths = get_paths()
-    return paths, load_config(paths.root), db.connect(paths)
+    root = find_root()
+    config = load_config(root)
+    paths = get_paths(root, config.vocabulary.ontology_file)
+    return paths, config, db.connect(paths)
 
 
 def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[tuple]:
     return list(conn.execute(sql, params))
 
 
 def _print_table(headers: list[str], rows: list[tuple]) -> None:
     if not rows:
         print("(nothing)")
         return
@@ -179,124 +181,134 @@ def _check(name: str, items: Sequence[str], ok_message: str, strict: bool) -> bo
     if not items:
         print(ok_message)
         return False
     print(f"\n{len(items)} {name}:")
     for item in items:
         print("  -", item)
     return strict
 
 
 def cmd_validate(args: argparse.Namespace) -> int:
-    paths, _config, _ = open_repo(args)
+    paths, config, _ = open_repo(args)
+    vocab = config.vocabulary
     from knowledge import lint
     ids = graph.spec_ids(paths)
     print(f"{len(ids)} spec(s)")
     try:
-        g = graph.load_graph(paths, ids)
+        g = graph.load_graph(paths, vocab, ids)
     except Exception as exc:  # noqa: BLE001 - the parser's message is the useful part
         print(f"\nPARSE FAILED: {exc}")
         return 1
     print(f"parsed OK: {len(g)} triples")
 
     strict = args.strict
     failures = [
-        _check("term(s) referenced but never declared", graph.dangling_terms(g),
+        _check("term(s) referenced but never declared", graph.dangling_terms(g, vocab),
                "no dangling references", True),
         _check("link(s) point at pages that do not exist", graph.broken_links(paths, ids),
                "all internal links resolve", strict),
         _check("invented ontology term(s) never declared",
-               lint.invented_predicates(g) + lint.invented_types(g),
+               lint.invented_predicates(g, vocab) + lint.invented_types(g, vocab),
                "no invented ontology terms", strict),
         _check("rule(s) whose comment restates the label or is missing",
-               lint.restated_rule_comments(g),
+               lint.restated_rule_comments(g, vocab),
                "every rule's comment says more than its label", strict),
-        _check("naming violation(s)", lint.naming_violations(g),
+        _check("naming violation(s)", lint.naming_violations(g, vocab),
                "no naming violations", strict),
         _check("concept(s) redeclared locally instead of referenced",
-               lint.locally_redeclared_concepts(paths, ids),
+               lint.locally_redeclared_concepts(paths, vocab, ids),
                "no locally redeclared concepts", strict),
         _check("predicate(s) used outside their declared domain or range",
-               lint.domain_range_violations(g),
+               lint.domain_range_violations(g, vocab),
                "every predicate stays inside its declared domain and range", strict),
         _check("empty-state string(s) no prose states",
-               lint.ungrounded_empty_states(paths, ids),
+               lint.ungrounded_empty_states(paths, vocab, ids),
                "every empty state appears in its spec's prose", strict),
     ]
     return 1 if any(failures) else 0
 
 
 def cmd_graph(args: argparse.Namespace) -> int:
-    paths, _config, conn = open_repo(args)
+    paths, config, conn = open_repo(args)
     ids = _selected_ids(conn, paths, args.include_drafts)
-    g = graph.load_graph(paths, ids)
+    g = graph.load_graph(paths, config.vocabulary, ids)
     output = Path(args.output)
     output.write_text(g.serialize(format="turtle"), encoding="utf-8", newline="\n")
     print(f"{len(g)} triples from {len(ids)} spec(s) written to {output}")
     return 0
 
 
 def cmd_query(args: argparse.Namespace) -> int:
-    paths, _config, conn = open_repo(args)
-    g = graph.load_graph(paths, _selected_ids(conn, paths, args.include_drafts))
-    rows = graph.run_query(g, args.sparql)
+    paths, config, conn = open_repo(args)
+    vocab = config.vocabulary
+    g = graph.load_graph(paths, vocab, _selected_ids(conn, paths, args.include_drafts))
+    rows = graph.run_query(g, vocab, args.sparql)
     print(f"{len(rows)} result(s)")
     for row in rows:
         print("   ", "  ".join(row))
     return 0
 
 
 def cmd_describe(args: argparse.Namespace) -> int:
-    paths, _config, _ = open_repo(args)
-    g = graph.load_graph(paths)
-    term = args.term if ":" in args.term else f"app:{args.term}"
+    paths, config, _ = open_repo(args)
+    vocab = config.vocabulary
+    g = graph.load_graph(paths, vocab)
+    term = args.term if ":" in args.term else f"{vocab.instance_prefix}:{args.term}"
     print(f"--- {term} as subject ---")
-    for row in graph.run_query(g, f"SELECT ?p ?o WHERE {{ {term} ?p ?o }}"):
+    for row in graph.run_query(g, vocab, f"SELECT ?p ?o WHERE {{ {term} ?p ?o }}"):
         print("   ", "  ".join(row))
     print(f"\n--- {term} as object ---")
-    for row in graph.run_query(g, f"SELECT ?s ?p WHERE {{ ?s ?p {term} }}"):
+    for row in graph.run_query(g, vocab, f"SELECT ?s ?p WHERE {{ ?s ?p {term} }}"):
         print("   ", "  ".join(row))
     return 0
 
 
 def cmd_ask(args: argparse.Namespace) -> int:
-    paths, _config, conn = open_repo(args)
-    g = graph.load_graph(paths, _selected_ids(conn, paths, args.include_drafts))
-    for title, sparql in graph.SANITY_QUERIES.items():
-        rows = graph.run_query(g, sparql)
+    paths, config, conn = open_repo(args)
+    vocab = config.vocabulary
+    presets = graph.surveys(config)
+    if not presets:
+        print("no `ask` presets configured — add [[ask]] tables to knowledge.toml")
+        return 0
+    g = graph.load_graph(paths, vocab, _selected_ids(conn, paths, args.include_drafts))
+    for title, sparql in presets:
+        rows = graph.run_query(g, vocab, sparql)
         print(f"\n{title} - {len(rows)} result(s)")
         for row in rows:
             print("   ", "  ".join(row))
     return 0
 
 
 def cmd_contradictions(args: argparse.Namespace) -> int:
-    paths, _config, conn = open_repo(args)
+    paths, config, conn = open_repo(args)
+    vocab = config.vocabulary
     from knowledge import contradictions, lint
     ids = _selected_ids(conn, paths, args.include_drafts)
-    g = graph.load_graph(paths, ids)
+    g = graph.load_graph(paths, vocab, ids)
     found = False
 
-    conflicts = contradictions.functional_conflicts(g)
+    conflicts = contradictions.functional_conflicts(g, vocab)
     if conflicts:
         found = True
         print(f"{len(conflicts)} functional-property conflict(s):")
         for subject, prop, values in conflicts:
-            print(f"  - {subject} mon:{prop} has {len(values)} values: {', '.join(values)}")
+            print(f"  - {subject} {vocab.prefix}:{prop} has {len(values)} values:"
+                  f" {', '.join(values)}")
 
-    dangling = graph.dangling_terms(g)
+    dangling = graph.dangling_terms(g, vocab)
     if dangling:
         found = True
         print(f"\n{len(dangling)} term(s) referenced but never declared:")
         for term in dangling:
             print("  -", term)
 
-    redeclared = lint.locally_redeclared_concepts(paths, ids)
+    redeclared = lint.locally_redeclared_concepts(paths, vocab, ids)
     if redeclared:
         found = True
         print(f"\n{len(redeclared)} concept(s) redeclared locally instead of referenced:")
         for msg in redeclared:
             print("  -", msg)
 
     if not found:
         print("no mechanical contradictions found")
     return 0
 
@@ -408,21 +420,21 @@ def cmd_stale(args: argparse.Namespace) -> int:
         for spec_id, hits in findings:
             print(f"{spec_id}: {len(hits)} dependency change(s)")
             for path in hits:
                 print("   ", path)
         if args.demote:
             db.save(conn, paths)
             print(f"\n{len(findings)} spec(s) demoted to draft")
         else:
             print(f"\n{len(findings)} spec(s) would be demoted (pass --demote to apply)")
 
-    gaps = deps.uncheckable(conn, paths)
+    gaps = deps.uncheckable(conn, paths, config.vocabulary)
     if gaps:
         print(f"\n{len(gaps)} verified spec(s) have no dependencies and cannot be checked:")
         print("   ", ", ".join(gaps))
         print('  Add one with: knowledge dep add <spec> "<glob>"')
     return 0
 
 
 def _clear_markdown(out_dir: Path) -> list[str]:
     """Unlink every top-level *.md in out_dir, returning what was removed.
 
@@ -516,35 +528,35 @@ def cmd_dep(args: argparse.Namespace) -> int:
             if not deps.matches({args.glob}, tracked):
                 print("  warning: this glob matches no file in the code repository today")
     elif args.action == "remove":
         conn.execute(
             "DELETE FROM spec_dependency WHERE spec_id = ? AND glob = ?", (args.spec, args.glob)
         )
         db.record_event(conn, args.spec, "dependency_removed", "cli", args.glob)
         db.save(conn, paths)
         print(f"{args.spec} no longer depends on {args.glob}")
     else:
-        derived = deps.derived_globs(paths, args.spec)
+        derived = deps.derived_globs(paths, config.vocabulary, args.spec)
         manual = deps.manual_globs(conn, args.spec)
         print(f"derived from the graph ({len(derived)}):")
         for glob in sorted(derived):
             print("   ", glob)
         print(f"manual ({len(manual)}):")
         for glob in sorted(manual):
             print("   ", glob)
     return 0
 
 
 def build_parser() -> argparse.ArgumentParser:
     parser = argparse.ArgumentParser(
         prog="knowledge",
-        description="Author, track and publish the monicords knowledge base.",
+        description="Author, track and publish a project's knowledge base.",
     )
     parser.add_argument("--version", action="version", version=VERSION)
     parser.set_defaults(handler=None)
     sub = parser.add_subparsers(dest="command")
 
     scan_p = sub.add_parser("scan", help="reconcile spec files against the database")
     scan_p.set_defaults(handler=cmd_scan)
 
     list_p = sub.add_parser("list", help="list specs")
     list_p.add_argument("--status", choices=["draft", "verified"])
@@ -578,21 +590,21 @@ def build_parser() -> argparse.ArgumentParser:
 
     qy_p = sub.add_parser("query", help="run SPARQL (prefixes are added for you)")
     qy_p.add_argument("sparql")
     qy_p.add_argument("--include-drafts", action="store_true")
     qy_p.set_defaults(handler=cmd_query)
 
     d_p = sub.add_parser("describe", help="every triple touching one node")
     d_p.add_argument("term")
     d_p.set_defaults(handler=cmd_describe)
 
-    ask_p = sub.add_parser("ask", help="run the built-in sanity queries")
+    ask_p = sub.add_parser("ask", help="run the configured [[ask]] survey queries")
     ask_p.add_argument("--include-drafts", action="store_true")
     ask_p.set_defaults(handler=cmd_ask)
 
     cx_p = sub.add_parser(
         "contradictions", help="mechanical contradiction checks for the interviewer"
     )
     cx_p.add_argument("--include-drafts", action="store_true")
     cx_p.set_defaults(handler=cmd_contradictions)
 
     new_p = sub.add_parser("new", help="scaffold a new spec folder")
diff --git a/src/knowledge/contradictions.py b/src/knowledge/contradictions.py
index 28e3e1f..068100c 100644
--- a/src/knowledge/contradictions.py
+++ b/src/knowledge/contradictions.py
@@ -1,31 +1,31 @@
 """Mechanical contradiction checks: the part of the interviewer's per-answer check that is
 a SPARQL-shaped query rather than a judgement call.
 """
 
 from __future__ import annotations
 
 from collections import defaultdict
 
-from rdflib import Graph, URIRef
+from rdflib import Graph
 
-from knowledge.graph import MON
+from knowledge.vocab import Vocabulary
 
-# Properties the ontology documents as single-valued, plus mon:defaultsTo and mon:route —
-# the design's own two examples of what this check looks for. "Functional by convention"
+# Properties the ontology documents as single-valued, plus defaultsTo and route — the
+# design's own two examples of what this check looks for. "Functional by convention"
 # because RDFS never enforces it (ontology/README.md, "Properties with literal values").
 FUNCTIONAL_PROPERTIES = ("route", "editable", "required", "viewport", "defaultsTo")
 
 
-def functional_conflicts(g: Graph) -> list[tuple[str, str, list[str]]]:
+def functional_conflicts(g: Graph, vocab: Vocabulary) -> list[tuple[str, str, list[str]]]:
     """(subject, property, sorted values) for every subject asserting more than one value
-    on a property that is supposed to hold at most one — two mon:route values on one view,
-    two mon:defaultsTo on one field."""
+    on a property that is supposed to hold at most one — two route values on one view, two
+    defaultsTo values on one field."""
     seen: dict[tuple[str, str], set[str]] = defaultdict(set)
     for prop in FUNCTIONAL_PROPERTIES:
-        for subject, obj in g.subject_objects(URIRef(MON + prop)):
+        for subject, obj in g.subject_objects(vocab.term(prop)):
             seen[(str(subject), prop)].add(str(obj))
     return sorted(
         (subject, prop, sorted(values))
         for (subject, prop), values in seen.items()
         if len(values) > 1
     )
diff --git a/src/knowledge/deps.py b/src/knowledge/deps.py
index 993f231..34edf41 100644
--- a/src/knowledge/deps.py
+++ b/src/knowledge/deps.py
@@ -1,30 +1,31 @@
 """What code does a spec depend on, and has any of it changed since verification?
 
-Two sources. Derived globs come from the spec's own triples — a mon:route or a
-mon:endpoint resolves mechanically to a file pattern — and are recomputed on every run, so
-they cannot themselves go stale. Manual globs in spec_dependency cover what the ontology
-does not model: services, Prisma models, shared utilities.
+Two sources. Derived globs come from the spec's own triples — a route or an endpoint
+resolves mechanically to a file pattern — and are recomputed on every run, so they cannot
+themselves go stale. Manual globs in spec_dependency cover what the ontology does not
+model: services, Prisma models, shared utilities.
 
 This never blocks a build. A code change failing on documentation is a check people learn
 to bypass; staleness is data, surfaced as work.
 """
 
 from __future__ import annotations
 
 import re
 from pathlib import Path, PurePosixPath
 
 from knowledge import gitcmd, lifecycle
 from knowledge.config import Config
 from knowledge.graph import load_spec_graph, run_query
 from knowledge.paths import Paths
+from knowledge.vocab import Vocabulary
 
 DYNAMIC_SEGMENT = re.compile(r"^\{.+\}$")
 
 # Routes whose files sit under a Next.js route group. /platform/assets lives at
 # app/platform/(menuLayout)/assets/page.tsx: the group sits between `platform` and the
 # module, so `platform` is dropped and the ** absorbs it along with the group.
 ROUTE_PREFIXES_ABSORBED_BY_GLOB = ("platform",)
 
 
 def route_to_glob(route: str) -> str:
@@ -36,39 +37,42 @@ def route_to_glob(route: str) -> str:
         segments = segments[1:]
     segments = ["*" if DYNAMIC_SEGMENT.match(part) else part for part in segments]
     return "app/**/" + "/".join(segments) + "/page.tsx"
 
 
 def endpoint_to_glob(endpoint: str) -> str:
     path = endpoint.split()[-1]  # tolerate "GET /api/cron" as well as "/api/cron"
     return "app/" + path.strip("/") + "/**/route.ts"
 
 
-def derived_globs(paths: Paths, spec_id: str) -> set[str]:
-    g = load_spec_graph(paths, spec_id)
-    globs = {route_to_glob(row[0]) for row in run_query(g, "SELECT ?r WHERE { ?s mon:route ?r }")}
+def derived_globs(paths: Paths, vocab: Vocabulary, spec_id: str) -> set[str]:
+    g = load_spec_graph(paths, vocab, spec_id)
+    globs = {
+        route_to_glob(row[0])
+        for row in run_query(g, vocab, f"SELECT ?r WHERE {{ ?s {vocab.prefix}:route ?r }}")
+    }
     globs |= {
         endpoint_to_glob(row[0])
-        for row in run_query(g, "SELECT ?e WHERE { ?s mon:endpoint ?e }")
+        for row in run_query(g, vocab, f"SELECT ?e WHERE {{ ?s {vocab.prefix}:endpoint ?e }}")
     }
     return globs
 
 
 def manual_globs(conn, spec_id: str) -> set[str]:
     return {
         row[0]
         for row in conn.execute("SELECT glob FROM spec_dependency WHERE spec_id = ?", (spec_id,))
     }
 
 
-def spec_globs(conn, paths: Paths, spec_id: str) -> set[str]:
-    return derived_globs(paths, spec_id) | manual_globs(conn, spec_id)
+def spec_globs(conn, paths: Paths, vocab: Vocabulary, spec_id: str) -> set[str]:
+    return derived_globs(paths, vocab, spec_id) | manual_globs(conn, spec_id)
 
 
 def changed_files(code_repo: Path, since: str) -> list[str]:
     """Both sides of a rename count. git reports only the destination path by default, so
     a renamed dependency directory would match no glob and the spec would never be flagged
     — a silent failure, and the one kind staleness cannot report on itself."""
     result = gitcmd.run(
         ["-C", str(code_repo), "diff", "--name-status", "-M", f"{since}..HEAD"],
         capture_output=True, text=True, check=True,
     )
@@ -103,30 +107,32 @@ def check(conn, paths: Paths, config: Config, demote: bool,
           code_repo: Path | None = None) -> list[tuple[str, list[str]]]:
     """code_repo overrides the configured path. CI checks the code repository out inside
     its own workspace, which is not where knowledge.toml points."""
     root = code_repo if code_repo is not None else config.code_repo
     findings: list[tuple[str, list[str]]] = []
     rows = list(conn.execute(
         "SELECT id, verified_against_commit FROM spec"
         " WHERE status = 'verified' AND verified_against_commit IS NOT NULL ORDER BY id"
     ))
     for spec_id, since in rows:
-        hits = matches(spec_globs(conn, paths, spec_id), changed_files(root, since))
+        hits = matches(
+            spec_globs(conn, paths, config.vocabulary, spec_id), changed_files(root, since)
+        )
         if not hits:
             continue
         findings.append((spec_id, hits))
         if demote:
             lifecycle.demote(
                 conn, spec_id, "changed since verification: " + ", ".join(hits), "stale-check"
             )
     return findings
 
 
-def uncheckable(conn, paths: Paths) -> list[str]:
-    """Verified specs with zero dependencies — no mon:route/mon:endpoint and no manual
+def uncheckable(conn, paths: Paths, vocab: Vocabulary) -> list[str]:
+    """Verified specs with zero dependencies — no derived route/endpoint and no manual
     glob. `check` reports these as clean, which is misleading: "checked and clean" and
     "cannot be checked" are different states, and conflating them is the same sin as
     guessing a missing exchange rate."""
     ids = [
         row[0] for row in conn.execute("SELECT id FROM spec WHERE status = 'verified' ORDER BY id")
     ]
-    return [spec_id for spec_id in ids if not spec_globs(conn, paths, spec_id)]
+    return [spec_id for spec_id in ids if not spec_globs(conn, paths, vocab, spec_id)]
diff --git a/src/knowledge/graph.py b/src/knowledge/graph.py
index 093f416..aac7661 100644
--- a/src/knowledge/graph.py
+++ b/src/knowledge/graph.py
@@ -7,114 +7,81 @@ spec's Turtle is written against.
 """
 
 from __future__ import annotations
 
 import re
 from collections.abc import Sequence
 
 from rdflib import RDF, Graph, URIRef
 
 from knowledge.paths import Paths, spec_md, spec_ttl
-
-MON = "https://monicords.com/ontology#"
-APP = "https://monicords.com/id/"
+from knowledge.vocab import Vocabulary
 
 MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
 
-SPARQL_PREFIXES = """
-PREFIX mon:     <https://monicords.com/ontology#>
-PREFIX app:     <https://monicords.com/id/>
-PREFIX rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
-PREFIX rdfs:    <http://www.w3.org/2000/01/rdf-schema#>
-PREFIX xsd:     <http://www.w3.org/2001/XMLSchema#>
-PREFIX skos:    <http://www.w3.org/2004/02/skos/core#>
-PREFIX dcterms: <http://purl.org/dc/terms/>
-"""
-
-SANITY_QUERIES = {
-    "modules": "SELECT ?label WHERE { ?m a mon:Module ; rdfs:label ?label } ORDER BY ?label",
-    "views and their routes": """
-        SELECT ?label ?route WHERE { ?v a mon:View ; rdfs:label ?label ; mon:route ?route }
-        ORDER BY ?route
-    """,
-    "what the user sees only on narrow screens": """
-        SELECT ?label WHERE { ?s mon:viewport "narrow" ; rdfs:label ?label } ORDER BY ?label
-    """,
-    "rules, and what each constrains": """
-        SELECT ?rule ?target WHERE {
-          ?r a mon:Rule ; rdfs:label ?rule ; mon:constrains ?t .
-          OPTIONAL { ?t rdfs:label ?tl }
-          BIND(COALESCE(?tl, REPLACE(STR(?t), "^.*[#/]", "")) AS ?target)
-        } ORDER BY ?rule
-    """,
-    "fields the user cannot edit": """
-        SELECT ?label WHERE { ?f mon:editable false ; rdfs:label ?label } ORDER BY ?label
-    """,
-    "concepts and how many things reference them": """
-        SELECT ?label (COUNT(?s) AS ?references) WHERE {
-          ?c a mon:Concept ; rdfs:label ?label . ?s ?p ?c .
-        } GROUP BY ?label ORDER BY DESC(?references)
-    """,
-}
-
 
 def spec_ids(paths: Paths) -> list[str]:
     if not paths.specs.is_dir():
         return []
     return sorted(d.name for d in paths.specs.iterdir() if (d / "spec.md").is_file())
 
 
-def wiki_page_name(spec_id: str) -> str:
+def page_name(spec_id: str) -> str:
     """assets -> Assets, loans-out -> Loans-Out. Inverse of str.lower() on a page stem."""
     return "-".join(word.capitalize() for word in spec_id.split("-"))
 
 
 def turtle_source(paths: Paths, ids: Sequence[str]) -> str:
     chunks = [f"# --- ontology ---\n{paths.ontology_ttl.read_text(encoding='utf-8')}"]
     for spec_id in ids:
         path = spec_ttl(paths, spec_id)
         if path.is_file():
             chunks.append(f"# --- {spec_id} ---\n{path.read_text(encoding='utf-8')}")
     return "\n".join(chunks)
 
 
-def load_graph(paths: Paths, ids: Sequence[str] | None = None) -> Graph:
+def load_graph(paths: Paths, vocab: Vocabulary, ids: Sequence[str] | None = None) -> Graph:
     g = Graph()
-    g.bind("mon", MON)
-    g.bind("app", APP)
+    g.bind(vocab.prefix, vocab.namespace)
+    g.bind(vocab.instance_prefix, vocab.instances)
     g.parse(data=turtle_source(paths, spec_ids(paths) if ids is None else ids), format="turtle")
     return g
 
 
-def load_spec_graph(paths: Paths, spec_id: str) -> Graph:
+def load_spec_graph(paths: Paths, vocab: Vocabulary, spec_id: str) -> Graph:
     """The ontology plus one spec, so the spec's own triples can be isolated."""
-    return load_graph(paths, [spec_id])
+    return load_graph(paths, vocab, [spec_id])
 
 
-def run_query(g: Graph, sparql: str) -> list[tuple[str, ...]]:
-    return [tuple(str(value) for value in row) for row in g.query(SPARQL_PREFIXES + sparql)]
+def run_query(g: Graph, vocab: Vocabulary, sparql: str) -> list[tuple[str, ...]]:
+    return [tuple(str(value) for value in row) for row in g.query(vocab.sparql_prefixes + sparql)]
 
 
-def dangling_terms(g: Graph) -> list[str]:
+def dangling_terms(g: Graph, vocab: Vocabulary) -> list[str]:
     typed = {s for s in g.subjects(RDF.type, None) if isinstance(s, URIRef)}
     used = {
         term
         for triple in g
         for term in triple
-        if isinstance(term, URIRef) and str(term).startswith((MON, APP))
+        if isinstance(term, URIRef) and (vocab.is_term(term) or vocab.is_instance(term))
     }
     return sorted(str(term) for term in used - typed)
 
 
+def surveys(config) -> list[tuple[str, str]]:
+    """The `ask` presets, in the order knowledge.toml declares them."""
+    return [(survey.name, survey.query) for survey in config.surveys]
+
+
 def broken_links(paths: Paths, ids: Sequence[str]) -> list[str]:
     """Links in prose point at wiki page names, which are derived from spec ids."""
-    known = {wiki_page_name(spec_id) for spec_id in spec_ids(paths)} | {"Ontology"}
+    known = {page_name(spec_id) for spec_id in spec_ids(paths)} | {"Ontology"}
     broken: list[str] = []
     for spec_id in ids:
         path = spec_md(paths, spec_id)
         if not path.is_file():
             continue
         for text, target in MD_LINK.findall(path.read_text(encoding="utf-8")):
             if target.startswith(("http", "#")):
                 continue
             if target.split("#", 1)[0] not in known:
                 broken.append(f"{spec_id}: [{text}]({target})")
diff --git a/src/knowledge/lint.py b/src/knowledge/lint.py
index ebff773..3a4d087 100644
--- a/src/knowledge/lint.py
+++ b/src/knowledge/lint.py
@@ -6,198 +6,199 @@ comment that just restates its label, a name that breaks the pattern its kind is
 to follow (ontology/README.md's naming table). `validate --strict` runs this on every push,
 so the agent is checked rather than trusted for exactly this part of its job.
 """
 
 from __future__ import annotations
 
 import re
 
 from rdflib import RDF, RDFS, Graph, URIRef
 
-from knowledge.graph import APP, MON
 from knowledge.paths import Paths
+from knowledge.vocab import Vocabulary
 
 FIELD_NAME = re.compile(r"^[A-Z][A-Za-z0-9]*_[a-z][A-Za-z0-9]*$")
 
 
 def _local(term) -> str:
     return str(term).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
 
 
-def known_terms(g: Graph) -> tuple[set[str], set[str]]:
-    """(classes, properties) the ontology itself declares under mon:."""
-    classes = {str(s) for s in g.subjects(RDF.type, RDFS.Class) if str(s).startswith(MON)}
+def known_terms(g: Graph, vocab: Vocabulary) -> tuple[set[str], set[str]]:
+    """(classes, properties) the ontology itself declares under the project namespace."""
+    classes = {str(s) for s in g.subjects(RDF.type, RDFS.Class) if vocab.is_term(s)}
     properties = {
-        str(s) for s in g.subjects(RDF.type, RDF.Property) if str(s).startswith(MON)
+        str(s) for s in g.subjects(RDF.type, RDF.Property) if vocab.is_term(s)
     }
     return classes, properties
 
 
-def invented_predicates(g: Graph) -> list[str]:
-    """Every mon: predicate actually asserted, that the ontology never declared."""
-    _, properties = known_terms(g)
-    used = {str(p) for p in g.predicates() if str(p).startswith(MON)}
+def invented_predicates(g: Graph, vocab: Vocabulary) -> list[str]:
+    """Every project-namespace predicate actually asserted, that the ontology never declared."""
+    _, properties = known_terms(g, vocab)
+    used = {str(p) for p in g.predicates() if vocab.is_term(p)}
     return sorted(used - properties)
 
 
-def invented_types(g: Graph) -> list[str]:
-    """Every mon: class actually asserted with `a`, that the ontology never declared."""
-    classes, _ = known_terms(g)
-    used = {str(o) for o in g.objects(None, RDF.type) if str(o).startswith(MON)}
+def invented_types(g: Graph, vocab: Vocabulary) -> list[str]:
+    """Every project-namespace class actually asserted with `a`, that the ontology never declared."""
+    classes, _ = known_terms(g, vocab)
+    used = {str(o) for o in g.objects(None, RDF.type) if vocab.is_term(o)}
     return sorted(used - classes)
 
 
-def restated_rule_comments(g: Graph) -> list[str]:
+def restated_rule_comments(g: Graph, vocab: Vocabulary) -> list[str]:
     """A comment that just repeats the label carries no reason a reader could not already
-    infer from the label alone — the whole point of a mon:Rule's rdfs:comment."""
+    infer from the label alone — the whole point of a rule's rdfs:comment."""
 
     def norm(text: str) -> str:
         return text.strip().rstrip(".").lower()
 
     offenders = []
-    for rule in g.subjects(RDF.type, URIRef(MON + "Rule")):
+    for rule in g.subjects(RDF.type, vocab.term("Rule")):
         label = next((str(o) for o in g.objects(rule, RDFS.label)), "")
         comment = next((str(o) for o in g.objects(rule, RDFS.comment)), "")
         if not comment or norm(comment) == norm(label):
             offenders.append(str(rule))
     return sorted(offenders)
 
 
-def naming_violations(g: Graph) -> list[str]:
+def naming_violations(g: Graph, vocab: Vocabulary) -> list[str]:
     """Fields follow `<Owner>_<field>`; every other individual avoids the underscore that
     pattern reserves for fields (ontology/README.md's naming table)."""
     offenders = []
-    fields = set(g.subjects(RDF.type, URIRef(MON + "Field")))
+    fields = set(g.subjects(RDF.type, vocab.term("Field")))
     for term in fields:
         if not FIELD_NAME.match(_local(term)):
             offenders.append(f"{term} does not match the <Owner>_<field> pattern")
     non_fields = {
         s for s in g.subjects(RDF.type, None)
-        if str(s).startswith(APP) and s not in fields
+        if vocab.is_instance(s) and s not in fields
     }
     for term in non_fields:
         if "_" in _local(term):
             offenders.append(f"{term} uses an underscore, which is reserved for fields")
     return sorted(offenders)
 
 
 def _superclasses(g: Graph) -> dict[URIRef, set[URIRef]]:
     """Every class each class inherits from, transitively over rdfs:subClassOf.
 
-    Without this, mon:contains — declared over mon:InterfaceElement — would flag every
-    triple in the corpus, because nothing is ever typed as mon:InterfaceElement directly.
-    mon:Module, mon:View and mon:Section are all subclasses of it.
+    Without this, a containment predicate declared over a base interface-element class
+    would flag every triple in the corpus, because nothing is ever typed as that base
+    class directly — only its subclasses (a module, a view, a section, ...) are.
     """
     direct: dict[URIRef, set[URIRef]] = {}
     for sub, sup in g.subject_objects(RDFS.subClassOf):
         direct.setdefault(sub, set()).add(sup)
     closure: dict[URIRef, set[URIRef]] = {}
     for cls in direct:
         seen: set[URIRef] = set()
         queue = [cls]
         while queue:
             for parent in direct.get(queue.pop(), ()):
                 if parent not in seen:
                     seen.add(parent)
                     queue.append(parent)
         closure[cls] = seen
     return closure
 
 
-def domain_range_violations(g: Graph) -> list[str]:
+def domain_range_violations(g: Graph, vocab: Vocabulary) -> list[str]:
     """A declared predicate used with a subject or object of the wrong type.
 
     The five checks above catch invented terms. This catches the other half of ontology
-    conformance: a real mon: predicate asserted where the ontology says it cannot go —
-    mon:emptyState, whose domain is mon:InterfaceElement, hung on a mon:Field.
+    conformance: a real project-namespace predicate asserted where the ontology says it
+    cannot go — an emptyState property, whose domain is the base interface-element class,
+    hung on a field.
 
     Two tolerances keep it free of false positives. Untyped terms are skipped, because
     graph.dangling_terms already owns those and a term with no rdf:type cannot be judged
-    against a class. Ranges outside mon: are skipped, because xsd:string and rdfs:Literal
-    describe a literal's datatype, which is not a class an individual is typed with.
+    against a class. Ranges outside the project namespace are skipped, because xsd:string
+    and rdfs:Literal describe a literal's datatype, which is not a class an individual is
+    typed with.
     """
     supers = _superclasses(g)
 
     def types_of(term) -> set[URIRef]:
         found: set[URIRef] = set()
         for cls in g.objects(term, RDF.type):
             found.add(cls)
             found |= supers.get(cls, set())
         return found
 
     def describe(types: set[URIRef]) -> str:
-        return ", ".join(f"mon:{_local(t)}" for t in sorted(types, key=str))
+        return ", ".join(vocab.qname(t) for t in sorted(types, key=str))
 
     offenders = []
     for prop in g.subjects(RDF.type, RDF.Property):
-        if not str(prop).startswith(MON):
+        if not vocab.is_term(prop):
             continue
         domains = set(g.objects(prop, RDFS.domain))
-        ranges = {r for r in g.objects(prop, RDFS.range) if str(r).startswith(MON)}
+        ranges = {r for r in g.objects(prop, RDFS.range) if vocab.is_term(r)}
         if not domains and not ranges:
             continue
-        name = f"mon:{_local(prop)}"
+        name = vocab.qname(prop)
         for subject, obj in g.subject_objects(prop):
             subject_types = types_of(subject)
             if domains and subject_types and not (domains & subject_types):
                 offenders.append(
                     f"{subject} is {describe(subject_types)}, but {name} declares"
                     f" rdfs:domain {describe(domains)}"
                 )
             if not ranges or not isinstance(obj, URIRef):
                 continue
             object_types = types_of(obj)
             if object_types and not (ranges & object_types):
                 offenders.append(
                     f"{obj} is {describe(object_types)}, but {name} declares"
                     f" rdfs:range {describe(ranges)}"
                 )
     return sorted(offenders)
 
 
-def ungrounded_empty_states(paths: Paths, ids) -> list[str]:
-    """A mon:emptyState literal no sentence in the owning spec.md states.
+def ungrounded_empty_states(paths: Paths, vocab: Vocabulary, ids) -> list[str]:
+    """An emptyState literal no sentence in the owning spec.md states.
 
-    mon:emptyState is the one predicate whose value is a verbatim UI string rather than a
+    emptyState is the one predicate whose value is a verbatim UI string rather than a
     paraphrase, which makes "does the prose say this?" a question code can answer. The
     writer's graph-to-prose rule says a triple the prose does not support is removed; this
-    is that rule, mechanised, for the one predicate it can be mechanised for. mon:format is
-    paraphrase by design and mon:defaultsTo often is too — neither belongs here.
+    is that rule, mechanised, for the one predicate it can be mechanised for. format is
+    paraphrase by design and defaultsTo often is too — neither belongs here.
 
     The prose is hard-wrapped, so the comparison collapses runs of whitespace first. Without
-    that, a string straddling a line break reads as ungrounded when it is not: three of the
-    corpus's fifteen grounded literals are wrapped that way.
+    that, a string straddling a line break reads as ungrounded when it is not.
     """
     from knowledge.graph import load_spec_graph
     from knowledge.paths import spec_md
 
-    empty_state = URIRef(MON + "emptyState")
+    empty_state = vocab.term("emptyState")
     offenders = []
     for spec_id in ids:
         path = spec_md(paths, spec_id)
         if not path.is_file():
             continue
         prose = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
-        for subject, literal in load_spec_graph(paths, spec_id).subject_objects(empty_state):
+        for subject, literal in load_spec_graph(paths, vocab, spec_id).subject_objects(empty_state):
             if str(literal) not in prose:
                 offenders.append(
-                    f"{subject} has mon:emptyState {str(literal)!r},"
+                    f"{subject} has {vocab.prefix}:emptyState {str(literal)!r},"
                     f" which no sentence of {spec_id}/spec.md states"
                 )
     return sorted(offenders)
 
 
-def locally_redeclared_concepts(paths: Paths, ids) -> list[str]:
+def locally_redeclared_concepts(paths: Paths, vocab: Vocabulary, ids) -> list[str]:
     """A concept declared once on the `concepts` spec and referenced everywhere else is
     what turns independent specs into one connected graph. Declaring it again on some other
     spec is the same fact twice, free to drift apart from the original."""
     from knowledge.graph import load_spec_graph
 
-    concept = URIRef(MON + "Concept")
+    concept = vocab.term("Concept")
     offenders = []
     for spec_id in ids:
         if spec_id == "concepts":
             continue
-        g = load_spec_graph(paths, spec_id)
+        g = load_spec_graph(paths, vocab, spec_id)
         for term in g.subjects(RDF.type, concept):
             offenders.append(f"{term} declared on {spec_id!r} instead of concepts")
     return sorted(offenders)
diff --git a/src/knowledge/paths.py b/src/knowledge/paths.py
index da00b76..c57b85b 100644
--- a/src/knowledge/paths.py
+++ b/src/knowledge/paths.py
@@ -26,29 +26,29 @@ class Paths:
 
 
 def find_root(start: Path | None = None) -> Path:
     current = (start or Path.cwd()).resolve()
     for candidate in [current, *current.parents]:
         if (candidate / MARKER).is_file():
             return candidate
     raise RuntimeError(f"no {MARKER} found in {current} or any parent directory")
 
 
-def get_paths(start: Path | None = None) -> Paths:
+def get_paths(start: Path | None = None, ontology_file: str = "ontology.ttl") -> Paths:
     root = find_root(start)
     ontology = root / "ontology"
     metadata = root / ".metadata"
     return Paths(
         root=root,
         specs=root / "specs",
         ontology=ontology,
-        ontology_ttl=ontology / "monicords.ttl",
+        ontology_ttl=ontology / ontology_file,
         ontology_readme=ontology / "README.md",
         ontology_version=ontology / "VERSION",
         metadata=metadata,
         db=metadata / "knowledge.db",
         dump=metadata / "dump.sql",
     )
 
 
 def spec_dir(paths: Paths, spec_id: str) -> Path:
     return paths.specs / spec_id
diff --git a/src/knowledge/publish.py b/src/knowledge/publish.py
index 12ddc52..3947f09 100644
--- a/src/knowledge/publish.py
+++ b/src/knowledge/publish.py
@@ -4,21 +4,21 @@ Turtle is not inlined: the wiki carries prose, and the graph is available as an
 artifact. Only _Sidebar.md is generated — Home carries the product description and its own
 mon:Actor declarations, so it stays an ordinary spec and publishes like any other page.
 """
 
 from __future__ import annotations
 
 import re
 from pathlib import Path
 
 from knowledge import gitcmd
-from knowledge.graph import wiki_page_name
+from knowledge.graph import page_name
 from knowledge.paths import Paths
 
 FRONTMATTER = re.compile(r"\A---\n.*?\n---\n\s*", re.S)
 
 # Reading order, not alphabetical. Anything not named here is appended alphabetically, so a
 # new spec appears in the sidebar without this list having to be edited first.
 SIDEBAR_ORDER = [
     "home",
     "concepts",
     "onboarding",
@@ -140,24 +140,24 @@ def write_pages(conn, paths: Paths, out_dir: Path) -> list[str]:
         if not (directory / "spec.md").is_file():
             # A row without a folder — usually `rm -rf specs/<id>` without `knowledge
             # forget`. Skip it rather than crash: a publish that omits one page and says
             # so beats one that fails entirely and publishes nothing.
             print(
                 f"warning: {spec_id} has a row but no spec.md — skipping it. "
                 f"Run `knowledge forget {spec_id} --by <name>` once you're sure it's "
                 "meant to be gone."
             )
             continue
-        # scan() always populates wiki_page, so `page` here is always wiki_page_name(spec_id)
+        # scan() always populates wiki_page, so `page` here is always page_name(spec_id)
         # already and the `if` branch never fires today. It exists so a hand-set wiki_page
         # (page != spec_id) survives untransformed instead of being re-derived from the id.
-        name = f"{wiki_page_name(page) if page == spec_id else page}.md"
+        name = f"{page_name(page) if page == spec_id else page}.md"
         (out_dir / name).write_text(
             render_page(conn, paths, spec_id), encoding="utf-8", newline="\n"
         )
         written.append(name)
 
     (out_dir / "Ontology.md").write_text(
         paths.ontology_readme.read_text(encoding="utf-8"), encoding="utf-8", newline="\n"
     )
     written.append("Ontology.md")
 
diff --git a/src/knowledge/scan.py b/src/knowledge/scan.py
index c3049c8..d8d2290 100644
--- a/src/knowledge/scan.py
+++ b/src/knowledge/scan.py
@@ -8,21 +8,21 @@ claim about content that has since moved.
 """
 
 from __future__ import annotations
 
 import hashlib
 import re
 from dataclasses import dataclass, field
 from pathlib import Path
 
 from knowledge import db
-from knowledge.graph import wiki_page_name
+from knowledge.graph import page_name
 from knowledge.lifecycle import demote
 from knowledge.paths import Paths
 
 FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
 HEADING = re.compile(r"^# (.+)$", re.M)
 
 RESOURCE_KINDS = {
     ".csv": "data",
     ".json": "data",
     ".tsv": "data",
@@ -119,21 +119,21 @@ def scan(conn, paths: Paths) -> ScanReport:
         path = _relative(paths, directory)
         title = read_title(md, spec_id)
         md_hash = file_hash(md)
         ttl_hash = file_hash(directory / "spec.ttl")
         timestamp = db.now()
 
         if spec_id not in known:
             conn.execute(
                 "INSERT INTO spec (id,title,path,status,md_hash,ttl_hash,publishes_to_wiki,"
                 "wiki_page,created_at,updated_at) VALUES (?,?,?,'draft',?,?,1,?,?,?)",
-                (spec_id, title, path, md_hash, ttl_hash, wiki_page_name(spec_id),
+                (spec_id, title, path, md_hash, ttl_hash, page_name(spec_id),
                  timestamp, timestamp),
             )
             db.record_event(conn, spec_id, "created", "scan", None)
             report.added.append(spec_id)
         else:
             (known_path, known_title, known_md_hash, known_ttl_hash,
              status, modeled_md_hash, modeled_ttl_hash) = known[spec_id]
             if known_path != path:
                 report.moved.append((spec_id, known_path, path))
                 db.record_event(conn, spec_id, "moved", "scan", f"{known_path} -> {path}")
diff --git a/tests/conftest.py b/tests/conftest.py
index 5b8a159..4e3df50 100644
--- a/tests/conftest.py
+++ b/tests/conftest.py
@@ -21,141 +21,207 @@ def isolate_git_env(monkeypatch):
     into the invoking repository's index.
 
     That is not hypothetical — it is what made these tests pass under `pytest` and error
     under the pre-push hook. Scrubbing here rather than in the hook keeps the tests correct
     however they are reached: a hook, a CI step, a rebase, `git bisect run`.
     """
     for key in list(os.environ):
         if key.startswith("GIT_") and key not in gitcmd.ENV_KEPT:
             monkeypatch.delenv(key, raising=False)
 
-# Every term below is copied from ontology/monicords.ttl with the same rdf:type and the same
-# rdfs:domain / rdfs:range, so a test written against this ontology tests the real vocabulary.
-# The subClassOf edges and the domain/range declarations are what domain_range_violations reads.
+# A generic vocabulary, unrelated to any real project, so a test written against it tests
+# the mechanism rather than any one domain. The subClassOf edges and the domain/range
+# declarations are what domain_range_violations reads.
 ONTOLOGY = """\
-@prefix mon:     <https://monicords.com/ontology#> .
-@prefix app:     <https://monicords.com/id/> .
+@prefix ex:      <https://example.test/ontology#> .
+@prefix app:     <https://example.test/id/> .
 @prefix rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
 @prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
 @prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .
 @prefix skos:    <http://www.w3.org/2004/02/skos/core#> .
 @prefix dcterms: <http://purl.org/dc/terms/> .
 
-mon:InterfaceElement a rdfs:Class ; rdfs:label "Interface element"@en .
-mon:Module a rdfs:Class ; rdfs:subClassOf mon:InterfaceElement ; rdfs:label "Module"@en .
-mon:View a rdfs:Class ; rdfs:subClassOf mon:InterfaceElement ; rdfs:label "View"@en .
-mon:Section a rdfs:Class ; rdfs:subClassOf mon:InterfaceElement ; rdfs:label "Section"@en .
-mon:Field a rdfs:Class ; rdfs:label "Field"@en .
-mon:Action a rdfs:Class ; rdfs:label "Action"@en .
-mon:Concept a rdfs:Class ; rdfs:label "Domain concept"@en .
-mon:Rule a rdfs:Class ; rdfs:label "Rule"@en .
-
-mon:contains a rdf:Property ; rdfs:label "contains"@en ;
-    rdfs:domain mon:InterfaceElement ; rdfs:range mon:InterfaceElement .
-mon:partOf a rdf:Property ; rdfs:label "part of"@en ;
-    rdfs:domain mon:InterfaceElement ; rdfs:range mon:InterfaceElement .
-mon:displays a rdf:Property ; rdfs:label "displays"@en ;
-    rdfs:domain mon:InterfaceElement ; rdfs:range mon:Field .
-mon:scopedTo a rdf:Property ; rdfs:label "scoped to"@en ;
-    rdfs:domain mon:InterfaceElement ; rdfs:range mon:Concept .
-mon:appliesTo a rdf:Property ; rdfs:label "applies to"@en ; rdfs:domain mon:Rule .
-mon:relatesTo a rdf:Property ; rdfs:label "relates to"@en ;
-    rdfs:domain mon:Concept ; rdfs:range mon:Concept .
-mon:route a rdf:Property ; rdfs:label "route"@en ;
-    rdfs:domain mon:View ; rdfs:range xsd:string .
-mon:endpoint a rdf:Property ; rdfs:label "endpoint"@en ;
-    rdfs:domain mon:Action ; rdfs:range xsd:string .
-mon:emptyState a rdf:Property ; rdfs:label "empty state"@en ;
-    rdfs:domain mon:InterfaceElement ; rdfs:range xsd:string .
-mon:format a rdf:Property ; rdfs:label "format"@en ;
-    rdfs:domain mon:Field ; rdfs:range xsd:string .
+ex:InterfaceElement a rdfs:Class ; rdfs:label "Interface element"@en .
+ex:Module a rdfs:Class ; rdfs:subClassOf ex:InterfaceElement ; rdfs:label "Module"@en .
+ex:View a rdfs:Class ; rdfs:subClassOf ex:InterfaceElement ; rdfs:label "View"@en .
+ex:Section a rdfs:Class ; rdfs:subClassOf ex:InterfaceElement ; rdfs:label "Section"@en .
+ex:Field a rdfs:Class ; rdfs:label "Field"@en .
+ex:Action a rdfs:Class ; rdfs:label "Action"@en .
+ex:Concept a rdfs:Class ; rdfs:label "Domain concept"@en .
+ex:Rule a rdfs:Class ; rdfs:label "Rule"@en .
+
+ex:contains a rdf:Property ; rdfs:label "contains"@en ;
+    rdfs:domain ex:InterfaceElement ; rdfs:range ex:InterfaceElement .
+ex:partOf a rdf:Property ; rdfs:label "part of"@en ;
+    rdfs:domain ex:InterfaceElement ; rdfs:range ex:InterfaceElement .
+ex:displays a rdf:Property ; rdfs:label "displays"@en ;
+    rdfs:domain ex:InterfaceElement ; rdfs:range ex:Field .
+ex:scopedTo a rdf:Property ; rdfs:label "scoped to"@en ;
+    rdfs:domain ex:InterfaceElement ; rdfs:range ex:Concept .
+ex:appliesTo a rdf:Property ; rdfs:label "applies to"@en ; rdfs:domain ex:Rule .
+ex:relatesTo a rdf:Property ; rdfs:label "relates to"@en ;
+    rdfs:domain ex:Concept ; rdfs:range ex:Concept .
+ex:route a rdf:Property ; rdfs:label "route"@en ;
+    rdfs:domain ex:View ; rdfs:range xsd:string .
+ex:endpoint a rdf:Property ; rdfs:label "endpoint"@en ;
+    rdfs:domain ex:Action ; rdfs:range xsd:string .
+ex:emptyState a rdf:Property ; rdfs:label "empty state"@en ;
+    rdfs:domain ex:InterfaceElement ; rdfs:range xsd:string .
+ex:format a rdf:Property ; rdfs:label "format"@en ;
+    rdfs:domain ex:Field ; rdfs:range xsd:string .
 """
 
 ASSETS_TTL = """\
-app:Assets a mon:View ;
+app:Assets a ex:View ;
     rdfs:label   "Assets"@en ;
-    mon:route    "/platform/assets" ;
-    mon:scopedTo app:Workspace .
+    ex:route     "/platform/assets" ;
+    ex:scopedTo  app:Workspace .
 """
 
 CONCEPTS_TTL = """\
-app:Workspace a mon:Concept ;
+app:Workspace a ex:Concept ;
     rdfs:label "Workspace"@en .
 """
 
+CONFIG_TOML = """\
+[project]
+name = "Example"
+
+[vocabulary]
+ontology_file = "ontology.ttl"
+namespace = "https://example.test/ontology#"
+instances = "https://example.test/id/"
+prefix = "ex"
+instance_prefix = "app"
+rule_class = "Rule"
+concept_class = "Concept"
+concept_spec = "concepts"
+field_class = "Field"
+field_name_pattern = "^[A-Z][A-Za-z0-9]*_[a-z][A-Za-z0-9]*$"
+underscore_reserved = true
+functional_properties = ["route", "editable", "required", "viewport", "defaultsTo"]
+verbatim_string_properties = ["emptyState"]
+
+[repo]
+code_repo = "../code"
+
+[dependencies]
+route_property = "route"
+endpoint_property = "endpoint"
+route_glob = "app/**/{segments}/page.tsx"
+endpoint_glob = "app/{path}/**/route.ts"
+absorbed_prefixes = ["platform"]
+
+[publish]
+target = "github-wiki"
+remote = "https://example.com/x.wiki.git"
+"""
+
 
-def write_spec(root, spec_id, ttl, prose="Some prose.\n"):
+def _write_spec(root, spec_id, ttl, prose="Some prose.\n"):
     directory = root / "specs" / spec_id
     directory.mkdir(parents=True, exist_ok=True)
     (directory / "spec.md").write_text(
         f"---\nid: {spec_id}\n---\n\n# {spec_id.replace('-', ' ').title()}\n\n{prose}",
         encoding="utf-8",
     )
     (directory / "spec.ttl").write_text(ttl, encoding="utf-8")
     return directory
 
 
-# knowledge.toml now requires a full [vocabulary] table (Task 2). These stay the monicords
-# namespaces on purpose — graph.py still has MON as a module constant at this point, so a
-# fixture using different namespaces would break every test that parses ONTOLOGY/ASSETS_TTL
-# above. Task 3 rewrites the fixture and the constant together.
+@pytest.fixture
+def write_spec():
+    """Tasks 4-7 request this as a fixture rather than importing it."""
+    return _write_spec
+
+
+# A separate template from CONFIG_TOML above: knowledge.toml's [repo]/[publish] values
+# overridden for one test, with the rest of the vocabulary/dependencies configuration a
+# working repository still needs. Kept distinct from the fixture ontology's namespace/prefix
+# so a caller only overrides what a given test actually cares about.
 KNOWLEDGE_TOML = """\
 [project]
-name = "Monicords"
+name = "Example"
 
 [vocabulary]
-ontology_file = "monicords.ttl"
-namespace = "https://monicords.com/ontology#"
-instances = "https://monicords.com/id/"
-prefix = "mon"
+ontology_file = "ontology.ttl"
+namespace = "https://example.test/ontology#"
+instances = "https://example.test/id/"
+prefix = "ex"
 instance_prefix = "app"
+rule_class = "Rule"
+concept_class = "Concept"
+concept_spec = "concepts"
+field_class = "Field"
+field_name_pattern = "^[A-Z][A-Za-z0-9]*_[a-z][A-Za-z0-9]*$"
+underscore_reserved = true
+functional_properties = ["route", "editable", "required", "viewport", "defaultsTo"]
+verbatim_string_properties = ["emptyState"]
 
 [repo]
 code_repo = "{code_repo}"
 
+[dependencies]
+route_property = "route"
+endpoint_property = "endpoint"
+route_glob = "app/**/{{segments}}/page.tsx"
+endpoint_glob = "app/{{path}}/**/route.ts"
+absorbed_prefixes = ["platform"]
+
 [publish]
 remote = "{remote}"
 """
 
 
 def write_knowledge_toml(root, *, code_repo="../code", remote="https://example.com/x.wiki.git"):
     (root / "knowledge.toml").write_text(
         KNOWLEDGE_TOML.format(code_repo=code_repo, remote=remote), encoding="utf-8"
     )
     return root
 
 
 def make_config(code_repo, remote="https://example.com/x.wiki.git"):
     """A Config for tests that exercise lifecycle/deps functions directly, without going
-    through load_config. Same monicords vocabulary as KNOWLEDGE_TOML above."""
+    through load_config. Same example vocabulary as KNOWLEDGE_TOML above."""
     return Config(
-        project_name="Monicords",
+        project_name="Example",
         vocabulary=Vocabulary(
-            ontology_file="monicords.ttl",
-            namespace="https://monicords.com/ontology#",
-            instances="https://monicords.com/id/",
-            prefix="mon",
+            ontology_file="ontology.ttl",
+            namespace="https://example.test/ontology#",
+            instances="https://example.test/id/",
+            prefix="ex",
             instance_prefix="app",
             checks=Checks(),
         ),
         surveys=(),
         code_repo=code_repo,
         dependencies=Dependencies(),
         publish=Publish(remote=remote),
         unconfigured=False,
     )
 
 
 @pytest.fixture
 def repo(tmp_path):
     """A knowledge repository with an ontology and two specs."""
-    write_knowledge_toml(tmp_path)
+    (tmp_path / "knowledge.toml").write_text(CONFIG_TOML, encoding="utf-8")
     ontology = tmp_path / "ontology"
     ontology.mkdir()
-    (ontology / "monicords.ttl").write_text(ONTOLOGY, encoding="utf-8")
+    (ontology / "ontology.ttl").write_text(ONTOLOGY, encoding="utf-8")
     (ontology / "README.md").write_text("# Ontology\n\nThe vocabulary.\n", encoding="utf-8")
     (ontology / "VERSION").write_text("1.0.0\n", encoding="utf-8")
     (tmp_path / ".metadata").mkdir()
 
-    write_spec(tmp_path, "assets", ASSETS_TTL, "The Assets screen. See [Concepts](Concepts).\n")
-    write_spec(tmp_path, "concepts", CONCEPTS_TTL)
+    _write_spec(tmp_path, "assets", ASSETS_TTL, "The Assets screen. See [Concepts](Concepts).\n")
+    _write_spec(tmp_path, "concepts", CONCEPTS_TTL)
     return paths_mod.get_paths(tmp_path)
+
+
+@pytest.fixture
+def config(repo):
+    from knowledge.config import load_config
+    return load_config(repo.root)
+
+
+@pytest.fixture
+def repo_with_vocab(repo, config):
+    return repo, config.vocabulary
diff --git a/tests/test_cli_read.py b/tests/test_cli_read.py
index 91fb53d..740598b 100644
--- a/tests/test_cli_read.py
+++ b/tests/test_cli_read.py
@@ -7,21 +7,21 @@ from knowledge import cli, db, lifecycle, scan
 def seeded(repo, monkeypatch):
     monkeypatch.chdir(repo.root)
     conn = db.connect(repo)
     scan.scan(conn, repo)
     conn.execute(
         "UPDATE spec SET status='verified', verified_by='jesus',"
         " verified_at='2026-01-01T00:00:00Z' WHERE id='concepts'"
     )
     conn.execute(
         "INSERT INTO open_question (spec_id, claim_iri, question, asked_by, asked_at, status)"
-        " VALUES ('assets','https://monicords.com/id/Assets','Can an amount be negative?',"
+        " VALUES ('assets','https://example.test/id/Assets','Can an amount be negative?',"
         "'interviewer','2026-01-01T00:00:00Z','open')"
     )
     db.save(conn, repo)
     return repo
 
 
 def run(argv):
     return cli.build_parser().parse_args(argv)
 
 
@@ -122,21 +122,21 @@ def test_questions_lists_open_ones(seeded, capsys):
 def test_validate_passes_on_a_clean_graph(seeded, capsys):
     args = run(["validate", "--strict"])
     assert args.handler(args) == 0
     assert "no dangling references" in capsys.readouterr().out
 
 
 def test_graph_writes_a_turtle_file(seeded, tmp_path, capsys):
     out = tmp_path / "g.ttl"
     args = run(["graph", "-o", str(out)])
     assert args.handler(args) == 0
-    assert "@prefix mon:" in out.read_text(encoding="utf-8")
+    assert "@prefix ex:" in out.read_text(encoding="utf-8")
     assert b"\r" not in out.read_bytes()
 
 
 def test_graph_defaults_to_verified_specs_only(seeded, tmp_path):
     out = tmp_path / "verified.ttl"
     args = run(["graph", "-o", str(out)])
     args.handler(args)
     text = out.read_text(encoding="utf-8")
     assert "Workspace" in text
     assert "/platform/assets" not in text
@@ -146,17 +146,16 @@ def test_graph_defaults_to_verified_specs_only(seeded, tmp_path):
     args.handler(args)
     assert "/platform/assets" in both.read_text(encoding="utf-8")
 
 
 def test_contradictions_reports_none_on_a_clean_graph(seeded, capsys):
     args = run(["contradictions", "--include-drafts"])
     assert args.handler(args) == 0
     assert "no mechanical contradictions found" in capsys.readouterr().out
 
 
-def test_contradictions_reports_a_functional_conflict(seeded, capsys):
-    from tests.conftest import write_spec
+def test_contradictions_reports_a_functional_conflict(seeded, write_spec, capsys):
     write_spec(seeded.root, "duplicate-route",
-               'app:Assets a mon:View ; mon:route "/somewhere-else" .\n')
+               'app:Assets a ex:View ; ex:route "/somewhere-else" .\n')
     args = run(["contradictions", "--include-drafts"])
     args.handler(args)
     assert "route" in capsys.readouterr().out
diff --git a/tests/test_contradictions.py b/tests/test_contradictions.py
index 7d146b0..0ffc9c0 100644
--- a/tests/test_contradictions.py
+++ b/tests/test_contradictions.py
@@ -1,16 +1,16 @@
 from knowledge import contradictions, graph
-from tests.conftest import write_spec
 
 
-def test_functional_conflicts_finds_two_routes_on_one_view(repo):
+def test_functional_conflicts_finds_two_routes_on_one_view(repo, config, write_spec):
     write_spec(repo.root, "duplicate-route",
-               'app:Assets a mon:View ; mon:route "/somewhere-else" .\n')
-    g = graph.load_graph(repo)
-    conflicts = contradictions.functional_conflicts(g)
+               'app:Assets a ex:View ; ex:route "/somewhere-else" .\n')
+    g = graph.load_graph(repo, config.vocabulary)
+    conflicts = contradictions.functional_conflicts(g, config.vocabulary)
     assert (
-        "https://monicords.com/id/Assets", "route", ["/platform/assets", "/somewhere-else"]
+        "https://example.test/id/Assets", "route", ["/platform/assets", "/somewhere-else"]
     ) in conflicts
 
 
-def test_functional_conflicts_is_empty_for_a_single_route(repo):
-    assert contradictions.functional_conflicts(graph.load_graph(repo)) == []
+def test_functional_conflicts_is_empty_for_a_single_route(repo, config):
+    g = graph.load_graph(repo, config.vocabulary)
+    assert contradictions.functional_conflicts(g, config.vocabulary) == []
diff --git a/tests/test_deps.py b/tests/test_deps.py
index 5ea75be..da0b6a6 100644
--- a/tests/test_deps.py
+++ b/tests/test_deps.py
@@ -1,16 +1,16 @@
 import subprocess
 
 import pytest
 
 from knowledge import db, deps, lifecycle, scan
-from tests.conftest import make_config, write_spec
+from tests.conftest import make_config
 
 
 def test_route_to_glob_ignores_route_groups():
     # /platform/assets lives at app/platform/(menuLayout)/assets/page.tsx
     assert deps.route_to_glob("/platform/assets") == "app/**/assets/page.tsx"
     assert deps.route_to_glob("/landing") == "app/**/landing/page.tsx"
     assert deps.route_to_glob("/platform/expenses/calendar") == (
         "app/**/expenses/calendar/page.tsx"
     )
 
@@ -34,33 +34,33 @@ def test_endpoint_to_glob():
     assert deps.endpoint_to_glob("/api/loans-out/summary") == (
         "app/api/loans-out/summary/**/route.ts"
     )
 
 
 def test_an_endpoint_glob_matches_a_route_handler_directly_beneath_it():
     globs = {deps.endpoint_to_glob("/api/cron")}
     assert deps.matches(globs, ["app/api/cron/route.ts"]) == ["app/api/cron/route.ts"]
 
 
-def test_derived_globs_come_from_the_specs_own_triples(repo):
-    assert deps.derived_globs(repo, "assets") == {"app/**/assets/page.tsx"}
-    assert deps.derived_globs(repo, "concepts") == set()
+def test_derived_globs_come_from_the_specs_own_triples(repo, config):
+    assert deps.derived_globs(repo, config.vocabulary, "assets") == {"app/**/assets/page.tsx"}
+    assert deps.derived_globs(repo, config.vocabulary, "concepts") == set()
 
 
-def test_manual_globs_are_added_to_derived_ones(repo):
+def test_manual_globs_are_added_to_derived_ones(repo, config):
     conn = db.connect(repo)
     scan.scan(conn, repo)
     conn.execute(
         "INSERT INTO spec_dependency (spec_id, glob, note)"
         " VALUES ('assets','modules/server/submodules/assets/**','the service layer')"
     )
-    assert deps.spec_globs(conn, repo, "assets") == {
+    assert deps.spec_globs(conn, repo, config.vocabulary, "assets") == {
         "app/**/assets/page.tsx",
         "modules/server/submodules/assets/**",
     }
 
 
 def test_matches_uses_full_glob_semantics():
     globs = {"app/**/assets/page.tsx", "modules/server/submodules/assets/**"}
     changed = [
         "app/platform/(menuLayout)/assets/page.tsx",
         "modules/server/submodules/assets/services/create/index.ts",
@@ -180,28 +180,28 @@ def test_check_accepts_a_code_repo_override(repo, code_repo, tmp_path):
 
     page = code_repo / "app" / "platform" / "(menuLayout)" / "assets" / "page.tsx"
     page.write_text("changed\n")
     subprocess.run(["git", "-C", str(code_repo), "commit", "-am", "change"], check=True,
                    capture_output=True)
 
     findings = deps.check(conn, repo, config, demote=True, code_repo=code_repo)
     assert findings == [("assets", ["app/platform/(menuLayout)/assets/page.tsx"])]
 
 
-def test_uncheckable_lists_a_verified_spec_with_no_dependencies(repo):
+def test_uncheckable_lists_a_verified_spec_with_no_dependencies(repo, config):
     conn = db.connect(repo)
     scan.scan(conn, repo)
     conn.execute("UPDATE spec SET status='verified' WHERE id IN ('assets','concepts')")
-    # assets has a derived glob from its mon:route; concepts has neither a route/endpoint
-    # nor a manual dependency, so only concepts is uncheckable.
-    assert deps.uncheckable(conn, repo) == ["concepts"]
+    # assets has a derived glob from its route; concepts has neither a route/endpoint nor a
+    # manual dependency, so only concepts is uncheckable.
+    assert deps.uncheckable(conn, repo, config.vocabulary) == ["concepts"]
 
 
-def test_uncheckable_excludes_a_spec_once_it_has_a_manual_glob(repo):
+def test_uncheckable_excludes_a_spec_once_it_has_a_manual_glob(repo, config):
     conn = db.connect(repo)
     scan.scan(conn, repo)
     conn.execute("UPDATE spec SET status='verified' WHERE id IN ('assets','concepts')")
     conn.execute(
         "INSERT INTO spec_dependency (spec_id, glob, note)"
         " VALUES ('concepts','prisma/schema.prisma','the data model')"
     )
-    assert deps.uncheckable(conn, repo) == []
+    assert deps.uncheckable(conn, repo, config.vocabulary) == []
diff --git a/tests/test_graph.py b/tests/test_graph.py
index c0d00df..c0b78af 100644
--- a/tests/test_graph.py
+++ b/tests/test_graph.py
@@ -1,57 +1,95 @@
 from knowledge import graph
-from tests.conftest import write_spec
+from knowledge.vocab import Vocabulary
 
 
-def test_the_graph_parses_and_holds_both_specs(repo):
-    g = graph.load_graph(repo)
-    labels = {row[0] for row in graph.run_query(g, "SELECT ?l WHERE { ?s rdfs:label ?l }")}
+def test_the_graph_parses_and_holds_both_specs(repo, config):
+    g = graph.load_graph(repo, config.vocabulary)
+    labels = {row[0] for row in graph.run_query(g, config.vocabulary,
+                                                 "SELECT ?l WHERE { ?s rdfs:label ?l }")}
     assert "Assets" in labels
     assert "Workspace" in labels
 
 
-def test_load_graph_can_be_limited_to_some_specs(repo):
-    g = graph.load_graph(repo, ["assets"])
-    routes = graph.run_query(g, "SELECT ?r WHERE { ?s mon:route ?r }")
+def test_load_graph_can_be_limited_to_some_specs(repo, config):
+    g = graph.load_graph(repo, config.vocabulary, ["assets"])
+    routes = graph.run_query(g, config.vocabulary, "SELECT ?r WHERE { ?s ex:route ?r }")
     assert routes == [("/platform/assets",)]
-    labels = {row[0] for row in graph.run_query(g, "SELECT ?l WHERE { ?s rdfs:label ?l }")}
+    labels = {row[0] for row in graph.run_query(g, config.vocabulary,
+                                                 "SELECT ?l WHERE { ?s rdfs:label ?l }")}
     assert "Workspace" not in labels
 
 
 def test_spec_ids_are_sorted_folder_names(repo):
     assert graph.spec_ids(repo) == ["assets", "concepts"]
 
 
-def test_dangling_terms_finds_a_referenced_but_undeclared_node(repo):
-    write_spec(repo.root, "orphan", 'app:Orphan a mon:View ; mon:relatesTo app:NeverDeclared .\n')
-    g = graph.load_graph(repo)
-    assert "https://monicords.com/id/NeverDeclared" in graph.dangling_terms(g)
+def test_dangling_terms_finds_a_referenced_but_undeclared_node(repo, config, write_spec):
+    write_spec(repo.root, "orphan", 'app:Orphan a ex:View ; ex:relatesTo app:NeverDeclared .\n')
+    g = graph.load_graph(repo, config.vocabulary)
+    assert "https://example.test/id/NeverDeclared" in graph.dangling_terms(g, config.vocabulary)
 
 
-def test_dangling_terms_is_empty_for_a_complete_graph(repo):
-    assert graph.dangling_terms(graph.load_graph(repo)) == []
+def test_dangling_terms_is_empty_for_a_complete_graph(repo, config):
+    g = graph.load_graph(repo, config.vocabulary)
+    assert graph.dangling_terms(g, config.vocabulary) == []
 
 
-def test_wiki_page_name_round_trips_every_shape():
-    assert graph.wiki_page_name("home") == "Home"
-    assert graph.wiki_page_name("loans-out") == "Loans-Out"
-    assert graph.wiki_page_name("expenses-calendar") == "Expenses-Calendar"
-    assert graph.wiki_page_name("profile-account") == "Profile-Account"
+def test_page_name_round_trips_every_shape():
+    assert graph.page_name("home") == "Home"
+    assert graph.page_name("loans-out") == "Loans-Out"
+    assert graph.page_name("expenses-calendar") == "Expenses-Calendar"
+    assert graph.page_name("profile-account") == "Profile-Account"
 
 
-def test_broken_links_reports_a_link_to_a_page_that_does_not_exist(repo):
-    write_spec(repo.root, "lonely", "app:Lonely a mon:View ; rdfs:label \"Lonely\"@en .\n",
+def test_broken_links_reports_a_link_to_a_page_that_does_not_exist(repo, write_spec):
+    write_spec(repo.root, "lonely", "app:Lonely a ex:View ; rdfs:label \"Lonely\"@en .\n",
                "Points at [Nowhere](Nowhere).\n")
     broken = graph.broken_links(repo, graph.spec_ids(repo))
     assert any("Nowhere" in entry for entry in broken)
 
 
-def test_broken_links_accepts_a_section_anchor_and_the_ontology_page(repo):
-    write_spec(repo.root, "anchored", "app:Anchored a mon:View ; rdfs:label \"A\"@en .\n",
+def test_broken_links_accepts_a_section_anchor_and_the_ontology_page(repo, write_spec):
+    write_spec(repo.root, "anchored", "app:Anchored a ex:View ; rdfs:label \"A\"@en .\n",
                "See [workspace](Concepts#workspace) and [Ontology](Ontology).\n")
     assert graph.broken_links(repo, graph.spec_ids(repo)) == []
 
 
-def test_the_serialised_graph_carries_the_mon_and_app_prefixes(repo):
-    text = graph.load_graph(repo).serialize(format="turtle")
-    assert "@prefix mon:" in text
+def test_the_serialised_graph_carries_the_configured_prefixes(repo, config):
+    text = graph.load_graph(repo, config.vocabulary).serialize(format="turtle")
+    assert "@prefix ex:" in text
     assert "@prefix app:" in text
+
+
+def test_load_graph_binds_the_configured_prefixes(repo_with_vocab):
+    paths, vocab = repo_with_vocab
+    g = graph.load_graph(paths, vocab)
+    bound = {prefix: str(iri) for prefix, iri in g.namespaces()}
+    assert bound[vocab.prefix] == vocab.namespace
+    assert bound[vocab.instance_prefix] == vocab.instances
+
+
+def test_run_query_prepends_the_configured_prefixes(repo_with_vocab):
+    paths, vocab = repo_with_vocab
+    g = graph.load_graph(paths, vocab)
+    rows = graph.run_query(g, vocab, "SELECT ?l WHERE { ?s a ex:View ; rdfs:label ?l }")
+    assert rows == [("Assets",)]
+
+
+def test_dangling_terms_uses_the_configured_namespaces(repo_with_vocab):
+    paths, vocab = repo_with_vocab
+    g = graph.load_graph(paths, vocab)
+    assert graph.dangling_terms(g, vocab) == []
+
+
+def test_surveys_come_from_the_config(tmp_path):
+    from knowledge.config import Config, Dependencies, Publish, Survey
+    config = Config(
+        project_name="Example",
+        vocabulary=Vocabulary("ontology.ttl", "https://e.test/o#", "https://e.test/id/", "ex", "app"),
+        surveys=(Survey(name="everything", query="SELECT ?s WHERE { ?s ?p ?o }"),),
+        code_repo=None,
+        dependencies=Dependencies(),
+        publish=Publish(),
+        unconfigured=False,
+    )
+    assert graph.surveys(config) == [("everything", "SELECT ?s WHERE { ?s ?p ?o }")]
diff --git a/tests/test_lint.py b/tests/test_lint.py
index d1e73b3..2c94f2f 100644
--- a/tests/test_lint.py
+++ b/tests/test_lint.py
@@ -1,180 +1,188 @@
 from knowledge import graph, lint
-from tests.conftest import write_spec
 
 
-def test_invented_predicates_finds_an_undeclared_mon_property(repo):
-    write_spec(repo.root, "typo", 'app:Assets a mon:View ; mon:rout "/x" .\n')
-    g = graph.load_graph(repo)
-    assert "https://monicords.com/ontology#rout" in lint.invented_predicates(g)
+def test_invented_predicates_finds_an_undeclared_property(repo, config, write_spec):
+    write_spec(repo.root, "typo", 'app:Assets a ex:View ; ex:rout "/x" .\n')
+    g = graph.load_graph(repo, config.vocabulary)
+    assert "https://example.test/ontology#rout" in lint.invented_predicates(g, config.vocabulary)
 
 
-def test_invented_predicates_is_empty_for_a_clean_graph(repo):
-    assert lint.invented_predicates(graph.load_graph(repo)) == []
+def test_invented_predicates_is_empty_for_a_clean_graph(repo, config):
+    g = graph.load_graph(repo, config.vocabulary)
+    assert lint.invented_predicates(g, config.vocabulary) == []
 
 
-def test_invented_types_finds_an_undeclared_mon_class(repo):
-    write_spec(repo.root, "typo", 'app:Thing a mon:Widget ; rdfs:label "Thing"@en .\n')
-    g = graph.load_graph(repo)
-    assert "https://monicords.com/ontology#Widget" in lint.invented_types(g)
+def test_invented_types_finds_an_undeclared_class(repo, config, write_spec):
+    write_spec(repo.root, "typo", 'app:Thing a ex:Widget ; rdfs:label "Thing"@en .\n')
+    g = graph.load_graph(repo, config.vocabulary)
+    assert "https://example.test/ontology#Widget" in lint.invented_types(g, config.vocabulary)
 
 
-def test_restated_rule_comments_flags_a_comment_that_repeats_the_label(repo):
+def test_restated_rule_comments_flags_a_comment_that_repeats_the_label(repo, config, write_spec):
     write_spec(repo.root, "lazy", """\
-app:LazyRule a mon:Rule ;
+app:LazyRule a ex:Rule ;
     rdfs:label   "Amount is required"@en ;
     rdfs:comment "Amount is required."@en .
 """)
-    g = graph.load_graph(repo)
-    assert "https://monicords.com/id/LazyRule" in lint.restated_rule_comments(g)
+    g = graph.load_graph(repo, config.vocabulary)
+    assert "https://example.test/id/LazyRule" in lint.restated_rule_comments(g, config.vocabulary)
 
 
-def test_restated_rule_comments_accepts_a_comment_that_explains_why(repo):
+def test_restated_rule_comments_accepts_a_comment_that_explains_why(repo, config, write_spec):
     write_spec(repo.root, "explained", """\
-app:ExplainedRule a mon:Rule ;
+app:ExplainedRule a ex:Rule ;
     rdfs:label   "Amount is required"@en ;
     rdfs:comment "An asset with no amount cannot be summed into any total."@en .
 """)
-    g = graph.load_graph(repo)
-    assert "https://monicords.com/id/ExplainedRule" not in lint.restated_rule_comments(g)
+    g = graph.load_graph(repo, config.vocabulary)
+    assert ("https://example.test/id/ExplainedRule"
+            not in lint.restated_rule_comments(g, config.vocabulary))
 
 
-def test_restated_rule_comments_flags_a_missing_comment(repo):
-    write_spec(repo.root, "silent", 'app:SilentRule a mon:Rule ; rdfs:label "No note"@en .\n')
-    g = graph.load_graph(repo)
-    assert "https://monicords.com/id/SilentRule" in lint.restated_rule_comments(g)
+def test_restated_rule_comments_flags_a_missing_comment(repo, config, write_spec):
+    write_spec(repo.root, "silent", 'app:SilentRule a ex:Rule ; rdfs:label "No note"@en .\n')
+    g = graph.load_graph(repo, config.vocabulary)
+    assert "https://example.test/id/SilentRule" in lint.restated_rule_comments(g, config.vocabulary)
 
 
-def test_naming_violations_accepts_the_documented_field_pattern(repo):
+def test_naming_violations_accepts_the_documented_field_pattern(repo, config, write_spec):
     write_spec(repo.root, "goodfield",
-               'app:Asset_name a mon:Field ; rdfs:label "Name"@en .\n')
-    g = graph.load_graph(repo)
-    assert lint.naming_violations(g) == []
+               'app:Asset_name a ex:Field ; rdfs:label "Name"@en .\n')
+    g = graph.load_graph(repo, config.vocabulary)
+    assert lint.naming_violations(g, config.vocabulary) == []
 
 
-def test_naming_violations_flags_a_field_missing_its_owner_prefix(repo):
-    write_spec(repo.root, "badfield", 'app:name a mon:Field ; rdfs:label "Name"@en .\n')
-    g = graph.load_graph(repo)
-    assert any("app:name" in msg or "id/name" in msg for msg in lint.naming_violations(g))
+def test_naming_violations_flags_a_field_missing_its_owner_prefix(repo, config, write_spec):
+    write_spec(repo.root, "badfield", 'app:name a ex:Field ; rdfs:label "Name"@en .\n')
+    g = graph.load_graph(repo, config.vocabulary)
+    assert any(
+        "app:name" in msg or "id/name" in msg
+        for msg in lint.naming_violations(g, config.vocabulary)
+    )
 
 
-def test_naming_violations_flags_an_underscore_outside_a_field(repo):
+def test_naming_violations_flags_an_underscore_outside_a_field(repo, config, write_spec):
     write_spec(repo.root, "badview",
-               'app:Assets_List a mon:View ; rdfs:label "Assets List"@en .\n')
-    g = graph.load_graph(repo)
-    assert any("Assets_List" in msg for msg in lint.naming_violations(g))
+               'app:Assets_List a ex:View ; rdfs:label "Assets List"@en .\n')
+    g = graph.load_graph(repo, config.vocabulary)
+    assert any("Assets_List" in msg for msg in lint.naming_violations(g, config.vocabulary))
 
 
-def test_locally_redeclared_concepts_flags_a_concept_declared_outside_its_home_spec(repo):
+def test_locally_redeclared_concepts_flags_a_concept_declared_outside_its_home_spec(
+    repo, config, write_spec
+):
     write_spec(repo.root, "duplicate",
-               'app:Workspace a mon:Concept ; rdfs:label "Workspace"@en .\n')
+               'app:Workspace a ex:Concept ; rdfs:label "Workspace"@en .\n')
     ids = graph.spec_ids(repo)
-    offenders = lint.locally_redeclared_concepts(repo, ids)
+    offenders = lint.locally_redeclared_concepts(repo, config.vocabulary, ids)
     assert any("Workspace" in msg and "duplicate" in msg for msg in offenders)
 
 
-def test_locally_redeclared_concepts_is_empty_when_concepts_lives_only_on_its_own_page(repo):
+def test_locally_redeclared_concepts_is_empty_when_concepts_lives_only_on_its_own_page(
+    repo, config
+):
     ids = graph.spec_ids(repo)
-    assert lint.locally_redeclared_concepts(repo, ids) == []
+    assert lint.locally_redeclared_concepts(repo, config.vocabulary, ids) == []
 
 
 CONFORMANT_TTL = """\
-app:Budgets a mon:Module ;
+app:Budgets a ex:Module ;
     rdfs:label   "Budgets"@en ;
-    mon:contains app:BudgetsList .
+    ex:contains app:BudgetsList .
 
-app:BudgetsList a mon:View ;
+app:BudgetsList a ex:View ;
     rdfs:label   "Budgets"@en ;
-    mon:partOf   app:Budgets ;
-    mon:route    "/platform/budgets" ;
-    mon:scopedTo app:Workspace ;
-    mon:displays app:Budget_limit .
+    ex:partOf   app:Budgets ;
+    ex:route    "/platform/budgets" ;
+    ex:scopedTo app:Workspace ;
+    ex:displays app:Budget_limit .
 
-app:Budget_limit a mon:Field ;
+app:Budget_limit a ex:Field ;
     rdfs:label "Limit"@en ;
-    mon:format "An amount in the local currency."@en .
+    ex:format "An amount in the local currency."@en .
 """
 
 
-def test_domain_range_violations_flags_a_field_carrying_an_interface_element_predicate(repo):
-    """mon:emptyState declares rdfs:domain mon:InterfaceElement; a mon:Field is not one.
-
-    This is the live violation the corpus actually carried, on app:LoanOut_installments.
-    """
+def test_domain_range_violations_flags_a_field_carrying_an_interface_element_predicate(
+    repo, config, write_spec
+):
+    """emptyState declares rdfs:domain InterfaceElement; a Field is not one."""
     write_spec(repo.root, "misplaced", """\
-app:Loan_installments a mon:Field ;
+app:Loan_installments a ex:Field ;
     rdfs:label     "Installments"@en ;
-    mon:emptyState "No installments yet." .
+    ex:emptyState "No installments yet." .
 """)
-    g = graph.load_graph(repo)
+    g = graph.load_graph(repo, config.vocabulary)
     assert any(
         "Loan_installments" in msg and "emptyState" in msg
-        for msg in lint.domain_range_violations(g)
+        for msg in lint.domain_range_violations(g, config.vocabulary)
     )
 
 
-def test_domain_range_violations_flags_an_object_of_the_wrong_type(repo):
-    """mon:displays declares rdfs:range mon:Field; app:Workspace is a mon:Concept."""
+def test_domain_range_violations_flags_an_object_of_the_wrong_type(repo, config, write_spec):
+    """displays declares rdfs:range Field; app:Workspace is a Concept."""
     write_spec(repo.root, "wrongobject", """\
-app:Panel a mon:Section ;
+app:Panel a ex:Section ;
     rdfs:label   "Panel"@en ;
-    mon:displays app:Workspace .
+    ex:displays app:Workspace .
 """)
-    g = graph.load_graph(repo)
+    g = graph.load_graph(repo, config.vocabulary)
     assert any(
         "displays" in msg and "Workspace" in msg
-        for msg in lint.domain_range_violations(g)
+        for msg in lint.domain_range_violations(g, config.vocabulary)
     )
 
 
-def test_domain_range_violations_accepts_conformant_individuals_across_the_subclass_closure(repo):
+def test_domain_range_violations_accepts_conformant_individuals_across_the_subclass_closure(
+    repo, config, write_spec
+):
     """The acceptance case is only meaningful because this fixture is full of triples the
-    check actually inspects: mon:contains and mon:partOf between a Module and a View, both
-    of which conform only through rdfs:subClassOf mon:InterfaceElement. Drop the closure and
-    this test fails."""
+    check actually inspects: contains and partOf between a Module and a View, both of which
+    conform only through rdfs:subClassOf InterfaceElement. Drop the closure and this test
+    fails."""
     write_spec(repo.root, "budgets", CONFORMANT_TTL)
-    g = graph.load_graph(repo)
-    assert lint.domain_range_violations(g) == []
+    g = graph.load_graph(repo, config.vocabulary)
+    assert lint.domain_range_violations(g, config.vocabulary) == []
 
 
-def test_domain_range_violations_ignores_a_literal_range(repo):
-    """mon:route's range is xsd:string. A literal has no rdf:type to check it against, so
-    the check must skip it rather than call every route a violation."""
+def test_domain_range_violations_ignores_a_literal_range(repo, config, write_spec):
+    """route's range is xsd:string. A literal has no rdf:type to check it against, so the
+    check must skip it rather than call every route a violation."""
     write_spec(repo.root, "budgets", CONFORMANT_TTL)
-    g = graph.load_graph(repo)
-    assert not any("route" in msg for msg in lint.domain_range_violations(g))
+    g = graph.load_graph(repo, config.vocabulary)
+    assert not any("route" in msg for msg in lint.domain_range_violations(g, config.vocabulary))
 
 
-def test_ungrounded_empty_states_flags_a_string_no_sentence_states(repo):
+def test_ungrounded_empty_states_flags_a_string_no_sentence_states(repo, config, write_spec):
     write_spec(repo.root, "invented", """\
-app:InventedTable a mon:Section ;
+app:InventedTable a ex:Section ;
     rdfs:label     "Table"@en ;
-    mon:emptyState "No rows to show." .
+    ex:emptyState "No rows to show." .
 """, prose="A table of five columns, footed with a count of what it holds.\n")
     ids = graph.spec_ids(repo)
     assert any(
         "InventedTable" in msg and "No rows to show." in msg
-        for msg in lint.ungrounded_empty_states(repo, ids)
+        for msg in lint.ungrounded_empty_states(repo, config.vocabulary, ids)
     )
 
 
-def test_ungrounded_empty_states_accepts_a_string_the_prose_states(repo):
+def test_ungrounded_empty_states_accepts_a_string_the_prose_states(repo, config, write_spec):
     write_spec(repo.root, "grounded", """\
-app:GroundedTable a mon:Section ;
+app:GroundedTable a ex:Section ;
     rdfs:label     "Table"@en ;
-    mon:emptyState "No workspaces yet." .
+    ex:emptyState "No workspaces yet." .
 """, prose="With nothing to show the table reads **No workspaces yet.**\n")
     ids = graph.spec_ids(repo)
-    assert lint.ungrounded_empty_states(repo, ids) == []
+    assert lint.ungrounded_empty_states(repo, config.vocabulary, ids) == []
 
 
-def test_ungrounded_empty_states_accepts_a_string_the_prose_hard_wraps(repo):
+def test_ungrounded_empty_states_accepts_a_string_the_prose_hard_wraps(repo, config, write_spec):
     """The prose is hard-wrapped at 90 columns, so a literal can straddle a line break. A
-    byte-for-byte substring test calls that ungrounded; incomes-detail's 'No deductions
-    yet.' is the real case, wrapped between 'No' and 'deductions'."""
+    byte-for-byte substring test calls that ungrounded when it is not."""
     write_spec(repo.root, "wrapped", """\
-app:WrappedTable a mon:Section ;
+app:WrappedTable a ex:Section ;
     rdfs:label     "Table"@en ;
-    mon:emptyState "No deductions yet." .
+    ex:emptyState "No deductions yet." .
 """, prose="The monthly column is red. With none recorded the section reads **No\ndeductions yet.**\n")
     ids = graph.spec_ids(repo)
-    assert lint.ungrounded_empty_states(repo, ids) == []
+    assert lint.ungrounded_empty_states(repo, config.vocabulary, ids) == []
diff --git a/tests/test_paths.py b/tests/test_paths.py
index 3a49044..d43c4e0 100644
--- a/tests/test_paths.py
+++ b/tests/test_paths.py
@@ -1,18 +1,18 @@
 import pytest
 
 from knowledge import paths
 
 
 def make_repo(tmp_path):
     (tmp_path / "knowledge.toml").write_text(
-        '[repo]\ncode_repo = "../monicords_app"\n\n'
+        '[repo]\ncode_repo = "../code"\n\n'
         '[wiki]\nremote = "https://example.com/x.wiki.git"\n',
         encoding="utf-8",
     )
     (tmp_path / "specs" / "assets").mkdir(parents=True)
     return tmp_path
 
 
 def test_find_root_walks_up_from_a_nested_directory(tmp_path):
     root = make_repo(tmp_path)
     assert paths.find_root(root / "specs" / "assets") == root
@@ -20,15 +20,15 @@ def test_find_root_walks_up_from_a_nested_directory(tmp_path):
 
 def test_find_root_raises_when_there_is_no_marker(tmp_path):
     with pytest.raises(RuntimeError, match="knowledge.toml"):
         paths.find_root(tmp_path)
 
 
 def test_paths_are_derived_from_the_root(tmp_path):
     root = make_repo(tmp_path)
     p = paths.get_paths(root)
     assert p.specs == root / "specs"
-    assert p.ontology_ttl == root / "ontology" / "monicords.ttl"
+    assert p.ontology_ttl == root / "ontology" / "ontology.ttl"
     assert p.db == root / ".metadata" / "knowledge.db"
     assert p.dump == root / ".metadata" / "dump.sql"
     assert paths.spec_md(p, "assets") == root / "specs" / "assets" / "spec.md"
     assert paths.spec_ttl(p, "assets") == root / "specs" / "assets" / "spec.ttl"
diff --git a/tests/test_round_trip.py b/tests/test_round_trip.py
index 9b82d71..fcf1c41 100644
--- a/tests/test_round_trip.py
+++ b/tests/test_round_trip.py
@@ -3,53 +3,54 @@ function an agent calls, in the order an agent calls them. Design's "Round trip"
 item: extract (scaffold), model, validate, and confirm the graph parses and its claims
 resolve.
 """
 
 from __future__ import annotations
 
 from knowledge import db, graph, lifecycle, lint, scan
 from tests.conftest import make_config
 
 FIXTURE_TTL = """\
-app:Budgets a mon:Module ;
+app:Budgets a ex:Module ;
     rdfs:label   "Budgets"@en ;
     rdfs:comment "Monthly spending limits per category."@en ;
-    mon:contains app:BudgetsList .
+    ex:contains app:BudgetsList .
 
-app:BudgetsList a mon:View ;
+app:BudgetsList a ex:View ;
     rdfs:label "Budgets"@en ;
-    mon:partOf app:Budgets ;
-    mon:route  "/platform/budgets" .
+    ex:partOf app:Budgets ;
+    ex:route  "/platform/budgets" .
 
-app:BudgetsAreMonthly a mon:Rule ;
+app:BudgetsAreMonthly a ex:Rule ;
     rdfs:label     "A budget resets every calendar month"@en ;
-    mon:appliesTo  app:Budgets ;
+    ex:appliesTo  app:Budgets ;
     rdfs:comment   "Spending against a category clears at midnight on the first, so a limit hit in March says nothing about April."@en .
 """
 
 
 def test_a_spec_can_be_scaffolded_modeled_and_verified(repo):
     conn = db.connect(repo)
     md = lifecycle.new_spec(repo, "budgets", "Budgets")
     md.write_text(
         md.read_text(encoding="utf-8") + "\nA monthly limit per category.\n",
         encoding="utf-8",
     )
     (repo.specs / "budgets" / "spec.ttl").write_text(FIXTURE_TTL, encoding="utf-8")
     scan.scan(conn, repo)
 
     lifecycle.mark_modeled(conn, repo, "budgets", by="writer", ontology_version="1.0.0")
 
-    g = graph.load_graph(repo, ["budgets"])
-    assert graph.dangling_terms(g) == []
-    assert lint.invented_predicates(g) == []
-    assert lint.invented_types(g) == []
-    assert lint.restated_rule_comments(g) == []
-    assert lint.naming_violations(g) == []
-
     config = make_config(repo.root)
+    vocab = config.vocabulary
+    g = graph.load_graph(repo, vocab, ["budgets"])
+    assert graph.dangling_terms(g, vocab) == []
+    assert lint.invented_predicates(g, vocab) == []
+    assert lint.invented_types(g, vocab) == []
+    assert lint.restated_rule_comments(g, vocab) == []
+    assert lint.naming_violations(g, vocab) == []
+
     lifecycle.verify(conn, repo, config, "budgets", by="jesus", prune=[], commit="abc123")
 
     row = list(conn.execute(
         "SELECT status, modeled_by, verified_by FROM spec WHERE id='budgets'"
     ))
     assert row == [("verified", "writer", "jesus")]
```
