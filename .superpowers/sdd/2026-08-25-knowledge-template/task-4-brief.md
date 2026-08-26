### Task 4: Make the five vocabulary-aware lint checks configurable

**Files:**

- Modify: `src/knowledge/lint.py`
- Modify: `src/knowledge/cli.py` (`cmd_validate`, `_check`)
- Test: `tests/test_lint.py`

**Interfaces:**

- Consumes: `vocab.Vocabulary`, `vocab.Checks` from Task 2; `graph.load_spec_graph` from Task 3.
- Produces (each returns `None` when its configuration is empty):
  - `lint.known_terms(g, vocab) -> tuple[set[str], set[str]]`
  - `lint.invented_predicates(g, vocab) -> list[str]`
  - `lint.invented_types(g, vocab) -> list[str]`
  - `lint.restated_rule_comments(g, vocab) -> list[str] | None`
  - `lint.naming_violations(g, vocab) -> list[str] | None`
  - `lint.domain_range_violations(g, vocab) -> list[str]`
  - `lint.ungrounded_literals(paths, vocab, ids) -> list[str] | None` (renamed from `ungrounded_empty_states`; iterates `checks.verbatim_string_properties`)
  - `lint.locally_redeclared_concepts(paths, vocab, ids) -> list[str] | None`
  - `cli._check(name, items, ok_message, strict) -> bool` gains handling for `items is None`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_lint.py`:

```python
from dataclasses import replace

from knowledge import graph, lint


def test_configured_checks_run(repo, config):
    vocab = config.vocabulary
    g = graph.load_graph(repo, vocab)
    assert lint.restated_rule_comments(g, vocab) == []
    assert lint.naming_violations(g, vocab) == []
    assert lint.locally_redeclared_concepts(repo, vocab, ["assets", "concepts"]) == []
    assert lint.ungrounded_literals(repo, vocab, ["assets", "concepts"]) == []


def test_unconfigured_checks_return_none_rather_than_passing(repo, config):
    vocab = replace(config.vocabulary, checks=replace(
        config.vocabulary.checks,
        rule_class="",
        concept_class="",
        field_class="",
        verbatim_string_properties=(),
    ))
    g = graph.load_graph(repo, vocab)
    assert lint.restated_rule_comments(g, vocab) is None
    assert lint.naming_violations(g, vocab) is None
    assert lint.locally_redeclared_concepts(repo, vocab, ["assets"]) is None
    assert lint.ungrounded_literals(repo, vocab, ["assets"]) is None


def test_underscore_rule_is_separable_from_the_field_pattern(repo, config):
    """A project may name fields freely but still reserve the underscore, or neither."""
    vocab = replace(config.vocabulary, checks=replace(
        config.vocabulary.checks, field_name_pattern="", underscore_reserved=False
    ))
    g = graph.load_graph(repo, vocab)
    assert lint.naming_violations(g, vocab) is None


def test_ungrounded_literals_covers_every_configured_property(repo, config, tmp_path):
    from tests.conftest import write_spec
    write_spec(
        repo.root,
        "widgets",
        'app:Widgets a ex:View ;\n'
        '    rdfs:label "Widgets"@en ;\n'
        '    ex:emptyState "Nothing here yet" .\n',
        "The Widgets screen says nothing about its empty state.\n",
    )
    vocab = config.vocabulary
    offenders = lint.ungrounded_literals(repo, vocab, ["widgets"])
    assert len(offenders) == 1
    assert "Nothing here yet" in offenders[0]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_lint.py -v`
Expected: FAIL — `lint.ungrounded_literals` does not exist, and the existing functions take no `vocab`.

- [ ] **Step 3: Rewrite the configurable checks in `lint.py`**

Delete `from knowledge.graph import APP, MON` and the module-level `FIELD_NAME`. Then:

```python
def known_terms(g: Graph, vocab: Vocabulary) -> tuple[set[str], set[str]]:
    """(classes, properties) the ontology itself declares under the project namespace."""
    classes = {str(s) for s in g.subjects(RDF.type, RDFS.Class) if vocab.is_term(s)}
    properties = {str(s) for s in g.subjects(RDF.type, RDF.Property) if vocab.is_term(s)}
    return classes, properties


def invented_predicates(g: Graph, vocab: Vocabulary) -> list[str]:
    _, properties = known_terms(g, vocab)
    used = {str(p) for p in g.predicates() if vocab.is_term(p)}
    return sorted(used - properties)


def invented_types(g: Graph, vocab: Vocabulary) -> list[str]:
    classes, _ = known_terms(g, vocab)
    used = {str(o) for o in g.objects(None, RDF.type) if vocab.is_term(o)}
    return sorted(used - classes)


def restated_rule_comments(g: Graph, vocab: Vocabulary) -> list[str] | None:
    """A comment that just repeats the label carries no reason a reader could not already
    infer from the label alone — the whole point of a rule's rdfs:comment.

    None when no rule class is configured: a project without a rule class has no rules for
    this to be about, which is different from having rules that all pass.
    """
    if not vocab.checks.rule_class:
        return None

    def norm(text: str) -> str:
        return text.strip().rstrip(".").lower()

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
    """
    checks = vocab.checks
    pattern = re.compile(checks.field_name_pattern) if checks.field_name_pattern else None
    if pattern is None and not checks.underscore_reserved:
        return None

    fields = (
        set(g.subjects(RDF.type, vocab.term(checks.field_class))) if checks.field_class else set()
    )
    offenders = []
    if pattern is not None:
        for term in fields:
            if not pattern.match(_local(term)):
                offenders.append(
                    f"{term} does not match {checks.field_name_pattern}"
                )
    if checks.underscore_reserved:
        others = {s for s in g.subjects(RDF.type, None) if vocab.is_instance(s) and s not in fields}
        for term in others:
            if "_" in _local(term):
                offenders.append(f"{term} uses an underscore, which is reserved for fields")
    return sorted(offenders)


def ungrounded_literals(paths: Paths, vocab: Vocabulary, ids) -> list[str] | None:
    """A literal no sentence in the owning spec.md states.

    Only for predicates whose value is a verbatim string rather than a paraphrase — the
    writer's graph-to-prose rule, mechanised for the predicates it can be mechanised for. A
    paraphrasing predicate must never be listed here: a verbatim-substring check would flag
    every one of its values, none of them correctly.

    The prose is hard-wrapped, so the comparison collapses runs of whitespace first.
    Without that, a string straddling a line break reads as ungrounded when it is not.
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
    the same fact twice, free to drift apart from the original."""
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
    return sorted(offenders)
```

`domain_range_violations` keeps its logic; replace `str(prop).startswith(MON)` with `vocab.is_term(prop)`, `str(r).startswith(MON)` with `vocab.is_term(r)`, and `f"mon:{_local(t)}"` with `vocab.qname(t)`.

Add `from knowledge.vocab import Vocabulary` to the imports and keep `import re`.

- [ ] **Step 4: Teach `cli._check` about a skipped check**

```python
def _check(name: str, items: list[str] | None, ok_message: str, strict: bool) -> bool:
    if items is None:
        print(f"skipped (not configured): {name}")
        return False
    if not items:
        print(ok_message)
        return False
    print(f"\n{len(items)} {name}:")
    for item in items:
        print("  -", item)
    return strict
```

Update `cmd_validate` to pass `config.vocabulary` into each check, and to combine the two invented-term lists without losing a `None` (neither returns `None`, so `lint.invented_predicates(g, v) + lint.invented_types(g, v)` still works).

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_lint.py tests/test_cli_read.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: configure the vocabulary-aware checks, and report the unconfigured ones as skipped"
```

---

