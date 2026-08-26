### Task 2: Configuration schema and vocabulary object

Replace the two-field `Config` with the full schema, add `Vocabulary`, and thread both through `cli.open_repo`. No behaviour changes yet — every module still uses its module-level constants — but every later task has something to read from.

**Files:**

- Create: `src/knowledge/vocab.py`
- Modify: `src/knowledge/config.py` (whole file)
- Modify: `src/knowledge/cli.py` (`open_repo` and its call sites)
- Modify: `knowledge.toml`
- Test: `tests/test_config.py`, `tests/test_vocab.py`

**Interfaces:**

- Consumes: nothing.
- Produces:
  - `vocab.Vocabulary(ontology_file: str, namespace: str, instances: str, prefix: str, instance_prefix: str, checks: Checks)` with methods `term(local) -> URIRef`, `instance(local) -> URIRef`, `is_term(iri) -> bool`, `is_instance(iri) -> bool`, `qname(iri) -> str`, and property `sparql_prefixes -> str`.
  - `vocab.Checks(rule_class, concept_class, concept_spec, field_class, field_name_pattern, underscore_reserved, functional_properties, verbatim_string_properties)`.
  - `config.Config(project_name, vocabulary, surveys, code_repo, dependencies, publish, unconfigured)`; `config.Survey(name, query)`; `config.Dependencies(...)` with property `derives -> bool`; `config.Publish(target, remote, out_dir, committer_name, committer_email, sidebar)`; `config.Sidebar(title, order, reference, nested_under, header_before, labels)`; `config.ConfigError`.
  - `config.load_config(root: Path) -> Config`.
  - `cli.open_repo(args) -> tuple[Paths, Config, sqlite3.Connection]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_vocab.py`:

```python
from rdflib import URIRef

from knowledge.vocab import Checks, Vocabulary


def make() -> Vocabulary:
    return Vocabulary(
        ontology_file="ontology.ttl",
        namespace="https://example.com/ontology#",
        instances="https://example.com/id/",
        prefix="ex",
        instance_prefix="app",
        checks=Checks(),
    )


def test_term_and_instance_build_iris():
    v = make()
    assert v.term("Rule") == URIRef("https://example.com/ontology#Rule")
    assert v.instance("Assets") == URIRef("https://example.com/id/Assets")


def test_is_term_and_is_instance_discriminate():
    v = make()
    assert v.is_term(v.term("Rule"))
    assert not v.is_term(v.instance("Assets"))
    assert v.is_instance(v.instance("Assets"))
    assert not v.is_instance(URIRef("http://elsewhere.test/x"))


def test_qname_shortens_known_namespaces_and_passes_others_through():
    v = make()
    assert v.qname(v.term("Rule")) == "ex:Rule"
    assert v.qname(v.instance("Assets")) == "app:Assets"
    assert v.qname(URIRef("http://elsewhere.test/x")) == "http://elsewhere.test/x"


def test_sparql_prefixes_declare_both_project_namespaces_and_the_fixed_ones():
    block = make().sparql_prefixes
    assert "PREFIX ex: <https://example.com/ontology#>" in block
    assert "PREFIX app: <https://example.com/id/>" in block
    assert "PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>" in block
    assert "PREFIX skos:" in block
```

Create `tests/test_config.py`:

```python
import pytest

from knowledge.config import ConfigError, load_config

FULL = """\
[project]
name = "Example"

[vocabulary]
ontology_file = "example.ttl"
namespace = "https://example.com/ontology#"
instances = "https://example.com/id/"
prefix = "ex"
instance_prefix = "app"
rule_class = "Rule"
concept_class = "Concept"
concept_spec = "concepts"
field_class = "Field"
field_name_pattern = "^[A-Z][A-Za-z0-9]*_[a-z][A-Za-z0-9]*$"
underscore_reserved = true
functional_properties = ["route", "editable"]
verbatim_string_properties = ["emptyState"]

[[ask]]
name = "modules"
query = "SELECT ?l WHERE { ?m a ex:Module ; rdfs:label ?l }"

[repo]
code_repo = "../code"

[dependencies]
route_property = "route"
route_glob = "app/**/{segments}/page.tsx"
absorbed_prefixes = ["platform"]

[publish]
target = "github-wiki"
remote = "https://example.com/x.wiki.git"

[publish.sidebar]
title = "Example"
order = ["home", "concepts"]
nested_under = { "concepts" = "home" }
"""

MINIMAL = """\
[project]
name = "Example"

[vocabulary]
ontology_file = "ontology.ttl"
namespace = "https://example.com/ontology#"
instances = "https://example.com/id/"
prefix = "ex"
instance_prefix = "app"
"""


def write(tmp_path, text):
    (tmp_path / "knowledge.toml").write_text(text, encoding="utf-8")
    return tmp_path


def test_full_config_round_trips(tmp_path):
    config = load_config(write(tmp_path, FULL))
    assert config.project_name == "Example"
    assert config.vocabulary.prefix == "ex"
    assert config.vocabulary.checks.functional_properties == ("route", "editable")
    assert config.vocabulary.checks.underscore_reserved is True
    assert [s.name for s in config.surveys] == ["modules"]
    assert config.code_repo is not None and config.code_repo.name == "code"
    assert config.dependencies.absorbed_prefixes == ("platform",)
    assert config.publish.target == "github-wiki"
    assert config.publish.sidebar.nested_under == {"concepts": "home"}


def test_minimal_config_defaults_every_optional_section(tmp_path):
    config = load_config(write(tmp_path, MINIMAL))
    assert config.vocabulary.checks.rule_class == ""
    assert config.surveys == ()
    assert config.code_repo is None
    assert config.dependencies.derives is False
    assert config.publish.target == "none"
    assert config.publish.sidebar.order == ()


def test_placeholders_read_as_empty(tmp_path):
    text = MINIMAL + '\n[repo]\ncode_repo = "{{CODE_REPO}}"\n'
    config = load_config(write(tmp_path, text))
    assert config.code_repo is None


def test_template_marker_is_reported(tmp_path):
    text = "[template]\nunconfigured = true\n\n" + MINIMAL
    assert load_config(write(tmp_path, text)).unconfigured is True
    assert load_config(write(tmp_path, MINIMAL)).unconfigured is False


def test_missing_required_key_names_it(tmp_path):
    text = '[project]\nname = "Example"\n\n[vocabulary]\nprefix = "ex"\n'
    with pytest.raises(ConfigError) as exc:
        load_config(write(tmp_path, text))
    assert "vocabulary.namespace" in str(exc.value)


def test_unknown_publish_target_is_rejected(tmp_path):
    text = MINIMAL + '\n[publish]\ntarget = "carrier-pigeon"\n'
    with pytest.raises(ConfigError) as exc:
        load_config(write(tmp_path, text))
    assert "carrier-pigeon" in str(exc.value)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_vocab.py tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'knowledge.vocab'` and `ImportError: cannot import name 'ConfigError'`.

- [ ] **Step 3: Write `src/knowledge/vocab.py`**

