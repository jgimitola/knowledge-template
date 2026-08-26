# Task 4 review package

BASE: 58d9446
HEAD: 6a7ed46

## Commits
```
6a7ed46 feat: configure the vocabulary-aware checks, and report the unconfigured ones as skipped
```

## Stat
```
 src/knowledge/cli.py  |  16 ++++++--
 src/knowledge/lint.py | 112 ++++++++++++++++++++++++++++++--------------------
 tests/conftest.py     |  11 ++++-
 tests/test_lint.py    |  62 +++++++++++++++++++++++++---
 4 files changed, 146 insertions(+), 55 deletions(-)
```

## Full diff (-U10)
```diff
diff --git a/src/knowledge/cli.py b/src/knowledge/cli.py
index c6fd2a7..f757b5f 100644
--- a/src/knowledge/cli.py
+++ b/src/knowledge/cli.py
@@ -164,27 +164,35 @@ def cmd_questions(args: argparse.Namespace) -> int:
     return 0
 
 
 def _selected_ids(conn: sqlite3.Connection, paths: Paths, include_drafts: bool) -> list[str]:
     if include_drafts:
         return graph.spec_ids(paths)
     verified = {row[0] for row in conn.execute("SELECT id FROM spec WHERE status='verified'")}
     return [spec_id for spec_id in graph.spec_ids(paths) if spec_id in verified]
 
 
-def _check(name: str, items: Sequence[str], ok_message: str, strict: bool) -> bool:
+def _check(name: str, items: Sequence[str] | None, ok_message: str, strict: bool) -> bool:
     """Report one validate check, and say whether it should fail the run.
 
     `name` is the plural noun phrase printed after the count, so the heading reads
     "N <name>:". A clean check prints `ok_message` instead. Only `strict` decides whether
     findings are fatal — the caller passes True for the checks that always are.
+
+    `items is None` means the check has no configuration to run against — a project without
+    a rule class has no rules for `restated_rule_comments` to be about. That is reported as
+    skipped, never as a pass: printing `ok_message` would claim a check ran clean when it
+    never ran at all.
     """
+    if items is None:
+        print(f"skipped (not configured): {name}")
+        return False
     if not items:
         print(ok_message)
         return False
     print(f"\n{len(items)} {name}:")
     for item in items:
         print("  -", item)
     return strict
 
 
 def cmd_validate(args: argparse.Namespace) -> int:
@@ -213,23 +221,23 @@ def cmd_validate(args: argparse.Namespace) -> int:
                lint.restated_rule_comments(g, vocab),
                "every rule's comment says more than its label", strict),
         _check("naming violation(s)", lint.naming_violations(g, vocab),
                "no naming violations", strict),
         _check("concept(s) redeclared locally instead of referenced",
                lint.locally_redeclared_concepts(paths, vocab, ids),
                "no locally redeclared concepts", strict),
         _check("predicate(s) used outside their declared domain or range",
                lint.domain_range_violations(g, vocab),
                "every predicate stays inside its declared domain and range", strict),
-        _check("empty-state string(s) no prose states",
-               lint.ungrounded_empty_states(paths, vocab, ids),
-               "every empty state appears in its spec's prose", strict),
+        _check("ungrounded literal(s) no prose states",
+               lint.ungrounded_literals(paths, vocab, ids),
+               "every verbatim string appears in its spec's prose", strict),
     ]
     return 1 if any(failures) else 0
 
 
 def cmd_graph(args: argparse.Namespace) -> int:
     paths, config, conn = open_repo(args)
     ids = _selected_ids(conn, paths, args.include_drafts)
     g = graph.load_graph(paths, config.vocabulary, ids)
     output = Path(args.output)
     output.write_text(g.serialize(format="turtle"), encoding="utf-8", newline="\n")
diff --git a/src/knowledge/lint.py b/src/knowledge/lint.py
index 3a4d087..68e45b3 100644
--- a/src/knowledge/lint.py
+++ b/src/knowledge/lint.py
@@ -9,22 +9,20 @@ so the agent is checked rather than trusted for exactly this part of its job.
 
 from __future__ import annotations
 
 import re
 
 from rdflib import RDF, RDFS, Graph, URIRef
 
 from knowledge.paths import Paths
 from knowledge.vocab import Vocabulary
 
-FIELD_NAME = re.compile(r"^[A-Z][A-Za-z0-9]*_[a-z][A-Za-z0-9]*$")
-
 
 def _local(term) -> str:
     return str(term).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
 
 
 def known_terms(g: Graph, vocab: Vocabulary) -> tuple[set[str], set[str]]:
     """(classes, properties) the ontology itself declares under the project namespace."""
     classes = {str(s) for s in g.subjects(RDF.type, RDFS.Class) if vocab.is_term(s)}
     properties = {
         str(s) for s in g.subjects(RDF.type, RDF.Property) if vocab.is_term(s)
@@ -39,51 +37,68 @@ def invented_predicates(g: Graph, vocab: Vocabulary) -> list[str]:
     return sorted(used - properties)
 
 
 def invented_types(g: Graph, vocab: Vocabulary) -> list[str]:
     """Every project-namespace class actually asserted with `a`, that the ontology never declared."""
     classes, _ = known_terms(g, vocab)
     used = {str(o) for o in g.objects(None, RDF.type) if vocab.is_term(o)}
     return sorted(used - classes)
 
 
-def restated_rule_comments(g: Graph, vocab: Vocabulary) -> list[str]:
+def restated_rule_comments(g: Graph, vocab: Vocabulary) -> list[str] | None:
     """A comment that just repeats the label carries no reason a reader could not already
-    infer from the label alone — the whole point of a rule's rdfs:comment."""
+    infer from the label alone — the whole point of a rule's rdfs:comment.
+
+    None when no rule class is configured: a project without a rule class has no rules for
+    this to be about, which is different from having rules that all pass.
+    """
+    if not vocab.checks.rule_class:
+        return None
 
     def norm(text: str) -> str:
         return text.strip().rstrip(".").lower()
 
     offenders = []
-    for rule in g.subjects(RDF.type, vocab.term("Rule")):
+    for rule in g.subjects(RDF.type, vocab.term(vocab.checks.rule_class)):
         label = next((str(o) for o in g.objects(rule, RDFS.label)), "")
         comment = next((str(o) for o in g.objects(rule, RDFS.comment)), "")
         if not comment or norm(comment) == norm(label):
             offenders.append(str(rule))
     return sorted(offenders)
 
 
-def naming_violations(g: Graph, vocab: Vocabulary) -> list[str]:
-    """Fields follow `<Owner>_<field>`; every other individual avoids the underscore that
-    pattern reserves for fields (ontology/README.md's naming table)."""
+def naming_violations(g: Graph, vocab: Vocabulary) -> list[str] | None:
+    """Individuals follow the project's naming conventions.
+
+    Two independent halves, each separately configurable: a pattern every instance of the
+    field class must match, and a reservation of the underscore for that class alone.
+    """
+    checks = vocab.checks
+    if not checks.field_class:
+        return None
+    pattern = re.compile(checks.field_name_pattern) if checks.field_name_pattern else None
+    if pattern is None and not checks.underscore_reserved:
+        return None
+
+    fields = set(g.subjects(RDF.type, vocab.term(checks.field_class)))
     offenders = []
-    fields = set(g.subjects(RDF.type, vocab.term("Field")))
-    for term in fields:
-        if not FIELD_NAME.match(_local(term)):
-            offenders.append(f"{term} does not match the <Owner>_<field> pattern")
-    non_fields = {
-        s for s in g.subjects(RDF.type, None)
-        if vocab.is_instance(s) and s not in fields
-    }
-    for term in non_fields:
-        if "_" in _local(term):
-            offenders.append(f"{term} uses an underscore, which is reserved for fields")
+    if pattern is not None:
+        for term in fields:
+            if not pattern.match(_local(term)):
+                offenders.append(
+                    f"{term} does not match {checks.field_name_pattern}"
+                )
+    if checks.underscore_reserved:
+        others = {s for s in g.subjects(RDF.type, None) if vocab.is_instance(s) and s not in fields}
+        for term in others:
+            if "_" in _local(term):
+                offenders.append(f"{term} uses an underscore, which is reserved for fields")
     return sorted(offenders)
 
 
 def _superclasses(g: Graph) -> dict[URIRef, set[URIRef]]:
     """Every class each class inherits from, transitively over rdfs:subClassOf.
 
     Without this, a containment predicate declared over a base interface-element class
     would flag every triple in the corpus, because nothing is ever typed as that base
     class directly — only its subclasses (a module, a view, a section, ...) are.
     """
@@ -149,56 +164,65 @@ def domain_range_violations(g: Graph, vocab: Vocabulary) -> list[str]:
                 continue
             object_types = types_of(obj)
             if object_types and not (ranges & object_types):
                 offenders.append(
                     f"{obj} is {describe(object_types)}, but {name} declares"
                     f" rdfs:range {describe(ranges)}"
                 )
     return sorted(offenders)
 
 
-def ungrounded_empty_states(paths: Paths, vocab: Vocabulary, ids) -> list[str]:
-    """An emptyState literal no sentence in the owning spec.md states.
+def ungrounded_literals(paths: Paths, vocab: Vocabulary, ids) -> list[str] | None:
+    """A literal no sentence in the owning spec.md states.
 
-    emptyState is the one predicate whose value is a verbatim UI string rather than a
-    paraphrase, which makes "does the prose say this?" a question code can answer. The
-    writer's graph-to-prose rule says a triple the prose does not support is removed; this
-    is that rule, mechanised, for the one predicate it can be mechanised for. format is
-    paraphrase by design and defaultsTo often is too — neither belongs here.
+    Only for predicates whose value is a verbatim string rather than a paraphrase — the
+    writer's graph-to-prose rule, mechanised for the predicates it can be mechanised for. A
+    paraphrasing predicate must never be listed here: a verbatim-substring check would flag
+    every one of its values, none of them correctly.
 
-    The prose is hard-wrapped, so the comparison collapses runs of whitespace first. Without
-    that, a string straddling a line break reads as ungrounded when it is not.
+    The prose is hard-wrapped, so the comparison collapses runs of whitespace first.
+    Without that, a string straddling a line break reads as ungrounded when it is not.
     """
     from knowledge.graph import load_spec_graph
     from knowledge.paths import spec_md
 
-    empty_state = vocab.term("emptyState")
+    properties = vocab.checks.verbatim_string_properties
+    if not properties:
+        return None
+
     offenders = []
     for spec_id in ids:
         path = spec_md(paths, spec_id)
         if not path.is_file():
             continue
         prose = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
-        for subject, literal in load_spec_graph(paths, vocab, spec_id).subject_objects(empty_state):
-            if str(literal) not in prose:
-                offenders.append(
-                    f"{subject} has {vocab.prefix}:emptyState {str(literal)!r},"
-                    f" which no sentence of {spec_id}/spec.md states"
-                )
+        g = load_spec_graph(paths, vocab, spec_id)
+        for name in properties:
+            for subject, literal in g.subject_objects(vocab.term(name)):
+                if str(literal) not in prose:
+                    offenders.append(
+                        f"{subject} has {vocab.prefix}:{name} {str(literal)!r},"
+                        f" which no sentence of {spec_id}/spec.md states"
+                    )
     return sorted(offenders)
 
 
-def locally_redeclared_concepts(paths: Paths, vocab: Vocabulary, ids) -> list[str]:
-    """A concept declared once on the `concepts` spec and referenced everywhere else is
-    what turns independent specs into one connected graph. Declaring it again on some other
-    spec is the same fact twice, free to drift apart from the original."""
+def locally_redeclared_concepts(paths: Paths, vocab: Vocabulary, ids) -> list[str] | None:
+    """A concept declared once on one spec and referenced everywhere else is what turns
+    independent specs into one connected graph. Declaring it again on some other spec is
+    the same fact twice, free to drift apart from the original."""
     from knowledge.graph import load_spec_graph
 
-    concept = vocab.term("Concept")
+    checks = vocab.checks
+    if not checks.concept_class or not checks.concept_spec:
+        return None
+
+    concept = vocab.term(checks.concept_class)
     offenders = []
     for spec_id in ids:
-        if spec_id == "concepts":
+        if spec_id == checks.concept_spec:
             continue
-        g = load_spec_graph(paths, vocab, spec_id)
-        for term in g.subjects(RDF.type, concept):
-            offenders.append(f"{term} declared on {spec_id!r} instead of concepts")
+        for term in load_spec_graph(paths, vocab, spec_id).subjects(RDF.type, concept):
+            offenders.append(
+                f"{term} declared on {spec_id!r} instead of {checks.concept_spec!r}"
+            )
     return sorted(offenders)
diff --git a/tests/conftest.py b/tests/conftest.py
index 4e3df50..a7bcd3a 100644
--- a/tests/conftest.py
+++ b/tests/conftest.py
@@ -183,21 +183,30 @@ def make_config(code_repo, remote="https://example.com/x.wiki.git"):
     """A Config for tests that exercise lifecycle/deps functions directly, without going
     through load_config. Same example vocabulary as KNOWLEDGE_TOML above."""
     return Config(
         project_name="Example",
         vocabulary=Vocabulary(
             ontology_file="ontology.ttl",
             namespace="https://example.test/ontology#",
             instances="https://example.test/id/",
             prefix="ex",
             instance_prefix="app",
-            checks=Checks(),
+            checks=Checks(
+                rule_class="Rule",
+                concept_class="Concept",
+                concept_spec="concepts",
+                field_class="Field",
+                field_name_pattern="^[A-Z][A-Za-z0-9]*_[a-z][A-Za-z0-9]*$",
+                underscore_reserved=True,
+                functional_properties=("route", "editable", "required", "viewport", "defaultsTo"),
+                verbatim_string_properties=("emptyState",),
+            ),
         ),
         surveys=(),
         code_repo=code_repo,
         dependencies=Dependencies(),
         publish=Publish(remote=remote),
         unconfigured=False,
     )
 
 
 @pytest.fixture
diff --git a/tests/test_lint.py b/tests/test_lint.py
index 2c94f2f..f052e5f 100644
--- a/tests/test_lint.py
+++ b/tests/test_lint.py
@@ -1,10 +1,12 @@
+from dataclasses import replace
+
 from knowledge import graph, lint
 
 
 def test_invented_predicates_finds_an_undeclared_property(repo, config, write_spec):
     write_spec(repo.root, "typo", 'app:Assets a ex:View ; ex:rout "/x" .\n')
     g = graph.load_graph(repo, config.vocabulary)
     assert "https://example.test/ontology#rout" in lint.invented_predicates(g, config.vocabulary)
 
 
 def test_invented_predicates_is_empty_for_a_clean_graph(repo, config):
@@ -146,43 +148,91 @@ def test_domain_range_violations_accepts_conformant_individuals_across_the_subcl
 
 
 def test_domain_range_violations_ignores_a_literal_range(repo, config, write_spec):
     """route's range is xsd:string. A literal has no rdf:type to check it against, so the
     check must skip it rather than call every route a violation."""
     write_spec(repo.root, "budgets", CONFORMANT_TTL)
     g = graph.load_graph(repo, config.vocabulary)
     assert not any("route" in msg for msg in lint.domain_range_violations(g, config.vocabulary))
 
 
-def test_ungrounded_empty_states_flags_a_string_no_sentence_states(repo, config, write_spec):
+def test_ungrounded_literals_flags_a_string_no_sentence_states(repo, config, write_spec):
     write_spec(repo.root, "invented", """\
 app:InventedTable a ex:Section ;
     rdfs:label     "Table"@en ;
     ex:emptyState "No rows to show." .
 """, prose="A table of five columns, footed with a count of what it holds.\n")
     ids = graph.spec_ids(repo)
     assert any(
         "InventedTable" in msg and "No rows to show." in msg
-        for msg in lint.ungrounded_empty_states(repo, config.vocabulary, ids)
+        for msg in lint.ungrounded_literals(repo, config.vocabulary, ids)
     )
 
 
-def test_ungrounded_empty_states_accepts_a_string_the_prose_states(repo, config, write_spec):
+def test_ungrounded_literals_accepts_a_string_the_prose_states(repo, config, write_spec):
     write_spec(repo.root, "grounded", """\
 app:GroundedTable a ex:Section ;
     rdfs:label     "Table"@en ;
     ex:emptyState "No workspaces yet." .
 """, prose="With nothing to show the table reads **No workspaces yet.**\n")
     ids = graph.spec_ids(repo)
-    assert lint.ungrounded_empty_states(repo, config.vocabulary, ids) == []
+    assert lint.ungrounded_literals(repo, config.vocabulary, ids) == []
 
 
-def test_ungrounded_empty_states_accepts_a_string_the_prose_hard_wraps(repo, config, write_spec):
+def test_ungrounded_literals_accepts_a_string_the_prose_hard_wraps(repo, config, write_spec):
     """The prose is hard-wrapped at 90 columns, so a literal can straddle a line break. A
     byte-for-byte substring test calls that ungrounded when it is not."""
     write_spec(repo.root, "wrapped", """\
 app:WrappedTable a ex:Section ;
     rdfs:label     "Table"@en ;
     ex:emptyState "No deductions yet." .
 """, prose="The monthly column is red. With none recorded the section reads **No\ndeductions yet.**\n")
     ids = graph.spec_ids(repo)
-    assert lint.ungrounded_empty_states(repo, config.vocabulary, ids) == []
+    assert lint.ungrounded_literals(repo, config.vocabulary, ids) == []
+
+
+def test_configured_checks_run(repo, config):
+    vocab = config.vocabulary
+    g = graph.load_graph(repo, vocab)
+    assert lint.restated_rule_comments(g, vocab) == []
+    assert lint.naming_violations(g, vocab) == []
+    assert lint.locally_redeclared_concepts(repo, vocab, ["assets", "concepts"]) == []
+    assert lint.ungrounded_literals(repo, vocab, ["assets", "concepts"]) == []
+
+
+def test_unconfigured_checks_return_none_rather_than_passing(repo, config):
+    vocab = replace(config.vocabulary, checks=replace(
+        config.vocabulary.checks,
+        rule_class="",
+        concept_class="",
+        field_class="",
+        verbatim_string_properties=(),
+    ))
+    g = graph.load_graph(repo, vocab)
+    assert lint.restated_rule_comments(g, vocab) is None
+    assert lint.naming_violations(g, vocab) is None
+    assert lint.locally_redeclared_concepts(repo, vocab, ["assets"]) is None
+    assert lint.ungrounded_literals(repo, vocab, ["assets"]) is None
+
+
+def test_underscore_rule_is_separable_from_the_field_pattern(repo, config):
+    """A project may name fields freely but still reserve the underscore, or neither."""
+    vocab = replace(config.vocabulary, checks=replace(
+        config.vocabulary.checks, field_name_pattern="", underscore_reserved=False
+    ))
+    g = graph.load_graph(repo, vocab)
+    assert lint.naming_violations(g, vocab) is None
+
+
+def test_ungrounded_literals_covers_every_configured_property(repo, config, write_spec):
+    write_spec(
+        repo.root,
+        "widgets",
+        'app:Widgets a ex:View ;\n'
+        '    rdfs:label "Widgets"@en ;\n'
+        '    ex:emptyState "Nothing here yet" .\n',
+        "The Widgets screen says nothing about its empty state.\n",
+    )
+    vocab = config.vocabulary
+    offenders = lint.ungrounded_literals(repo, vocab, ["widgets"])
+    assert len(offenders) == 1
+    assert "Nothing here yet" in offenders[0]
```
