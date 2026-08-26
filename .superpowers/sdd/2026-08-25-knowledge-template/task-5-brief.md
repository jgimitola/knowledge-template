### Task 5: Configure the functional-property list

**Files:**

- Modify: `src/knowledge/contradictions.py`
- Modify: `src/knowledge/cli.py` (`cmd_contradictions`)
- Test: `tests/test_contradictions.py`

**Interfaces:**

- Consumes: `vocab.Vocabulary` from Task 2.
- Produces: `contradictions.functional_conflicts(g, vocab) -> list[tuple[str, str, list[str]]] | None`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_contradictions.py`:

```python
from dataclasses import replace

from knowledge import contradictions, graph


def test_conflict_is_found_for_a_configured_functional_property(repo, config):
    from tests.conftest import write_spec
    write_spec(
        repo.root,
        "twice",
        'app:Twice a ex:View ;\n'
        '    rdfs:label "Twice"@en ;\n'
        '    ex:route "/a" ;\n'
        '    ex:route "/b" .\n',
    )
    vocab = config.vocabulary
    g = graph.load_graph(repo, vocab, ["twice"])
    found = contradictions.functional_conflicts(g, vocab)
    assert len(found) == 1
    subject, prop, values = found[0]
    assert prop == "route"
    assert values == ["/a", "/b"]


def test_no_configured_properties_returns_none(repo, config):
    vocab = replace(
        config.vocabulary,
        checks=replace(config.vocabulary.checks, functional_properties=()),
    )
    g = graph.load_graph(repo, vocab)
    assert contradictions.functional_conflicts(g, vocab) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_contradictions.py -v`
Expected: FAIL — `functional_conflicts()` takes 1 positional argument but 2 were given.

- [ ] **Step 3: Rewrite `contradictions.py`**

```python
"""Mechanical contradiction checks: the part of the interviewer's per-answer check that is
a SPARQL-shaped query rather than a judgement call.
"""

from __future__ import annotations

from collections import defaultdict

from rdflib import Graph

from knowledge.vocab import Vocabulary


def functional_conflicts(
    g: Graph, vocab: Vocabulary
) -> list[tuple[str, str, list[str]]] | None:
    """(subject, property, sorted values) for every subject asserting more than one value
    on a property configured as single-valued — two routes on one view, two defaults on one
    field. RDFS never enforces this, so the list comes from knowledge.toml.

    None when no properties are configured: nothing to check is not the same as nothing
    found.
    """
    properties = vocab.checks.functional_properties
    if not properties:
        return None

    seen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for prop in properties:
        for subject, obj in g.subject_objects(vocab.term(prop)):
            seen[(str(subject), prop)].add(str(obj))
    return sorted(
        (subject, prop, sorted(values))
        for (subject, prop), values in seen.items()
        if len(values) > 1
    )
```

- [ ] **Step 4: Update `cmd_contradictions`**

```python
conflicts = contradictions.functional_conflicts(g, config.vocabulary)
if conflicts is None:
    print("skipped (not configured): functional-property conflicts")
elif conflicts:
    found = True
    print(f"{len(conflicts)} functional-property conflict(s):")
    for subject, prop, values in conflicts:
        print(f"  - {subject} {config.vocabulary.prefix}:{prop} has "
              f"{len(values)} values: {', '.join(values)}")

redeclared = lint.locally_redeclared_concepts(paths, config.vocabulary, ids)
if redeclared is None:
    print("skipped (not configured): locally redeclared concepts")
elif redeclared:
    ...
```

Pass `config.vocabulary` into `graph.dangling_terms` too.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_contradictions.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: read the functional-property list from knowledge.toml"
```

---

