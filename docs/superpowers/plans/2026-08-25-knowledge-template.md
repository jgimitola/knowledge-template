# knowledge-template Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract this repository's knowledge-base tooling into a public GitHub template repository where every monicords-specific decision is configuration, not code.

**Architecture:** A new sibling repository `../knowledge-template` receives a copy of `src/knowledge/`, `tests/`, and the hook configuration. Every hardcoded monicords term — the `mon:`/`app:` IRIs, the ontology filename, the five vocabulary-aware lint checks, the functional-property list, the six `ask` surveys, the Next.js route globs, the five sidebar constants — moves into `knowledge.toml`, read through a new `config.Config` and a new `vocab.Vocabulary`. A new `knowledge init` substitutes `{{PLACEHOLDER}}` tokens across a small manifest and removes the example content. This repository is never modified.

**Tech Stack:** Python 3.13, rdflib, sqlite3, argparse, pytest, pre-commit, prettier, uv.

**Spec:** `docs/superpowers/specs/2026-08-25-knowledge-template-design.md` (in monicords-knowledge, alongside this plan)

## Global Constraints

- **Work happens in `../knowledge-template`, never in `../monicords-knowledge`.** The only file this plan writes inside monicords-knowledge is nothing — the spec and this plan already exist. Read from monicords-knowledge freely; write to it never.
- **Python `requires-python = ">=3.13"`.**
- **Exact dependency versions, no `^` or `~` ranges:** `rdflib==7.6.0`, `pytest==8.3.4`, `pre-commit==4.4.0`.
- **All files LF, no trailing whitespace.** `.gitattributes` sets `* text=auto eol=lf`.
- **Markdown and YAML are formatted by prettier with `proseWrap: preserve`.** Never rewrap existing prose paragraphs.
- **No monicords prose, spec content, IRI or project name ships in the template.** The single exception is `ontology/examples/webapp.ttl` plus `ontology/examples/webapp.toml`, which carry the monicords _vocabulary_ (not its specs) as a worked example that nothing loads.
- **A check that cannot run says so.** A configurable check whose configuration is empty returns `None`, and the caller prints `skipped (not configured)`. It never prints a pass.
- **Commit after every task.** Conventional commit messages (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).

---

## File Structure

**New modules:**

| File                     | Responsibility                                                                                                                                                     |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `src/knowledge/vocab.py` | `Vocabulary` and `Checks` dataclasses: namespaces, prefixes, IRI construction, qname rendering, SPARQL prefix block, and which terms each configurable check uses. |
| `src/knowledge/init.py`  | Placeholder substitution, the file manifest, the example-content teardown, and the two guards.                                                                     |

**Modified modules:** `config.py` (schema), `paths.py` (ontology filename), `graph.py` (namespaces, prefixes, surveys, page naming), `lint.py` (five checks), `contradictions.py` (functional properties), `deps.py` (glob templates), `publish.py` (sidebar, targets), `cli.py` (threading, `init`, skipped output), `tests/conftest.py` (fixture vocabulary).

**Removed:** `scripts/` (monicords migration one-offs), `.github/workflows/` (recipes instead).

**New content:** `ontology/{ontology.ttl,AUTHORING.md,README.md,VERSION}`, `ontology/examples/{webapp.ttl,webapp.toml}`, `presets/nextjs.toml`, `specs/example/{spec.md,spec.ttl}`, `docs/{GUIDE.md,README.template.md}`, `docs/recipes/{github-actions,github-wiki-publishing,nextjs-dependencies}.md`, `.claude/agents/{interviewer,writer}.md`, `integrations/code-repo/.claude/skills/knowledge-base/SKILL.md`, `README.md`, `LICENSE`.

---

### Task 1: Bootstrap the template repository

Create the new repository with the files that need no changes, and prove the copied test suite passes before anything is edited. Nothing monicords-specific in content is copied — but the _code_ still contains monicords constants at this point, and that is expected: Tasks 2–9 remove them.

**Files:**

- Create: `../knowledge-template/` (git repository)
- Copy verbatim from `../monicords-knowledge/`: `src/knowledge/*.py`, `tests/*.py`, `uv.lock`, `.gitignore`, `.pre-commit-config.yaml`, `.prettierrc.mjs`, `.prettierignore`, `.gitattributes`
- Create: `../knowledge-template/pyproject.toml`
- Create: `../knowledge-template/knowledge.toml` (temporary, replaced in Task 2)
- Create: `../knowledge-template/ontology/VERSION`

**Interfaces:**

- Consumes: nothing.
- Produces: a repository at `../knowledge-template` where `uv run pytest` passes, and where `uv run knowledge --help` runs.

- [ ] **Step 1: Create the repository and copy the files that need no editing**

Run from `../monicords-knowledge`:

```bash
mkdir -p ../knowledge-template
cd ../knowledge-template
git init -b main
mkdir -p src/knowledge tests ontology
cp ../monicords-knowledge/src/knowledge/*.py src/knowledge/
cp ../monicords-knowledge/tests/*.py tests/
cp ../monicords-knowledge/uv.lock .
cp ../monicords-knowledge/.gitignore .
cp ../monicords-knowledge/.pre-commit-config.yaml .
cp ../monicords-knowledge/.prettierrc.mjs .
cp ../monicords-knowledge/.prettierignore .
cp ../monicords-knowledge/.gitattributes .
printf '1.0.0\n' > ontology/VERSION
```

Do **not** copy `scripts/`, `specs/`, `.metadata/`, `.github/`, `docs/`, `README.md`, `knowledge.toml`, or `.claude/`.

- [ ] **Step 2: Write `pyproject.toml`**

Create `../knowledge-template/pyproject.toml`:

```toml
[project]
name = "knowledge"
version = "0.1.0"
description = "Authoring, tracking and publishing for a knowledge base"
requires-python = ">=3.13"
dependencies = [
    "rdflib==7.6.0",
]

[project.scripts]
knowledge = "knowledge.cli:main"

[dependency-groups]
dev = [
    "pre-commit==4.4.0",
    "pytest==8.3.4",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/knowledge"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 3: Write a temporary `knowledge.toml` so `paths.find_root` works**

Create `../knowledge-template/knowledge.toml`:

```toml
[repo]
code_repo = ""

