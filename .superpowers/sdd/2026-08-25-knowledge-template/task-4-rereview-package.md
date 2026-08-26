# Task 4 fix-round 1 scoped diff

FIX_BASE: 6a7ed46
HEAD: cb02250

## Commits
```
cb02250 docs: explain the None sentinel in each configurable check
```

## Stat
```
 src/knowledge/lint.py | 17 ++++++++++++++++-
 1 file changed, 16 insertions(+), 1 deletion(-)
```

## Full diff (-U15)
```diff
diff --git a/src/knowledge/lint.py b/src/knowledge/lint.py
index 68e45b3..57c4bd6 100644
--- a/src/knowledge/lint.py
+++ b/src/knowledge/lint.py
@@ -59,30 +59,36 @@ def restated_rule_comments(g: Graph, vocab: Vocabulary) -> list[str] | None:
 
     offenders = []
     for rule in g.subjects(RDF.type, vocab.term(vocab.checks.rule_class)):
         label = next((str(o) for o in g.objects(rule, RDFS.label)), "")
         comment = next((str(o) for o in g.objects(rule, RDFS.comment)), "")
         if not comment or norm(comment) == norm(label):
             offenders.append(str(rule))
     return sorted(offenders)
 
 
 def naming_violations(g: Graph, vocab: Vocabulary) -> list[str] | None:
     """Individuals follow the project's naming conventions.
 
     Two independent halves, each separately configurable: a pattern every instance of the
     field class must match, and a reservation of the underscore for that class alone.
+
+    None when no field class is configured, or when a field class is configured but
+    neither pattern nor underscore reservation is set. An empty field class makes the
+    check meaningless: without it, the underscore half has nothing to exempt, so it
+    would flag every field as a violation. The second condition leaves no checks active
+    to run, which is different from having checks that all pass.
     """
     checks = vocab.checks
     if not checks.field_class:
         return None
     pattern = re.compile(checks.field_name_pattern) if checks.field_name_pattern else None
     if pattern is None and not checks.underscore_reserved:
         return None
 
     fields = set(g.subjects(RDF.type, vocab.term(checks.field_class)))
     offenders = []
     if pattern is not None:
         for term in fields:
             if not pattern.match(_local(term)):
                 offenders.append(
                     f"{term} does not match {checks.field_name_pattern}"
@@ -169,59 +175,68 @@ def domain_range_violations(g: Graph, vocab: Vocabulary) -> list[str]:
                     f" rdfs:range {describe(ranges)}"
                 )
     return sorted(offenders)
 
 
 def ungrounded_literals(paths: Paths, vocab: Vocabulary, ids) -> list[str] | None:
     """A literal no sentence in the owning spec.md states.
 
     Only for predicates whose value is a verbatim string rather than a paraphrase — the
     writer's graph-to-prose rule, mechanised for the predicates it can be mechanised for. A
     paraphrasing predicate must never be listed here: a verbatim-substring check would flag
     every one of its values, none of them correctly.
 
     The prose is hard-wrapped, so the comparison collapses runs of whitespace first.
     Without that, a string straddling a line break reads as ungrounded when it is not.
+
+    None when verbatim_string_properties is empty: a project with no verbatim predicates
+    configured has nothing for this check to be about, which is different from having
+    predicates that all appear in the prose.
     """
     from knowledge.graph import load_spec_graph
     from knowledge.paths import spec_md
 
     properties = vocab.checks.verbatim_string_properties
     if not properties:
         return None
 
     offenders = []
     for spec_id in ids:
         path = spec_md(paths, spec_id)
         if not path.is_file():
             continue
         prose = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
         g = load_spec_graph(paths, vocab, spec_id)
         for name in properties:
             for subject, literal in g.subject_objects(vocab.term(name)):
                 if str(literal) not in prose:
                     offenders.append(
                         f"{subject} has {vocab.prefix}:{name} {str(literal)!r},"
                         f" which no sentence of {spec_id}/spec.md states"
                     )
     return sorted(offenders)
 
 
 def locally_redeclared_concepts(paths: Paths, vocab: Vocabulary, ids) -> list[str] | None:
     """A concept declared once on one spec and referenced everywhere else is what turns
     independent specs into one connected graph. Declaring it again on some other spec is
-    the same fact twice, free to drift apart from the original."""
+    the same fact twice, free to drift apart from the original.
+
+    None when concept_class or concept_spec is empty: the check cannot identify what a
+    concept is, or enforce where concepts belong, so it has nothing to check, which is
+    different from finding concepts that all respect the rule.
+    """
     from knowledge.graph import load_spec_graph
 
     checks = vocab.checks
     if not checks.concept_class or not checks.concept_spec:
         return None
 
     concept = vocab.term(checks.concept_class)
     offenders = []
     for spec_id in ids:
         if spec_id == checks.concept_spec:
             continue
         for term in load_spec_graph(paths, vocab, spec_id).subjects(RDF.type, concept):
             offenders.append(
                 f"{term} declared on {spec_id!r} instead of {checks.concept_spec!r}"
             )
```
