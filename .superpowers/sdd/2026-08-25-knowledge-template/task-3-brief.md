### Task 3: Move the ontology filename and the graph namespaces onto the config

**Files:**

- Modify: `src/knowledge/paths.py`
- Modify: `src/knowledge/graph.py`
- Modify: `src/knowledge/cli.py` (`cmd_ask`, `cmd_query`, `cmd_describe`, `cmd_graph`, `cmd_validate`, `cmd_contradictions`)
- Modify: `src/knowledge/scan.py` (import rename only)
- Test: `tests/test_graph.py`, `tests/test_paths.py`, `tests/conftest.py`

**Interfaces:**

- Consumes: `config.Config`, `vocab.Vocabulary` from Task 2.
- Produces:
  - `paths.get_paths(start=None, ontology_file="ontology.ttl") -> Paths`
  - `graph.load_graph(paths, vocab, ids=None) -> Graph`
  - `graph.load_spec_graph(paths, vocab, spec_id) -> Graph`
  - `graph.run_query(g, vocab, sparql) -> list[tuple[str, ...]]`
  - `graph.dangling_terms(g, vocab) -> list[str]`
  - `graph.page_name(spec_id) -> str` (renamed from `wiki_page_name`)
  - `graph.broken_links(paths, ids) -> list[str]`
  - `graph.surveys(config) -> list[tuple[str, str]]`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_graph.py`:

```python
from knowledge import graph
from knowledge.vocab import Vocabulary


def test_load_graph_binds_the_configured_prefixes(repo_with_vocab):
    paths, vocab = repo_with_vocab
    g = graph.load_graph(paths, vocab)
    bound = {prefix: str(iri) for prefix, iri in g.namespaces()}
    assert bound[vocab.prefix] == vocab.namespace
    assert bound[vocab.instance_prefix] == vocab.instances


def test_run_query_prepends_the_configured_prefixes(repo_with_vocab):
    paths, vocab = repo_with_vocab
    g = graph.load_graph(paths, vocab)
    rows = graph.run_query(g, vocab, "SELECT ?l WHERE { ?s a ex:View ; rdfs:label ?l }")
    assert rows == [("Assets",)]


def test_dangling_terms_uses_the_configured_namespaces(repo_with_vocab):
    paths, vocab = repo_with_vocab
    g = graph.load_graph(paths, vocab)
    assert graph.dangling_terms(g, vocab) == []


def test_surveys_come_from_the_config(tmp_path):
    from knowledge.config import Config, Dependencies, Publish, Survey
    config = Config(
        project_name="Example",
        vocabulary=Vocabulary("ontology.ttl", "https://e.test/o#", "https://e.test/id/", "ex", "app"),
        surveys=(Survey(name="everything", query="SELECT ?s WHERE { ?s ?p ?o }"),),
        code_repo=None,
        dependencies=Dependencies(),
        publish=Publish(),
        unconfigured=False,
    )
    assert graph.surveys(config) == [("everything", "SELECT ?s WHERE { ?s ?p ?o }")]
