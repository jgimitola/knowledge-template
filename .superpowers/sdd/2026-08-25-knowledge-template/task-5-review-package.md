# Task 5 review package

BASE: cb02250
HEAD: 74b6741

## Commits
```
74b6741 fix: do not report a clean contradictions run when checks were skipped
19ab1bf feat: read the functional-property list from knowledge.toml
```

## Stat
```
 src/knowledge/cli.py            | 19 ++++++++++++++++---
 src/knowledge/contradictions.py | 23 ++++++++++++++---------
 tests/test_cli_read.py          | 19 +++++++++++++++++++
 tests/test_contradictions.py    | 29 +++++++++++++++++++++++++++++
 4 files changed, 78 insertions(+), 12 deletions(-)
```

## Full diff (-U10)
```diff
diff --git a/src/knowledge/cli.py b/src/knowledge/cli.py
index f757b5f..bbde317 100644
--- a/src/knowledge/cli.py
+++ b/src/knowledge/cli.py
@@ -286,45 +286,58 @@ def cmd_ask(args: argparse.Namespace) -> int:
     return 0
 
 
 def cmd_contradictions(args: argparse.Namespace) -> int:
     paths, config, conn = open_repo(args)
     vocab = config.vocabulary
     from knowledge import contradictions, lint
     ids = _selected_ids(conn, paths, args.include_drafts)
     g = graph.load_graph(paths, vocab, ids)
     found = False
+    skipped = 0
 
     conflicts = contradictions.functional_conflicts(g, vocab)
-    if conflicts:
+    if conflicts is None:
+        skipped += 1
+        print("skipped (not configured): functional-property conflicts")
+    elif conflicts:
         found = True
         print(f"{len(conflicts)} functional-property conflict(s):")
         for subject, prop, values in conflicts:
             print(f"  - {subject} {vocab.prefix}:{prop} has {len(values)} values:"
                   f" {', '.join(values)}")
 
     dangling = graph.dangling_terms(g, vocab)
     if dangling:
         found = True
         print(f"\n{len(dangling)} term(s) referenced but never declared:")
         for term in dangling:
             print("  -", term)
 
     redeclared = lint.locally_redeclared_concepts(paths, vocab, ids)
-    if redeclared:
+    if redeclared is None:
+        skipped += 1
+        print("skipped (not configured): locally redeclared concepts")
+    elif redeclared:
         found = True
         print(f"\n{len(redeclared)} concept(s) redeclared locally instead of referenced:")
         for msg in redeclared:
             print("  -", msg)
 
     if not found:
-        print("no mechanical contradictions found")
+        if skipped:
+            print(
+                f"no contradictions found by the checks that ran"
+                f" ({skipped} skipped — see above)"
+            )
+        else:
+            print("no mechanical contradictions found")
     return 0
 
 
 def cmd_new(args: argparse.Namespace) -> int:
     paths, _config, conn = open_repo(args)
     from knowledge import lifecycle
     md = lifecycle.new_spec(paths, args.id, args.title or args.id.replace("-", " ").title())
     scan.scan(conn, paths)
     print(f"created {md}")
     return 0
diff --git a/src/knowledge/contradictions.py b/src/knowledge/contradictions.py
index 068100c..11307c3 100644
--- a/src/knowledge/contradictions.py
+++ b/src/knowledge/contradictions.py
@@ -3,29 +3,34 @@ a SPARQL-shaped query rather than a judgement call.
 """
 
 from __future__ import annotations
 
 from collections import defaultdict
 
 from rdflib import Graph
 
 from knowledge.vocab import Vocabulary
 
-# Properties the ontology documents as single-valued, plus defaultsTo and route — the
-# design's own two examples of what this check looks for. "Functional by convention"
-# because RDFS never enforces it (ontology/README.md, "Properties with literal values").
-FUNCTIONAL_PROPERTIES = ("route", "editable", "required", "viewport", "defaultsTo")
 
-
-def functional_conflicts(g: Graph, vocab: Vocabulary) -> list[tuple[str, str, list[str]]]:
+def functional_conflicts(
+    g: Graph, vocab: Vocabulary
+) -> list[tuple[str, str, list[str]]] | None:
     """(subject, property, sorted values) for every subject asserting more than one value
-    on a property that is supposed to hold at most one — two route values on one view, two
-    defaultsTo values on one field."""
+    on a property configured as single-valued — two routes on one view, two defaults on one
+    field. RDFS never enforces this, so the list comes from knowledge.toml.
+
+    None when no properties are configured: nothing to check is not the same as nothing
+    found.
+    """
+    properties = vocab.checks.functional_properties
+    if not properties:
+        return None
+
     seen: dict[tuple[str, str], set[str]] = defaultdict(set)
-    for prop in FUNCTIONAL_PROPERTIES:
+    for prop in properties:
         for subject, obj in g.subject_objects(vocab.term(prop)):
             seen[(str(subject), prop)].add(str(obj))
     return sorted(
         (subject, prop, sorted(values))
         for (subject, prop), values in seen.items()
         if len(values) > 1
     )
diff --git a/tests/test_cli_read.py b/tests/test_cli_read.py
index 740598b..78a1bd7 100644
--- a/tests/test_cli_read.py
+++ b/tests/test_cli_read.py
@@ -146,16 +146,35 @@ def test_graph_defaults_to_verified_specs_only(seeded, tmp_path):
     args.handler(args)
     assert "/platform/assets" in both.read_text(encoding="utf-8")
 
 
 def test_contradictions_reports_none_on_a_clean_graph(seeded, capsys):
     args = run(["contradictions", "--include-drafts"])
     assert args.handler(args) == 0
     assert "no mechanical contradictions found" in capsys.readouterr().out
 
 
+def test_contradictions_summary_accounts_for_skipped_checks(seeded, capsys):
+    """With every configurable check unconfigured, only dangling_terms actually ran. The
+    summary must not read as a verdict on the checks that were skipped."""
+    toml_path = seeded.root / "knowledge.toml"
+    text = toml_path.read_text(encoding="utf-8")
+    text = text.replace('concept_class = "Concept"\nconcept_spec = "concepts"\n', "")
+    text = text.replace(
+        'functional_properties = ["route", "editable", "required", "viewport", "defaultsTo"]\n',
+        "",
+    )
+    toml_path.write_text(text, encoding="utf-8")
+
+    args = run(["contradictions", "--include-drafts"])
+    assert args.handler(args) == 0
+    out = capsys.readouterr().out
+    assert "no mechanical contradictions found" not in out
+    assert "2 skipped" in out
+
+
 def test_contradictions_reports_a_functional_conflict(seeded, write_spec, capsys):
     write_spec(seeded.root, "duplicate-route",
                'app:Assets a ex:View ; ex:route "/somewhere-else" .\n')
     args = run(["contradictions", "--include-drafts"])
     args.handler(args)
     assert "route" in capsys.readouterr().out
diff --git a/tests/test_contradictions.py b/tests/test_contradictions.py
index 0ffc9c0..56d56a3 100644
--- a/tests/test_contradictions.py
+++ b/tests/test_contradictions.py
@@ -1,16 +1,45 @@
+from dataclasses import replace
+
 from knowledge import contradictions, graph
 
 
 def test_functional_conflicts_finds_two_routes_on_one_view(repo, config, write_spec):
     write_spec(repo.root, "duplicate-route",
                'app:Assets a ex:View ; ex:route "/somewhere-else" .\n')
     g = graph.load_graph(repo, config.vocabulary)
     conflicts = contradictions.functional_conflicts(g, config.vocabulary)
     assert (
         "https://example.test/id/Assets", "route", ["/platform/assets", "/somewhere-else"]
     ) in conflicts
 
 
 def test_functional_conflicts_is_empty_for_a_single_route(repo, config):
     g = graph.load_graph(repo, config.vocabulary)
     assert contradictions.functional_conflicts(g, config.vocabulary) == []
+
+
+def test_conflict_is_found_for_a_configured_functional_property(repo, config, write_spec):
+    write_spec(
+        repo.root,
+        "twice",
+        'app:Twice a ex:View ;\n'
+        '    rdfs:label "Twice"@en ;\n'
+        '    ex:route "/a" ;\n'
+        '    ex:route "/b" .\n',
+    )
+    vocab = config.vocabulary
+    g = graph.load_graph(repo, vocab, ["twice"])
+    found = contradictions.functional_conflicts(g, vocab)
+    assert len(found) == 1
+    subject, prop, values = found[0]
+    assert prop == "route"
+    assert values == ["/a", "/b"]
+
+
+def test_no_configured_properties_returns_none(repo, config):
+    vocab = replace(
+        config.vocabulary,
+        checks=replace(config.vocabulary.checks, functional_properties=()),
+    )
+    g = graph.load_graph(repo, vocab)
+    assert contradictions.functional_conflicts(g, vocab) is None
```