[wiki]
remote = ""
```

- [ ] **Step 4: Run the copied test suite**

Run: `cd ../knowledge-template && uv sync --all-extras --dev && uv run pytest -v`
Expected: PASS. Every test builds its own fixture repository in `tmp_path`, so none of them needs the files that were not copied.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: seed the template from monicords-knowledge's tooling"
```

---

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

### Task 6: Configure the dependency globs

**Files:**

- Modify: `src/knowledge/deps.py`
- Modify: `src/knowledge/cli.py` (`cmd_stale`, `cmd_dep`)
- Create: `presets/nextjs.toml`
- Test: `tests/test_deps.py`

**Interfaces:**

- Consumes: `config.Dependencies` from Task 2; `graph.load_spec_graph` / `graph.run_query` from Task 3.
- Produces:
  - `deps.route_to_glob(route: str, settings: Dependencies) -> str`
  - `deps.endpoint_to_glob(endpoint: str, settings: Dependencies) -> str`
  - `deps.derived_globs(paths, config, spec_id) -> set[str]`
  - `deps.spec_globs(conn, paths, config, spec_id) -> set[str]`
  - `deps.check(conn, paths, config, demote, code_repo=None) -> list[tuple[str, list[str]]]`
  - `deps.uncheckable(conn, paths, config) -> list[str]`

- [ ] **Step 1: Write the failing tests**

Replace the glob tests in `tests/test_deps.py`:

```python
from knowledge import deps
from knowledge.config import Dependencies

NEXTJS = Dependencies(
    route_property="route",
    endpoint_property="endpoint",
    route_glob="app/**/{segments}/page.tsx",
    endpoint_glob="app/{path}/**/route.ts",
    absorbed_prefixes=("platform",),
)


def test_route_glob_absorbs_the_configured_prefix():
    assert deps.route_to_glob("/platform/assets", NEXTJS) == "app/**/assets/page.tsx"


def test_route_glob_replaces_dynamic_segments():
    assert (
        deps.route_to_glob("/platform/incomes/{incomeSourceId}", NEXTJS)
        == "app/**/incomes/*/page.tsx"
    )


def test_route_glob_leaves_unabsorbed_prefixes_alone():
    assert deps.route_to_glob("/settings/profile", NEXTJS) == "app/**/settings/profile/page.tsx"


def test_endpoint_glob_tolerates_a_leading_method():
    assert deps.endpoint_to_glob("GET /api/cron", NEXTJS) == "app/api/cron/**/route.ts"


def test_a_different_framework_needs_no_code_change():
    django = Dependencies(
        route_property="route",
        route_glob="apps/**/{segments}/views.py",
        dynamic_segment="<...>",
    )
    assert deps.route_to_glob("/reports/<year>", django) == "apps/**/reports/*/views.py"


def test_derived_globs_are_empty_when_nothing_is_configured(repo, config):
    from dataclasses import replace
    plain = replace(config, dependencies=Dependencies())
    assert deps.derived_globs(repo, plain, "assets") == set()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_deps.py -v`
Expected: FAIL — `route_to_glob()` takes 1 positional argument but 2 were given.

- [ ] **Step 3: Rewrite the derivation in `deps.py`**

Delete `DYNAMIC_SEGMENT` and `ROUTE_PREFIXES_ABSORBED_BY_GLOB`. Then:

```python
def _dynamic_delimiters(settings: Dependencies) -> tuple[str, str]:
    """`{...}` -> ("{", "}"), `<...>` -> ("<", ">"). The syntax a project writes dynamic
    route segments in is the project's, not this tool's."""
    opening, _, closing = settings.dynamic_segment.partition("...")
    return opening, closing


def route_to_glob(route: str, settings: Dependencies) -> str:
    """A route says nothing about directories a framework inserts and the URL omits, so an
    absorbed prefix is dropped and the glob's ** covers it. A dynamic segment becomes the
    configured replacement, matching whatever the real directory is called."""
    opening, closing = _dynamic_delimiters(settings)
    segments = [part for part in route.strip("/").split("/") if part]
    if segments and segments[0] in settings.absorbed_prefixes:
        segments = segments[1:]
    segments = [
        settings.dynamic_replacement
        if part.startswith(opening) and part.endswith(closing)
        else part
        for part in segments
    ]
    return settings.route_glob.replace("{segments}", "/".join(segments))


def endpoint_to_glob(endpoint: str, settings: Dependencies) -> str:
    path = endpoint.split()[-1]  # tolerate "GET /api/cron" as well as "/api/cron"
    return settings.endpoint_glob.replace("{path}", path.strip("/"))


def derived_globs(paths: Paths, config: Config, spec_id: str) -> set[str]:
    settings = config.dependencies
    if not settings.derives:
        return set()
    g = load_spec_graph(paths, config.vocabulary, spec_id)
    vocab = config.vocabulary
    globs: set[str] = set()
    if settings.route_property and settings.route_glob:
        rows = run_query(g, vocab, f"SELECT ?r WHERE {{ ?s {vocab.prefix}:{settings.route_property} ?r }}")
        globs |= {route_to_glob(row[0], settings) for row in rows}
    if settings.endpoint_property and settings.endpoint_glob:
        rows = run_query(g, vocab, f"SELECT ?e WHERE {{ ?s {vocab.prefix}:{settings.endpoint_property} ?e }}")
        globs |= {endpoint_to_glob(row[0], settings) for row in rows}
    return globs
```

Thread `config` in place of `paths, config` pairs through `spec_globs`, `check` and `uncheckable`, replacing their `Config`-typed `config` parameter usage: `check` already takes `config` and reads `config.code_repo`, which is now `Path | None`. Guard it:

```python
    root = code_repo if code_repo is not None else config.code_repo
    if root is None:
        raise RuntimeError(
            "no code repository configured — set repo.code_repo in knowledge.toml,"
            " or pass --code-repo"
        )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_deps.py -v`
Expected: PASS.

- [ ] **Step 5: Write the Next.js preset**

Create `presets/nextjs.toml`:

```toml
# Copy this into your knowledge.toml to derive file globs from routes and endpoints in a
# Next.js App Router project. It is data, not something the tooling reads from here.
#
# `platform` is absorbed because /platform/assets lives at
# app/platform/(menuLayout)/assets/page.tsx: the route group sits between `platform` and the
# module, so the segment is dropped and the ** covers both it and the group.
# A dynamic segment like {incomeSourceId} becomes *, matching [incomeSourceId] on disk.
[dependencies]
route_property      = "route"
endpoint_property   = "endpoint"
route_glob          = "app/**/{segments}/page.tsx"
endpoint_glob       = "app/{path}/**/route.ts"
absorbed_prefixes   = ["platform"]
dynamic_segment     = "{...}"
dynamic_replacement = "*"
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: derive dependency globs from configured patterns"
```

---

### Task 7: Configure publishing

**Files:**

- Modify: `src/knowledge/publish.py`
- Modify: `src/knowledge/cli.py` (`cmd_publish`)
- Test: `tests/test_publish.py`, `tests/test_cli_publish.py`

**Interfaces:**

- Consumes: `config.Publish`, `config.Sidebar` from Task 2; `graph.page_name` from Task 3.
- Produces:
  - `publish.render_sidebar(conn, sidebar: Sidebar) -> str`
  - `publish.write_pages(conn, paths, out_dir, sidebar: Sidebar) -> list[str]`
  - `publish.push(out_dir, remote, message, committer_name, committer_email) -> bool`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_publish.py`:

```python
from knowledge import publish
from knowledge.config import Sidebar


def test_sidebar_uses_the_configured_title_and_order(seeded_conn):
    bar = Sidebar(title="Example", order=("concepts",), labels={"concepts": "Concepts"})
    text = publish.render_sidebar(seeded_conn, bar)
    assert text.startswith("### Example")
    assert "- [Concepts](Concepts)" in text


def test_unlisted_specs_are_appended_alphabetically(seeded_conn):
    text = publish.render_sidebar(seeded_conn, Sidebar(title="Example", order=("concepts",)))
    assert text.index("Concepts") < text.index("Assets")


def test_nesting_and_headers_come_from_the_config(seeded_conn):
    bar = Sidebar(
        title="Example",
        order=("concepts", "assets"),
        nested_under={"assets": "concepts"},
        header_before={"concepts": "Modules"},
    )
    text = publish.render_sidebar(seeded_conn, bar)
    assert "**Modules**" in text
    assert "  - [Assets](Assets)" in text


def test_an_empty_sidebar_config_renders_every_spec_flat_and_alphabetical(seeded_conn):
    text = publish.render_sidebar(seeded_conn, Sidebar(title="Example"))
    assert "  - [" not in text
    assert "**" not in text.split("**Reference**")[0].replace("### Example", "")
```

`seeded_conn` is a fixture that scans the `repo` fixture into a database. Add it to `tests/conftest.py`:

```python
@pytest.fixture
def seeded_conn(repo):
    from knowledge import db, scan
    conn = db.connect(repo)
    scan.scan(conn, repo)
    return conn
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_publish.py -v`
Expected: FAIL — `render_sidebar()` takes 1 positional argument but 2 were given.

- [ ] **Step 3: Rewrite `publish.py`'s constants as parameters**

Delete `SIDEBAR_ORDER`, `SIDEBAR_REFERENCE`, `SIDEBAR_LABELS`, `SIDEBAR_HEADER_BEFORE`, `NESTED_UNDER`, `BOT_NAME` and `BOT_EMAIL`. Keep `FRONTMATTER`, `strip_frontmatter`, `_spec_directory`, `render_page` and `_published` unchanged. Then:

```python
def render_sidebar(conn, sidebar: Sidebar) -> str:
    rows = {spec_id: (title, page) for spec_id, title, page in _published(conn)}
    reference = set(sidebar.reference)
    ordered = [s for s in sidebar.order if s in rows and s not in reference]
    ordered += sorted(s for s in rows if s not in sidebar.order and s not in reference)

    lines = [f"### {sidebar.title}", ""] if sidebar.title else []
    for spec_id in ordered:
        header = sidebar.header_before.get(spec_id)
        if header:
            lines += ["", f"**{header}**", ""]
        title, page = rows[spec_id]
        label = sidebar.labels.get(spec_id, title)
        indent = "  " if spec_id in sidebar.nested_under else ""
        lines.append(f"{indent}- [{label}]({page})")

    lines += ["", "**Reference**", "", "- [Ontology](Ontology)"]
    for spec_id in sidebar.reference:
        if spec_id not in rows:
            continue
        title, page = rows[spec_id]
        lines.append(f"- [{sidebar.labels.get(spec_id, title)}]({page})")
    lines.append("")
    return "\n".join(lines)
```

`write_pages` gains a `sidebar: Sidebar` parameter and passes it to `render_sidebar`. `push` gains `committer_name: str` and `committer_email: str` parameters in place of the deleted constants.

- [ ] **Step 4: Dispatch on the target in `cmd_publish`**

At the top of `cmd_publish`:

```python
    target = config.publish.target
    if target == "none":
        print(
            "publishing is not configured — set publish.target in knowledge.toml"
            " to 'directory' or 'github-wiki'",
            file=sys.stderr,
        )
        return 1
    if target == "directory":
        out_dir = Path(args.out_dir or config.publish.out_dir)
        if not str(out_dir):
            print("publish.out_dir is required when publish.target is 'directory'",
                  file=sys.stderr)
            return 1
        written = publish.write_pages(conn, paths, out_dir, config.publish.sidebar)
        print(f"{len(written)} page(s) written to {out_dir}")
        return 0