```

In `tests/conftest.py`, rewrite the fixture vocabulary off monicords. Replace the `ONTOLOGY`, `ASSETS_TTL` and `CONCEPTS_TTL` constants and the `repo` fixture with:

```python
ONTOLOGY = """\
@prefix ex:      <https://example.test/ontology#> .
@prefix app:     <https://example.test/id/> .
@prefix rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .
@prefix skos:    <http://www.w3.org/2004/02/skos/core#> .
@prefix dcterms: <http://purl.org/dc/terms/> .

ex:InterfaceElement a rdfs:Class ; rdfs:label "Interface element"@en .
ex:Module a rdfs:Class ; rdfs:subClassOf ex:InterfaceElement ; rdfs:label "Module"@en .
ex:View a rdfs:Class ; rdfs:subClassOf ex:InterfaceElement ; rdfs:label "View"@en .
ex:Section a rdfs:Class ; rdfs:subClassOf ex:InterfaceElement ; rdfs:label "Section"@en .
ex:Field a rdfs:Class ; rdfs:label "Field"@en .
ex:Action a rdfs:Class ; rdfs:label "Action"@en .
ex:Concept a rdfs:Class ; rdfs:label "Domain concept"@en .
ex:Rule a rdfs:Class ; rdfs:label "Rule"@en .

ex:contains a rdf:Property ; rdfs:label "contains"@en ;
    rdfs:domain ex:InterfaceElement ; rdfs:range ex:InterfaceElement .
ex:partOf a rdf:Property ; rdfs:label "part of"@en ;
    rdfs:domain ex:InterfaceElement ; rdfs:range ex:InterfaceElement .
ex:displays a rdf:Property ; rdfs:label "displays"@en ;
    rdfs:domain ex:InterfaceElement ; rdfs:range ex:Field .
ex:scopedTo a rdf:Property ; rdfs:label "scoped to"@en ;
    rdfs:domain ex:InterfaceElement ; rdfs:range ex:Concept .
ex:appliesTo a rdf:Property ; rdfs:label "applies to"@en ; rdfs:domain ex:Rule .
ex:relatesTo a rdf:Property ; rdfs:label "relates to"@en ;
    rdfs:domain ex:Concept ; rdfs:range ex:Concept .
ex:route a rdf:Property ; rdfs:label "route"@en ;
    rdfs:domain ex:View ; rdfs:range xsd:string .
ex:endpoint a rdf:Property ; rdfs:label "endpoint"@en ;
    rdfs:domain ex:Action ; rdfs:range xsd:string .
ex:emptyState a rdf:Property ; rdfs:label "empty state"@en ;
    rdfs:domain ex:InterfaceElement ; rdfs:range xsd:string .
ex:format a rdf:Property ; rdfs:label "format"@en ;
    rdfs:domain ex:Field ; rdfs:range xsd:string .
"""

ASSETS_TTL = """\
app:Assets a ex:View ;
    rdfs:label   "Assets"@en ;
    ex:route     "/platform/assets" ;
    ex:scopedTo  app:Workspace .
"""

CONCEPTS_TTL = """\
app:Workspace a ex:Concept ;
    rdfs:label "Workspace"@en .
"""

