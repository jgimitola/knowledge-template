### Task 10: Ontology seed, authoring guide, worked example, example spec

**Files:**

- Create: `ontology/ontology.ttl`, `ontology/AUTHORING.md`, `ontology/README.md`
- Create: `ontology/examples/webapp.ttl`, `ontology/examples/webapp.toml`
- Create: `specs/example/spec.md`, `specs/example/spec.ttl`
- Create: `.metadata/dump.sql` (generated)
- Test: `tests/test_template_content.py`

**Interfaces:**

- Consumes: everything from Tasks 2–9.
- Produces: a template repository where `uv run knowledge scan && uv run knowledge validate --strict` exits 0 before `init` runs.

- [ ] **Step 1: Write the failing test**

Create `tests/test_template_content.py`:

```python
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run(
        [sys.executable, "-m", "knowledge.cli", *args],
        cwd=ROOT, capture_output=True, text=True,
    )


def test_the_shipped_template_validates_as_it_stands():
    assert run("scan").returncode == 0
    result = run("validate", "--strict")
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_shipped_template_still_has_its_placeholders():
    """`init --check` must FAIL here — the template is the one repository where
    placeholders are correct. A generated repository asserts the opposite."""
    assert run("init", "--check").returncode == 1


def test_the_example_ontology_is_not_loaded():
    from knowledge.graph import turtle_source
    from knowledge.paths import get_paths
    paths = get_paths(ROOT, "ontology.ttl")
    assert "webapp" not in turtle_source(paths, ["example"])
    assert "Module" not in turtle_source(paths, ["example"])
```

Add `if __name__ == "__main__": raise SystemExit(main())` support by ensuring `src/knowledge/cli.py` already ends with it (it does).

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_template_content.py -v`
Expected: FAIL — `ontology/ontology.ttl` does not exist, so `validate` cannot parse.

- [ ] **Step 3: Write the ontology seed**

Create `ontology/ontology.ttl`:

```turtle
@prefix {{PREFIX}}: <{{BASE_IRI}}ontology#> .
@prefix app:        <{{BASE_IRI}}id/> .
@prefix rdf:        <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:       <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:        <http://www.w3.org/2001/XMLSchema#> .
@prefix skos:       <http://www.w3.org/2004/02/skos/core#> .
@prefix dcterms:    <http://purl.org/dc/terms/> .

# A starting point, not a fixture. Three classes and three properties are enough to write a
# first spec against; ontology/AUTHORING.md is how you grow this into your domain's real
# vocabulary. Delete anything here that your domain has no use for.

{{PREFIX}}:Concept a rdfs:Class ;
    rdfs:label   "Concept"@en ;
    rdfs:comment "A thing the domain is about, independent of how it is presented."@en .

{{PREFIX}}:Rule a rdfs:Class ;
    rdfs:label   "Rule"@en ;
    rdfs:comment "A constraint or invariant the domain enforces."@en .

{{PREFIX}}:Actor a rdfs:Class ;
    rdfs:label   "Actor"@en ;
    rdfs:comment "Who performs something."@en .

{{PREFIX}}:relatesTo a rdf:Property ;
    rdfs:label   "relates to"@en ;
    rdfs:domain  {{PREFIX}}:Concept ;
    rdfs:range   {{PREFIX}}:Concept ;
    rdfs:comment "Read as symmetric, but assert it in whichever direction reads better; the reverse triple is not inferred."@en .

{{PREFIX}}:constrains a rdf:Property ;
    rdfs:label   "constrains"@en ;
    rdfs:domain  {{PREFIX}}:Rule ;
    rdfs:comment "What the rule restricts. No rdfs:range: the values span more than one type, and two ranges would be read as requiring both at once."@en .

{{PREFIX}}:performedBy a rdf:Property ;
    rdfs:label  "performed by"@en ;
    rdfs:range  {{PREFIX}}:Actor .
```

- [ ] **Step 4: Write the example spec**

Create `specs/example/spec.md`:

```markdown
---
id: example
---

# Example

A worked example, so a fresh clone has something to run every command against. `knowledge init` deletes this folder.

Replace it with your first real spec: prose here in `spec.md`, the same claims as triples in `spec.ttl`.

## Rules

An example is deleted on init, because a template that ships someone else's content makes the first real spec harder to write, not easier.
```

Create `specs/example/spec.ttl`:

```turtle
app:Example a {{PREFIX}}:Concept ;
    rdfs:label   "Example"@en ;
    rdfs:comment "A worked example, so a fresh clone has something to run every command against."@en .

app:ExampleIsDeletedOnInit a {{PREFIX}}:Rule ;
    rdfs:label      "The example is deleted on init"@en ;
    rdfs:comment    "A template that ships someone else's content makes the first real spec harder to write, not easier."@en ;
    {{PREFIX}}:constrains app:Example .
```

`specs/example/spec.ttl` carries `{{PREFIX}}` and so must be substituted, even though `init` deletes the folder moments later: `remaining_placeholders` sweeps the whole tree, and an unsubstituted token there would make `init --check` fail in a generated repository for a file that no longer exists. Extend `init.run`'s substitution manifest to cover it alongside the ontology file:

```python
    rewritten = substitute(
        root, values, MANIFEST + (f"ontology/{ontology_file}", "specs/example/spec.ttl")
    )