```

The existing `github-wiki` path continues below, reading `config.publish.remote`, and passing `config.publish.committer_name` / `.committer_email` into `publish.push`.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_publish.py tests/test_cli_publish.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: configure the sidebar and the publishing target"
```

---

### Task 8: Finish the CLI's generic surface

Everything left in `cli.py` that names monicords, plus readable failures for the commands whose configuration is empty.

**Files:**

- Modify: `src/knowledge/cli.py`
- Modify: `src/knowledge/__init__.py`
- Modify: `src/knowledge/graph.py` (`broken_links` docstring)
- Test: `tests/test_cli_read.py`

**Interfaces:**

- Consumes: everything from Tasks 2–7.
- Produces: no new API; `cmd_stale` and `cmd_dep` exit 1 with a message when `config.code_repo is None`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli_read.py`:

```python
def test_stale_without_a_configured_code_repo_fails_clearly(repo, capsys, monkeypatch):
    from knowledge import cli
    (repo.root / "knowledge.toml").write_text(
        (repo.root / "knowledge.toml").read_text(encoding="utf-8").replace(
            'code_repo = "../code"', 'code_repo = ""'
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(repo.root)
    assert cli.main_argv(["stale"]) == 1
    assert "no code repository configured" in capsys.readouterr().err


def test_the_parser_description_names_no_project(capsys):
    from knowledge import cli
    text = cli.build_parser().format_help()
    assert "monicords" not in text.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_cli_read.py -v`
Expected: FAIL — `cli.main_argv` does not exist, and the description still says "monicords".

- [ ] **Step 3: Make the CLI testable and generic**

Split `main` so tests can drive it without `sys.argv`:

```python
def main_argv(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.handler is None:
        parser.print_help()
        return 1
    try:
        return args.handler(args)
    except (RuntimeError, ConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    return main_argv()
```

Change the parser description to `"Author, track and publish a knowledge base."`. Change `src/knowledge/__init__.py`'s docstring to `"""Authoring, tracking and publishing for a knowledge base."""`.

In `cmd_stale` and `cmd_dep`, fail before doing work:

```python
    if config.code_repo is None and not getattr(args, "code_repo", None):
        print(
            "no code repository configured — set repo.code_repo in knowledge.toml,"
            " or pass --code-repo",
            file=sys.stderr,
        )
        return 1
```

- [ ] **Step 4: Sweep for anything left**

Run: `rg -i 'monicords|mon:|https://monicords' src/ tests/`
Expected: no hits. Fix any that appear.

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: remove the last project-specific strings from the CLI"
```

---

### Task 9: `knowledge init`

**Files:**

- Create: `src/knowledge/init.py`
- Modify: `src/knowledge/cli.py` (`cmd_init`, parser)
- Test: `tests/test_init.py`

**Interfaces:**

- Consumes: `config.load_config` from Task 2.
- Produces:
  - `init.Answers(project_name, base_iri, prefix, instance_prefix, code_repo, publish_target, dependency_preset)`
  - `init.slugify(name: str) -> str`
  - `init.substitute(root: Path, values: dict[str, str]) -> list[str]` (returns the paths it rewrote)
  - `init.remaining_placeholders(root: Path) -> list[str]`
  - `init.run(root: Path, answers: Answers) -> list[str]`
  - `init.MANIFEST: tuple[str, ...]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_init.py`:

```python
import pytest

from knowledge import init
from knowledge.config import load_config


def build_template(tmp_path):
    """A miniature of the shipped template: placeholders in every manifest file."""
    (tmp_path / "knowledge.toml").write_text(
        "[template]\nunconfigured = true\n\n"
        '[project]\nname = "{{PROJECT_NAME}}"\n\n'
        "[vocabulary]\n"
        'ontology_file = "ontology.ttl"\n'
        'namespace = "{{BASE_IRI}}ontology#"\n'
        'instances = "{{BASE_IRI}}id/"\n'
        'prefix = "{{PREFIX}}"\n'
        'instance_prefix = "app"\n\n'
        '[repo]\ncode_repo = "{{CODE_REPO}}"\n',
        encoding="utf-8",
    )
    ontology = tmp_path / "ontology"
    ontology.mkdir()
    (ontology / "ontology.ttl").write_text(
        "@prefix {{PREFIX}}: <{{BASE_IRI}}ontology#> .\n"
        "@prefix app: <{{BASE_IRI}}id/> .\n",
        encoding="utf-8",
    )
    (ontology / "README.md").write_text("# {{PROJECT_NAME}} ontology\n", encoding="utf-8")
    (ontology / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.template.md").write_text("# {{PROJECT_NAME}}\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# knowledge-template\n", encoding="utf-8")
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "writer.md").write_text("Audit against {{ONTOLOGY_FILE}}.\n", encoding="utf-8")
    (agents / "interviewer.md").write_text("Interview about {{PROJECT_NAME}}.\n", encoding="utf-8")
    skill = tmp_path / "integrations" / "code-repo" / ".claude" / "skills" / "knowledge-base"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("Read {{PROJECT_NAME}}'s knowledge base.\n", encoding="utf-8")
    example = tmp_path / "specs" / "example"
    example.mkdir(parents=True)
    (example / "spec.md").write_text("---\nid: example\n---\n\n# Example\n", encoding="utf-8")
    (example / "spec.ttl").write_text("# example\n", encoding="utf-8")
    (tmp_path / ".metadata").mkdir()
    (tmp_path / ".metadata" / "dump.sql").write_text("-- seeded\n", encoding="utf-8")
    return tmp_path


ANSWERS = init.Answers(
    project_name="Acme",
    base_iri="https://acme.test/",
    prefix="acme",
    instance_prefix="app",
    code_repo="../acme_app",
    publish_target="none",
    dependency_preset="none",
)


def test_slugify_lowercases_and_strips_punctuation():
    assert init.slugify("Acme Widgets, Inc.") == "acmewidgets"
    assert init.slugify("monicords") == "monicords"


def test_run_substitutes_every_placeholder(tmp_path):
    root = build_template(tmp_path)
    init.run(root, ANSWERS)
    assert init.remaining_placeholders(root) == []


def test_run_produces_a_loadable_config(tmp_path):
    root = build_template(tmp_path)
    init.run(root, ANSWERS)
    config = load_config(root)
    assert config.project_name == "Acme"
    assert config.vocabulary.namespace == "https://acme.test/ontology#"
    assert config.vocabulary.prefix == "acme"
    assert config.unconfigured is False
    assert config.code_repo is not None


def test_run_rewrites_the_ontology_prefix_lines(tmp_path):
    root = build_template(tmp_path)
    init.run(root, ANSWERS)
    text = (root / "ontology" / "ontology.ttl").read_text(encoding="utf-8")
    assert "@prefix acme: <https://acme.test/ontology#> ." in text


def test_run_removes_the_example_spec_and_empties_the_dump(tmp_path):
    root = build_template(tmp_path)
    init.run(root, ANSWERS)
    assert not (root / "specs" / "example").exists()
    assert "seeded" not in (root / ".metadata" / "dump.sql").read_text(encoding="utf-8")


def test_run_replaces_the_readme_with_the_template_one(tmp_path):
    root = build_template(tmp_path)
    init.run(root, ANSWERS)
    assert (root / "README.md").read_text(encoding="utf-8") == "# Acme\n"


def test_run_refuses_a_configured_repository(tmp_path):
    root = build_template(tmp_path)
    init.run(root, ANSWERS)
    with pytest.raises(RuntimeError) as exc:
        init.run(root, ANSWERS)
    assert "already configured" in str(exc.value)


def test_remaining_placeholders_reports_what_is_left(tmp_path):
    root = build_template(tmp_path)
    (root / "stray.md").write_text("# {{PROJECT_NAME}}\n", encoding="utf-8")
    init.run(root, ANSWERS)
    assert any("stray.md" in entry for entry in init.remaining_placeholders(root))


def test_an_empty_code_repo_answer_disables_staleness(tmp_path):
    root = build_template(tmp_path)
    from dataclasses import replace
    init.run(root, replace(ANSWERS, code_repo=""))
    assert load_config(root).code_repo is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_init.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'knowledge.init'`.

- [ ] **Step 3: Write `src/knowledge/init.py`**

```python
"""`knowledge init` — bind the template to one project, once.

The template ships with {{PLACEHOLDER}} tokens rather than a working configuration, so a
half-configured repository is impossible to mistake for a configured one: every placeholder
that survives is visible, and `--check` fails on it.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from knowledge.config import load_config

PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")

# Files that carry placeholders. Everything else in the template is already generic.
MANIFEST = (
    "knowledge.toml",
    "ontology/README.md",
    "docs/README.template.md",
    ".claude/agents/interviewer.md",
    ".claude/agents/writer.md",
    "integrations/code-repo/.claude/skills/knowledge-base/SKILL.md",
)

# Directories a placeholder sweep must not walk into.
SKIPPED_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules", ".worktrees"}
TEXT_SUFFIXES = {".md", ".toml", ".ttl", ".yaml", ".yml", ".py", ".json", ".txt", ""}


@dataclass(frozen=True)
class Answers:
    project_name: str
    base_iri: str
    prefix: str
    instance_prefix: str
    code_repo: str
    publish_target: str
    dependency_preset: str


def slugify(name: str) -> str:
    """A prefix has to be a legal Turtle prefix, so anything that is not a letter or a
    digit goes, and what is left is lowercased."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _values(answers: Answers, ontology_file: str) -> dict[str, str]:
    base = answers.base_iri if answers.base_iri.endswith("/") else answers.base_iri + "/"
    return {
        "PROJECT_NAME": answers.project_name,
        "BASE_IRI": base,
        "PREFIX": answers.prefix,
        "INSTANCE_PREFIX": answers.instance_prefix,
        "CODE_REPO": answers.code_repo,
        "ONTOLOGY_FILE": ontology_file,
        "PUBLISH_TARGET": answers.publish_target,
    }


def substitute(root: Path, values: dict[str, str], manifest=MANIFEST) -> list[str]:
    """Rewrite every {{TOKEN}} in the manifest. A token with no value is left alone, so it
    shows up in `remaining_placeholders` rather than becoming an empty string silently."""
    rewritten: list[str] = []
    for relative in manifest:
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        new = PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), text)
        if new != text:
            path.write_text(new, encoding="utf-8", newline="\n")
            rewritten.append(relative)
    return rewritten


def remaining_placeholders(root: Path) -> list[str]:
    """"<path>: {{TOKEN}}" for every placeholder still in the tree."""
    found: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        if SKIPPED_DIRS & set(path.relative_to(root).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in PLACEHOLDER.finditer(text):
            found.append(f"{path.relative_to(root).as_posix()}: {match.group(0)}")
    return found


def _reset_metadata(root: Path) -> None:
    """An empty database dumped fresh, so the generated repository starts with no history
    of specs that are no longer there."""
    from knowledge import db
    from knowledge.paths import get_paths

    paths = get_paths(root, load_config(root).vocabulary.ontology_file)
    paths.db.unlink(missing_ok=True)
    conn = db.connect(paths)
    db.save(conn, paths)
    conn.close()
    paths.db.unlink(missing_ok=True)


def run(root: Path, answers: Answers) -> list[str]:
    """Bind the template to one project. Returns the files it rewrote."""
    config = load_config(root)
    if not config.unconfigured:
        raise RuntimeError(
            f"{root} is already configured — remove the [template] table from"
            " knowledge.toml to re-run init"
        )

    ontology_file = config.vocabulary.ontology_file
    values = _values(answers, ontology_file)

    rewritten = substitute(root, values, MANIFEST + (f"ontology/{ontology_file}",))

    text = (root / "knowledge.toml").read_text(encoding="utf-8")
    text = re.sub(r"\[template\]\nunconfigured = true\n\n?", "", text, count=1)
    if answers.publish_target != "none":
        text = text.replace('target  = "none"', f'target  = "{answers.publish_target}"')
    if answers.dependency_preset != "none":
        preset = (root / "presets" / f"{answers.dependency_preset}.toml").read_text(
            encoding="utf-8"
        )
        block = preset.split("[dependencies]", 1)[1]
        text = re.sub(r"\[dependencies\].*?(?=\n\[)", "[dependencies]" + block, text, flags=re.S)
    (root / "knowledge.toml").write_text(text, encoding="utf-8", newline="\n")

    shutil.rmtree(root / "specs" / "example", ignore_errors=True)
    _reset_metadata(root)

    template_readme = root / "docs" / "README.template.md"
    if template_readme.is_file():
        shutil.move(str(template_readme), str(root / "README.md"))
        rewritten.append("README.md")

    return sorted(set(rewritten))
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_init.py -v`
Expected: PASS.

- [ ] **Step 5: Add the `init` subcommand**

In `cli.py`:

```python
def _prompt(question: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{question}{suffix}: ").strip()
    return answer or default


def cmd_init(args: argparse.Namespace) -> int:
    from knowledge import init
    root = find_root()

    if args.check:
        remaining = init.remaining_placeholders(root)
        if remaining:
            print(f"{len(remaining)} placeholder(s) not substituted:")
            for entry in remaining:
                print("  -", entry)
            return 1
        print("no placeholders remain")
        return 0

    name = args.name or _prompt("Project name")
    if not name:
        print("a project name is required", file=sys.stderr)
        return 1
    base_iri = args.base_iri or _prompt("Base IRI", f"https://{init.slugify(name)}.example/")
    prefix = args.prefix or _prompt("Turtle prefix", init.slugify(name))
    answers = init.Answers(
        project_name=name,
        base_iri=base_iri,
        prefix=prefix,
        instance_prefix=args.instance_prefix or _prompt("Instance prefix", "app"),
        code_repo=args.code_repo if args.code_repo is not None
        else _prompt("Code repository path (blank to disable staleness)"),
        publish_target=args.publish_target or _prompt(
            "Publish target (none/directory/github-wiki)", "none"
        ),
        dependency_preset=args.dependency_preset or _prompt(
            "Dependency preset (none/nextjs)", "none"
        ),
    )

    rewritten = init.run(root, answers)
    print(f"configured {name}: rewrote {len(rewritten)} file(s)")
    for relative in rewritten:
        print("  -", relative)

    skill = root / "integrations" / "code-repo" / ".claude" / "skills" / "knowledge-base"
    if args.install_skill and answers.code_repo:
        destination = (root / answers.code_repo).resolve() / ".claude" / "skills" / "knowledge-base"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skill, destination, dirs_exist_ok=True)
        print(f"installed the reading skill into {destination}")
    elif skill.is_dir():
        print(f"\nthe reading skill is at {skill}")
        print("copy it into your code repository's .claude/skills/, or re-run with --install-skill")

    remaining = init.remaining_placeholders(root)
    if remaining:
        print(f"\nwarning: {len(remaining)} placeholder(s) remain; run `knowledge init --check`")
    return 0
```

Register it, and note that it must not call `open_repo` — the repository is not yet configured:

```python
    init_p = sub.add_parser("init", help="bind this template to one project")
    init_p.add_argument("--check", action="store_true",
                        help="report unsubstituted placeholders and exit non-zero")
    init_p.add_argument("--name")
    init_p.add_argument("--base-iri")
    init_p.add_argument("--prefix")
    init_p.add_argument("--instance-prefix")
    init_p.add_argument("--code-repo")
    init_p.add_argument("--publish-target", choices=["none", "directory", "github-wiki"])
    init_p.add_argument("--dependency-preset", choices=["none", "nextjs"])
    init_p.add_argument("--install-skill", action="store_true",
                        help="copy the reading skill into the code repository")
    init_p.set_defaults(handler=cmd_init)
```

Add `import shutil` to `cli.py`.

- [ ] **Step 6: Run the whole suite**

Run: `uv run pytest -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: add knowledge init"
```

---

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

### Task 11: The agents and the reading skill

**Files:**

- Create: `.claude/agents/interviewer.md`, `.claude/agents/writer.md`
- Create: `integrations/code-repo/.claude/skills/knowledge-base/SKILL.md`
- Test: `tests/test_template_content.py` (extend)

**Interfaces:**

- Consumes: `init.MANIFEST` from Task 9 — these three files are in it.
- Produces: no code API.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_template_content.py`:

```python
AGENT_FILES = (
    ".claude/agents/interviewer.md",
    ".claude/agents/writer.md",
    "integrations/code-repo/.claude/skills/knowledge-base/SKILL.md",
)


def test_the_agents_name_no_project():
    for relative in AGENT_FILES:
        text = (ROOT / relative).read_text(encoding="utf-8").lower()
        assert "monicords" not in text, relative
        assert "app:workspace" not in text, relative


def test_the_agents_are_all_in_the_init_manifest():
    from knowledge.init import MANIFEST
    for relative in AGENT_FILES:
        assert relative in MANIFEST, relative
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_template_content.py -v`
Expected: FAIL with `FileNotFoundError` for `.claude/agents/interviewer.md`.

- [ ] **Step 3: Write `.claude/agents/interviewer.md`**

Copy `../monicords-knowledge/.claude/agents/interviewer.md` and make exactly these changes, keeping every other sentence:

- `ontology/monicords.ttl` becomes `ontology/{{ONTOLOGY_FILE}}`.
- `ontology/README.md`'s naming table becomes `ontology/AUTHORING.md`'s naming section.
- The step-3 SPARQL example loses its `mon:` prefix in favour of `{{PREFIX}}:`, and `knowledge describe app:Assets` becomes `knowledge describe {{INSTANCE_PREFIX}}:<SomeNode>`.
- The `--claim <app:IRI>` flag description becomes `--claim <{{INSTANCE_PREFIX}}:IRI>`.
- The frontmatter `description` says "a knowledge base" rather than naming a product.
- Add one sentence after Setup step 1: "If your vocabulary has no class for what you are documenting, stop and add it to `ontology/{{ONTOLOGY_FILE}}` first — inventing a term inline is what `validate --strict` exists to catch."

- [ ] **Step 4: Write `.claude/agents/writer.md`**

Copy `../monicords-knowledge/.claude/agents/writer.md` and make exactly these changes:

- `ontology/monicords.ttl` becomes `ontology/{{ONTOLOGY_FILE}}`.
- The concepts bullet becomes vocabulary-neutral: "Concepts are referenced, not redeclared. If your configuration names a concept class and a concept spec, a concept belongs on that spec and nowhere else."
- The `mon:Rule` bullet becomes `{{PREFIX}}:Rule`, keeping the "amount is required" worked example intact — it demonstrates the rule about reasons, not a monicords fact.
- The `mon:viewport` bullet is replaced with: "A property your ontology documents as narrow in scope goes only where its `rdfs:domain` allows. `validate --strict` checks this for every predicate that declares a domain or range."
- The naming bullet points at `ontology/AUTHORING.md` and says the enforced pattern is whatever `[vocabulary] field_name_pattern` holds.
- The frontmatter `description` says "a knowledge base" rather than naming a product.

- [ ] **Step 5: Write the reading skill**

Create `integrations/code-repo/.claude/skills/knowledge-base/SKILL.md` from `../monicords_app/.claude/skills/knowledge-graph/SKILL.md`, keeping: the command table, the spec-id-versus-node-name distinction, the draft-exclusion trap and `describe`'s exemption, the prefix trap, the `dep list` trap, and the transitivity and inverse-pair traps as conditional ("if your vocabulary declares an inverse pair…"). Replace the monicords-specific trap rows and the drafts list with a `## Your knowledge base` section holding `{{PROJECT_NAME}}`, the path to the knowledge repository, and a "fill this in" list for current drafts and project-specific traps.

Its frontmatter:

```markdown
---
name: knowledge-base
description: Use when answering questions about what {{PROJECT_NAME}} does, why a rule exists, or what a module is for — and whenever running the `knowledge` CLI. Covers which subcommand answers which question, the draft-exclusion trap, and SPARQL against the project vocabulary.
---
```

- [ ] **Step 6: Run the tests**

Run: `uv run pytest tests/test_template_content.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: add the interviewer, the writer and the reading skill"
```

---

### Task 12: README, guide, recipes, licence

**Files:**

- Create: `README.md`, `LICENSE`
- Create: `docs/GUIDE.md`, `docs/README.template.md`
- Create: `docs/recipes/github-actions.md`, `docs/recipes/github-wiki-publishing.md`, `docs/recipes/nextjs-dependencies.md`

**Interfaces:**

- Consumes: nothing.
- Produces: no code API.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_template_content.py`:

```python
DOCS = (
    "README.md",
    "LICENSE",
    "docs/GUIDE.md",
    "docs/README.template.md",
    "docs/recipes/github-actions.md",
    "docs/recipes/github-wiki-publishing.md",
    "docs/recipes/nextjs-dependencies.md",
)


def test_every_document_exists_and_names_no_project():
    for relative in DOCS:
        path = ROOT / relative
        assert path.is_file(), relative
        if relative == "LICENSE":
            continue
        assert "monicords" not in path.read_text(encoding="utf-8").lower(), relative


def test_the_guide_documents_installing_the_hooks():
    text = (ROOT / "docs" / "GUIDE.md").read_text(encoding="utf-8")
    assert "pre-commit install --hook-type pre-commit --hook-type pre-push" in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/test_template_content.py -v`
Expected: FAIL with `assert False` on `README.md`.

- [ ] **Step 3: Write `README.md`** — the template's own front page

Sections: what this is in three sentences; the two-file model (`spec.md` prose, `spec.ttl` graph, one assembled RDF graph); Getting started (Use this template → clone → `uv sync --all-extras --dev` → `uv run knowledge init` → `uv run pre-commit install --hook-type pre-commit --hook-type pre-push`); What you get (the CLI, the two agents, the reading skill, the lifecycle); What you configure, as a table of the `knowledge.toml` sections; pointers to `docs/GUIDE.md`, `ontology/AUTHORING.md` and `docs/recipes/`.

- [ ] **Step 4: Write `docs/GUIDE.md`**

Sections:

1. **The model** — a spec is prose plus a graph; `draft` and `verified` are the only statuses; `model` is the writer's audit and `verify` is a person's confirmation; staleness is a demotion, not a third status; verification refuses an unaudited graph and refuses while a question is open.
2. **The drafts default** — `query`, `ask`, `graph` and `contradictions` read verified specs only and say nothing about what they left out; `describe` always reads everything; when to pass `--include-drafts` and to say that you did.
3. **Adapting the template** — in order: design the vocabulary (`ontology/AUTHORING.md`), wire the checks into `[vocabulary]`, decide on `[dependencies]`, decide on `[publish]`, then write the first spec.
4. **The hooks** — the one-time `uv run pre-commit install --hook-type pre-commit --hook-type pre-push`, what each of the four hooks does, that `prettier` uses `proseWrap: preserve` because specs are hand-wrapped, that `.gitattributes` normalises to LF because `.metadata/dump.sql` is byte-compared, and that `pytest` is the one to drop for a user who never edits `src/`.
5. **What is deliberately not here** — no workflows; see `docs/recipes/`.
6. **Command reference** — the reading commands and the authoring commands, as the two tables from this repository's README, with monicords examples replaced.

- [ ] **Step 5: Write `docs/README.template.md`**

The README a generated repository gets. Same shape as `README.md` but written for the user's own project: `# {{PROJECT_NAME}} knowledge`, the layout block, the reading commands, the authoring commands, the hook install line, and a pointer to `docs/GUIDE.md`.

- [ ] **Step 6: Write the three recipes**

`docs/recipes/github-actions.md` — prose on why staleness belongs in the knowledge repository rather than the code repository ("a code change failing on documentation is a check people learn to bypass; staleness is work, surfaced where the work lives"), and why cross-repository access needs a PAT rather than the default `GITHUB_TOKEN`. Then three fenced YAML blocks adapted from `../monicords-knowledge/.github/workflows/{ci,publish,stale}.yml`, with `jgimitola/monicords` replaced by `<owner>/<repo>`, `develop` by `<branch>`, and every comment kept.

`docs/recipes/github-wiki-publishing.md` — `[publish]` and `[publish.sidebar]` explained key by key; the page-naming rule (`loans-out` → `Loans-Out`); that only `_Sidebar.md` is generated while every other page is a spec; that GitHub creates the wiki remote only once the wiki has at least one page, so a brand-new wiki needs one page created by hand first.

`docs/recipes/nextjs-dependencies.md` — what `[dependencies]` derives and why a route needs a glob rather than a path (route groups are in the file path but not the URL); the `{segments}` and `{path}` substitution tokens; the `presets/nextjs.toml` block; and the note that both sides of a rename count, which is why `deps.changed_files` passes `-M`.

- [ ] **Step 7: Write `LICENSE`**

The MIT licence, `Copyright (c) 2026 Jesús Imitola`.

- [ ] **Step 8: Run the tests and format**

```bash
uv run pytest -v
uv run pre-commit run --all-files
```

Expected: PASS; prettier may reformat the new markdown, which is fine — re-stage and continue.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "docs: add the README, the guide, the recipes and the licence"
```

---

### Task 13: End-to-end verification and publication

**Files:**

- No files in the template change unless verification finds a defect.

**Interfaces:**

- Consumes: everything.
- Produces: `github.com/jgimitola/knowledge-template`, public, marked as a template repository.

- [ ] **Step 1: Run the full local check**

```bash
uv run pytest -v
uv run pre-commit run --all-files
uv run pre-commit run --all-files --hook-stage pre-push
uv run knowledge scan
uv run knowledge validate --strict
uv run knowledge init --check
```

Expected: everything passes except `init --check`, which must exit 1 and list the placeholders — that is the template's correct state.

- [ ] **Step 2: Prove `init` produces a working repository**

```bash
rm -rf /tmp/kt-check && cp -r . /tmp/kt-check && rm -rf /tmp/kt-check/.git
cd /tmp/kt-check
uv run knowledge init --name Acme --base-iri https://acme.example/ --prefix acme \
  --instance-prefix app --code-repo "" --publish-target directory --dependency-preset none
uv run knowledge init --check
uv run knowledge scan
uv run knowledge validate --strict
uv run knowledge new first --title "First"
```

Expected: `init --check` exits 0; `validate --strict` exits 0 on an empty corpus; `new` scaffolds `specs/first/`. Then author a two-triple `spec.ttl` and `spec.md` by hand, and run:

```bash
uv run knowledge scan
uv run knowledge validate --strict
uv run knowledge model first --by check
uv run knowledge verify first --by check
uv run knowledge publish --dry-run --out-dir ./_pages
```

Expected: the spec reaches `verified`, and `_pages/` contains `First.md`, `Ontology.md` and `_Sidebar.md`.

- [ ] **Step 3: Fix anything the round trip exposed**

Any failure here is a defect in Tasks 2–12. Fix it in `../knowledge-template`, re-run Step 2, and commit the fix before continuing.

- [ ] **Step 4: Create the GitHub repository**

```bash
cd ../knowledge-template
gh repo create jgimitola/knowledge-template --public \
  --description "A template for a knowledge base: prose plus an RDF graph, tracked and published." \
  --source . --remote origin --push
```

- [ ] **Step 5: Mark it as a template repository**

```bash
gh api -X PATCH repos/jgimitola/knowledge-template -f is_template=true
gh api repos/jgimitola/knowledge-template --jq .is_template
```

Expected: `true`.

- [ ] **Step 6: Add repository topics so it is findable**

```bash
gh api -X PUT repos/jgimitola/knowledge-template/topics \
  -f 'names[]=knowledge-base' -f 'names[]=rdf' -f 'names[]=sparql' \
  -f 'names[]=documentation' -f 'names[]=template'
```

- [ ] **Step 7: Verify the published state**

```bash
gh repo view jgimitola/knowledge-template
```

Confirm: public, `is_template: true`, README renders, and no `.github/workflows/` directory exists.

- [ ] **Step 8: Commit any final fixes and push**

```bash
git status --short
git push
```

---

## Self-Review

**Spec coverage.** Every section of the spec maps to a task: near-empty ontology → Task 10; configuration-driven checks → Tasks 4, 5; disabled-check reporting → Task 4 Step 4; repository layout → Tasks 1, 10, 11, 12; the `knowledge.toml` schema → Task 2; the module-change table → Tasks 3–8; `knowledge init` and both guards → Task 9; the ontology seed, `AUTHORING.md` and the webapp example → Task 10; agents and the reading skill → Task 11; the three recipes and the shipped hooks → Task 12 (the hooks themselves are copied in Task 1 and documented in Task 12 Step 4); publication → Task 13. `scripts/` removal is covered by Task 1 not copying it.

**Type consistency.** `Vocabulary`, `Checks`, `Config`, `Survey`, `Dependencies`, `Sidebar` and `Publish` are defined in Task 2 and used with those exact field names throughout. `graph.page_name` is renamed once, in Task 3, and its importers (`scan.py`, `publish.py`) are updated there. `lint.ungrounded_empty_states` is renamed to `ungrounded_literals` in Task 4 and referenced by that name in Task 4 only. `cli.open_repo`'s three-value return is introduced in Task 2 and assumed by Tasks 3–9. `deps.check` keeps its name and gains a `None`-guard.

**Placeholder scan.** No `TBD`, no "handle edge cases", no "similar to Task N". Task 12's document steps name their sections and required content rather than shipping full prose, which is deliberate: they are documents, and the content each must cover is enumerated. Task 10 Step 6 and Task 11 Steps 3–5 do the same, each listing the exact changes to make against a named source file.