```python
"""The project's vocabulary, as configuration rather than as constants.

Every namespace, prefix and check-term the tooling needs is here, so a knowledge base can
declare whatever vocabulary its domain calls for and the mechanical checks still know which
of its terms they are about.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rdflib import URIRef

# Standard vocabularies every knowledge base gets for free. Not configurable: a project
# that redefines rdfs: is not a project this tooling can help.
FIXED_PREFIXES = {
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "dcterms": "http://purl.org/dc/terms/",
}


@dataclass(frozen=True)
class Checks:
    """Which of the project's own terms each configurable check is about.

    An empty value disables its check. The check then returns None rather than an empty
    list, so a caller can print "skipped" instead of a pass nobody earned.
    """

    rule_class: str = ""
    concept_class: str = ""
    concept_spec: str = ""
    field_class: str = ""
    field_name_pattern: str = ""
    underscore_reserved: bool = False
    functional_properties: tuple[str, ...] = ()
    verbatim_string_properties: tuple[str, ...] = ()


@dataclass(frozen=True)
class Vocabulary:
    ontology_file: str
    namespace: str
    instances: str
    prefix: str
    instance_prefix: str
    checks: Checks = field(default_factory=Checks)

    def term(self, local: str) -> URIRef:
        return URIRef(self.namespace + local)

    def instance(self, local: str) -> URIRef:
        return URIRef(self.instances + local)

    def is_term(self, iri) -> bool:
        return str(iri).startswith(self.namespace)

    def is_instance(self, iri) -> bool:
        return str(iri).startswith(self.instances)

    def qname(self, iri) -> str:
        text = str(iri)
        if text.startswith(self.namespace):
            return f"{self.prefix}:{text[len(self.namespace):]}"
        if text.startswith(self.instances):
            return f"{self.instance_prefix}:{text[len(self.instances):]}"
        return text

    @property
    def sparql_prefixes(self) -> str:
        lines = [
            f"PREFIX {self.prefix}: <{self.namespace}>",
            f"PREFIX {self.instance_prefix}: <{self.instances}>",
        ]
        lines += [f"PREFIX {name}: <{iri}>" for name, iri in FIXED_PREFIXES.items()]
        return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Write `src/knowledge/config.py`**

Replace the whole file:

```python
"""knowledge.toml — every value that is about this project rather than about the tooling.

The namespaces, the terms the mechanical checks are about, the preset surveys, where the
code repository lives, how a route becomes a file glob, and where pages publish to. None of
it is hardcoded, so the same tooling serves a knowledge base about anything.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from knowledge.vocab import Checks, Vocabulary

PLACEHOLDER = re.compile(r"^\{\{[A-Z_]+\}\}$")
TARGETS = ("none", "directory", "github-wiki")


class ConfigError(RuntimeError):
    """knowledge.toml is missing a required key, or holds a value it cannot hold."""


@dataclass(frozen=True)
class Survey:
    name: str
    query: str


@dataclass(frozen=True)
class Dependencies:
    route_property: str = ""
    endpoint_property: str = ""
    route_glob: str = ""
    endpoint_glob: str = ""
    absorbed_prefixes: tuple[str, ...] = ()
    dynamic_segment: str = "{...}"
    dynamic_replacement: str = "*"

    @property
    def derives(self) -> bool:
        """Whether any glob can be derived from the graph at all. False leaves manual
        globs as the only dependency source, which is the shipped default."""
        return bool(self.route_property and self.route_glob) or bool(
            self.endpoint_property and self.endpoint_glob
        )


@dataclass(frozen=True)
class Sidebar:
    title: str = ""
    order: tuple[str, ...] = ()
    reference: tuple[str, ...] = ()
    nested_under: dict[str, str] = field(default_factory=dict)
    header_before: dict[str, str] = field(default_factory=dict)
    labels: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Publish:
    target: str = "none"
    remote: str = ""
    out_dir: str = ""
    committer_name: str = "github-actions[bot]"
    committer_email: str = "41898282+github-actions[bot]@users.noreply.github.com"
    sidebar: Sidebar = field(default_factory=Sidebar)


@dataclass(frozen=True)
class Config:
    project_name: str
    vocabulary: Vocabulary
    surveys: tuple[Survey, ...]
    code_repo: Path | None
    dependencies: Dependencies
    publish: Publish
    unconfigured: bool


def _clean(value) -> str:
    """An unsubstituted {{PLACEHOLDER}} reads as empty, so the shipped template loads."""
    text = str(value or "")
    return "" if PLACEHOLDER.match(text) else text


def _required(table: dict, section: str, key: str) -> str:
    value = _clean(table.get(key))
    if not value:
        raise ConfigError(f"knowledge.toml: {section}.{key} is required")
    return value


def _vocabulary(data: dict) -> Vocabulary:
    table = data.get("vocabulary", {})
    checks = Checks(
        rule_class=_clean(table.get("rule_class")),
        concept_class=_clean(table.get("concept_class")),
        concept_spec=_clean(table.get("concept_spec")),
        field_class=_clean(table.get("field_class")),
        field_name_pattern=_clean(table.get("field_name_pattern")),
        underscore_reserved=bool(table.get("underscore_reserved", False)),
        functional_properties=tuple(table.get("functional_properties", ())),
        verbatim_string_properties=tuple(table.get("verbatim_string_properties", ())),
    )
    return Vocabulary(
        ontology_file=_clean(table.get("ontology_file")) or "ontology.ttl",
        namespace=_required(table, "vocabulary", "namespace"),
        instances=_required(table, "vocabulary", "instances"),
        prefix=_required(table, "vocabulary", "prefix"),
        instance_prefix=_clean(table.get("instance_prefix")) or "app",
        checks=checks,
    )


def _publish(data: dict) -> Publish:
    table = data.get("publish", {})
    target = _clean(table.get("target")) or "none"
    if target not in TARGETS:
        raise ConfigError(
            f"knowledge.toml: publish.target is {target!r}; expected one of {', '.join(TARGETS)}"
        )
    bar = table.get("sidebar", {})
    return Publish(
        target=target,
        remote=_clean(table.get("remote")),
        out_dir=_clean(table.get("out_dir")),
        committer_name=_clean(table.get("committer_name")) or Publish.committer_name,
        committer_email=_clean(table.get("committer_email")) or Publish.committer_email,
        sidebar=Sidebar(
            title=_clean(bar.get("title")),
            order=tuple(bar.get("order", ())),
            reference=tuple(bar.get("reference", ())),
            nested_under=dict(bar.get("nested_under", {})),
            header_before=dict(bar.get("header_before", {})),
            labels=dict(bar.get("labels", {})),
        ),
    )


def load_config(root: Path) -> Config:
    with (root / "knowledge.toml").open("rb") as handle:
        data = tomllib.load(handle)

    code_repo = _clean(data.get("repo", {}).get("code_repo"))
    deps = data.get("dependencies", {})

    return Config(
        project_name=_clean(data.get("project", {}).get("name")),
        vocabulary=_vocabulary(data),
        surveys=tuple(
            Survey(name=_clean(row.get("name")), query=_clean(row.get("query")))
            for row in data.get("ask", ())
        ),
        code_repo=(root / code_repo).resolve() if code_repo else None,
        dependencies=Dependencies(
            route_property=_clean(deps.get("route_property")),
            endpoint_property=_clean(deps.get("endpoint_property")),
            route_glob=_clean(deps.get("route_glob")),
            endpoint_glob=_clean(deps.get("endpoint_glob")),
            absorbed_prefixes=tuple(deps.get("absorbed_prefixes", ())),
            dynamic_segment=_clean(deps.get("dynamic_segment")) or "{...}",
            dynamic_replacement=_clean(deps.get("dynamic_replacement")) or "*",
        ),
        publish=_publish(data),
        unconfigured=bool(data.get("template", {}).get("unconfigured", False)),
    )
```

- [ ] **Step 5: Run the new tests**

Run: `uv run pytest tests/test_vocab.py tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 6: Thread the config through `cli.open_repo`**

In `src/knowledge/cli.py`, change `open_repo` to load the config:

```python
def open_repo(_args: argparse.Namespace) -> tuple[Paths, Config, sqlite3.Connection]:
    paths = get_paths()
    return paths, load_config(paths.root), db.connect(paths)
```

Add `from knowledge.config import Config, load_config` to the imports. Then update every call site: each `paths, conn = open_repo(args)` becomes `paths, config, conn = open_repo(args)`, and each `paths, _ = open_repo(args)` becomes `paths, config, _ = open_repo(args)`. Where a command does not yet use `config`, name it `_config` so linting stays quiet. `cmd_stale` and `cmd_publish` currently call `load_config` themselves — delete those calls and use the threaded value.

- [ ] **Step 7: Replace `knowledge.toml` with the full template**

Write `../knowledge-template/knowledge.toml` exactly as the spec's Configuration section shows it, including the `[template]` table, the `{{PROJECT_NAME}}` / `{{BASE_IRI}}` / `{{PREFIX}}` / `{{CODE_REPO}}` placeholders, and the single starter `[[ask]]` survey.

- [ ] **Step 8: Run the whole suite**

Run: `uv run pytest -v`
Expected: PASS. Tests that build their own `knowledge.toml` in `tmp_path` (`tests/test_cli_*.py`, `tests/conftest.py`) may need their fixture TOML extended with the now-required `[vocabulary]` keys — update `conftest.repo` to write the full minimal TOML, keeping the monicords namespaces for now since the modules still use their constants.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: read the full project configuration from knowledge.toml"
```

---