```

- [ ] **Step 5: Write `ontology/README.md`**

```markdown
# {{PROJECT_NAME}} ontology

The vocabulary every `spec.ttl` is written against. `ontology/{{ONTOLOGY_FILE}}` is the
machine-readable version; this page is what it means.

Replace this page as your vocabulary grows. `ontology/AUTHORING.md` explains how to design
one, and `ontology/examples/webapp.ttl` is a vocabulary that has survived real use.

## Classes

| Class     | What it is                                                       |
| --------- | ---------------------------------------------------------------- |
| `Concept` | A thing the domain is about, independent of how it is presented. |
| `Rule`    | A constraint or invariant the domain enforces.                   |
| `Actor`   | Who performs something.                                          |

## Properties

| Property      | Domain    | Range     | Notes                                                    |
| ------------- | --------- | --------- | -------------------------------------------------------- |
| `relatesTo`   | `Concept` | `Concept` | Read as symmetric; the reverse triple is not inferred.   |
| `constrains`  | `Rule`    | —         | Values span more than one type, so no range is declared. |
| `performedBy` | —         | `Actor`   |                                                          |

## Naming

Fill in the naming conventions your vocabulary uses, and encode them in
`[vocabulary] field_name_pattern` and `underscore_reserved` so `validate --strict` enforces
them rather than trusting them.
```

- [ ] **Step 6: Write `ontology/AUTHORING.md`**

Cover, each as its own `##` section with a worked snippet: designing from the domain rather than the tooling; the naming-convention table and how `field_name_pattern` plus `underscore_reserved` encode it; why `partOf` should not be declared transitive and that a chain needs the SPARQL path `partOf+`; why inverse pairs like `contains`/`partOf` are convention and a query must ask both directions with `p1|^p2`; why a predicate whose values span two types is better with no `rdfs:range` than with two, since RDFS reads two ranges as requiring both at once; what makes a property functional and how listing it in `functional_properties` makes `contradictions` catch a second value; which predicates may go in `verbatim_string_properties` (only ones whose value is a verbatim string, never a paraphrase — a paraphrasing predicate would have every value flagged, none correctly); and a closing checklist mapping each new term to the `[vocabulary]` key that makes a check see it.

- [ ] **Step 7: Write the worked example**

Create `ontology/examples/webapp.ttl` by copying `../monicords-knowledge/ontology/monicords.ttl` verbatim, then replacing `mon:` with `web:`, `https://monicords.com/ontology#` with `https://example.com/ontology#`, and `https://monicords.com/id/` with `https://example.com/id/`. Add a header comment:

```turtle
# A vocabulary for documenting a web application, as a worked example for
# ontology/AUTHORING.md. Nothing loads this file. Copy what your domain needs into
# ontology/{{ONTOLOGY_FILE}}, or copy the whole thing if you are documenting a web app.
```

Create `ontology/examples/webapp.toml`:

```toml
# The knowledge.toml fragment that matches ontology/examples/webapp.ttl. Copy the keys you
# want; nothing reads this file.

[vocabulary]
rule_class                 = "Rule"
concept_class              = "Concept"
concept_spec               = "concepts"
field_class                = "Field"
field_name_pattern         = "^[A-Z][A-Za-z0-9]*_[a-z][A-Za-z0-9]*$"
underscore_reserved        = true
functional_properties      = ["route", "editable", "required", "viewport", "defaultsTo"]
verbatim_string_properties = ["emptyState"]

[[ask]]
name  = "modules"
query = "SELECT ?label WHERE { ?m a web:Module ; rdfs:label ?label } ORDER BY ?label"

[[ask]]
name  = "views and their routes"
query = "SELECT ?label ?route WHERE { ?v a web:View ; rdfs:label ?label ; web:route ?route } ORDER BY ?route"

[[ask]]
name  = "what the user sees only on narrow screens"
query = "SELECT ?label WHERE { ?s web:viewport \"narrow\" ; rdfs:label ?label } ORDER BY ?label"

[[ask]]
name  = "rules, and what each constrains"
query = """
SELECT ?rule ?target WHERE {
  ?r a web:Rule ; rdfs:label ?rule ; web:constrains ?t .
  OPTIONAL { ?t rdfs:label ?tl }
  BIND(COALESCE(?tl, REPLACE(STR(?t), "^.*[#/]", "")) AS ?target)
} ORDER BY ?rule
"""

[[ask]]
name  = "fields the user cannot edit"
query = "SELECT ?label WHERE { ?f web:editable false ; rdfs:label ?label } ORDER BY ?label"

[[ask]]
name  = "concepts and how many things reference them"
query = """
SELECT ?label (COUNT(?s) AS ?references) WHERE {
  ?c a web:Concept ; rdfs:label ?label . ?s ?p ?c .
} GROUP BY ?label ORDER BY DESC(?references)
"""
```

- [ ] **Step 8: Generate the dump and verify**

```bash
uv run knowledge scan
uv run knowledge validate --strict
uv run pytest tests/test_template_content.py -v
```

Expected: `validate` exits 0, reporting `skipped (not configured)` for the checks the seed leaves empty; the tests pass.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: add the ontology seed, the authoring guide and the example spec"
```

---