CONFIG_TOML = """\
[project]
name = "Example"

[vocabulary]
ontology_file = "ontology.ttl"
namespace = "https://example.test/ontology#"
instances = "https://example.test/id/"
prefix = "ex"
instance_prefix = "app"
rule_class = "Rule"
concept_class = "Concept"
concept_spec = "concepts"
field_class = "Field"
field_name_pattern = "^[A-Z][A-Za-z0-9]*_[a-z][A-Za-z0-9]*$"
underscore_reserved = true
functional_properties = ["route", "editable", "required", "viewport", "defaultsTo"]
verbatim_string_properties = ["emptyState"]

[repo]
code_repo = "../code"

[dependencies]
route_property = "route"
endpoint_property = "endpoint"
route_glob = "app/**/{segments}/page.tsx"
endpoint_glob = "app/{path}/**/route.ts"
absorbed_prefixes = ["platform"]

[publish]
target = "github-wiki"
remote = "https://example.com/x.wiki.git"
"""
```

and rewrite the fixture:

```python
@pytest.fixture
def repo(tmp_path):
    """A knowledge repository with an ontology and two specs."""
    (tmp_path / "knowledge.toml").write_text(CONFIG_TOML, encoding="utf-8")
    ontology = tmp_path / "ontology"
    ontology.mkdir()
    (ontology / "ontology.ttl").write_text(ONTOLOGY, encoding="utf-8")
    (ontology / "README.md").write_text("# Ontology\n\nThe vocabulary.\n", encoding="utf-8")
    (ontology / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    (tmp_path / ".metadata").mkdir()

    write_spec(tmp_path, "assets", ASSETS_TTL, "The Assets screen. See [Concepts](Concepts).\n")
    write_spec(tmp_path, "concepts", CONCEPTS_TTL)
    return paths_mod.get_paths(tmp_path)


@pytest.fixture
def config(repo):
    from knowledge.config import load_config
    return load_config(repo.root)


@pytest.fixture
def repo_with_vocab(repo, config):
    return repo, config.vocabulary
```

Every existing test referencing `mon:` or `https://monicords.com/` must be updated to `ex:` and `https://example.test/`. Search with `rg 'mon:|monicords' tests/` and fix each hit.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_graph.py -v`
Expected: FAIL — `load_graph()` takes 2 positional arguments but 3 were given, and `graph.surveys` does not exist.

- [ ] **Step 3: Update `paths.py`**

```python
def get_paths(start: Path | None = None, ontology_file: str = "ontology.ttl") -> Paths:
    root = find_root(start)
    ontology = root / "ontology"
    metadata = root / ".metadata"
    return Paths(
        root=root,
        specs=root / "specs",
        ontology=ontology,
        ontology_ttl=ontology / ontology_file,
        ontology_readme=ontology / "README.md",
        ontology_version=ontology / "VERSION",
        metadata=metadata,
        db=metadata / "knowledge.db",
        dump=metadata / "dump.sql",
    )
```

- [ ] **Step 4: Update `graph.py`**

Delete `MON`, `APP` and `SPARQL_PREFIXES`. Delete `SANITY_QUERIES`. Rename `wiki_page_name` to `page_name` and update its importers (`scan.py`, `publish.py`). Change the signatures:

```python
def load_graph(paths: Paths, vocab: Vocabulary, ids: Sequence[str] | None = None) -> Graph:
    g = Graph()
    g.bind(vocab.prefix, vocab.namespace)
    g.bind(vocab.instance_prefix, vocab.instances)
    g.parse(data=turtle_source(paths, spec_ids(paths) if ids is None else ids), format="turtle")
    return g


def load_spec_graph(paths: Paths, vocab: Vocabulary, spec_id: str) -> Graph:
    """The ontology plus one spec, so the spec's own triples can be isolated."""
    return load_graph(paths, vocab, [spec_id])


def run_query(g: Graph, vocab: Vocabulary, sparql: str) -> list[tuple[str, ...]]:
    return [tuple(str(value) for value in row) for row in g.query(vocab.sparql_prefixes + sparql)]


def dangling_terms(g: Graph, vocab: Vocabulary) -> list[str]:
    typed = {s for s in g.subjects(RDF.type, None) if isinstance(s, URIRef)}
    used = {
        term
        for triple in g
        for term in triple
        if isinstance(term, URIRef) and (vocab.is_term(term) or vocab.is_instance(term))
    }
    return sorted(str(term) for term in used - typed)


def surveys(config) -> list[tuple[str, str]]:
    """The `ask` presets, in the order knowledge.toml declares them."""
    return [(survey.name, survey.query) for survey in config.surveys]
```

- [ ] **Step 5: Update `cli.py`'s graph callers**

`open_repo` now builds `Paths` with the configured ontology filename:

```python
def open_repo(_args: argparse.Namespace) -> tuple[Paths, Config, sqlite3.Connection]:
    root = find_root()
    config = load_config(root)
    paths = get_paths(root, config.vocabulary.ontology_file)
    return paths, config, db.connect(paths)
```

Import `find_root` alongside `get_paths`. Then pass `config.vocabulary` into every `graph.load_graph`, `graph.run_query` and `graph.dangling_terms` call. In `cmd_describe`, the bare-term default becomes the configured instance prefix:

```python
term = args.term if ":" in args.term else f"{config.vocabulary.instance_prefix}:{args.term}"
```

In `cmd_ask`, iterate `graph.surveys(config)` and print a clear message when it is empty:

```python
presets = graph.surveys(config)
if not presets:
    print("no `ask` presets configured — add [[ask]] tables to knowledge.toml")
    return 0
```

- [ ] **Step 6: Run the whole suite**

Run: `uv run pytest -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: build the graph from the configured vocabulary"
```

---

