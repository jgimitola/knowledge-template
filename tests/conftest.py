import os

import pytest

from knowledge import gitcmd
from knowledge import paths as paths_mod
from knowledge.config import Config, Dependencies, Publish
from knowledge.vocab import Checks, Vocabulary


@pytest.fixture(autouse=True)
def isolate_git_env(monkeypatch):
    """No test inherits the caller's repository.

    git exports GIT_DIR to every hook it runs — a linked worktree's gitdir, absolutely
    pathed — and hands GIT_INDEX_FILE and the GIT_AUTHOR_*/GIT_COMMITTER_* identity to
    commit hooks and rebases on top of that. Subprocesses inherit all of it, and GIT_DIR
    outranks `-C <path>`, so a fixture building a throwaway repository in tmp_path would
    quietly drive the repository being pushed instead: `git init <tmp>` reinitialises
    GIT_DIR and creates nothing at <tmp>, then `git -C <tmp> add -A` stages <tmp>'s files
    into the invoking repository's index.

    That is not hypothetical — it is what made these tests pass under `pytest` and error
    under the pre-push hook. Scrubbing here rather than in the hook keeps the tests correct
    however they are reached: a hook, a CI step, a rebase, `git bisect run`.
    """
    for key in list(os.environ):
        if key.startswith("GIT_") and key not in gitcmd.ENV_KEPT:
            monkeypatch.delenv(key, raising=False)

# A generic vocabulary, unrelated to any real project, so a test written against it tests
# the mechanism rather than any one domain. The subClassOf edges and the domain/range
# declarations are what domain_range_violations reads.
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


def _write_spec(root, spec_id, ttl, prose="Some prose.\n"):
    directory = root / "specs" / spec_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "spec.md").write_text(
        f"---\nid: {spec_id}\n---\n\n# {spec_id.replace('-', ' ').title()}\n\n{prose}",
        encoding="utf-8",
    )
    (directory / "spec.ttl").write_text(ttl, encoding="utf-8")
    return directory


@pytest.fixture
def write_spec():
    """Tasks 4-7 request this as a fixture rather than importing it."""
    return _write_spec


# A separate template from CONFIG_TOML above: knowledge.toml's [repo]/[publish] values
# overridden for one test, with the rest of the vocabulary/dependencies configuration a
# working repository still needs. Kept distinct from the fixture ontology's namespace/prefix
# so a caller only overrides what a given test actually cares about.
KNOWLEDGE_TOML = """\
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
code_repo = "{code_repo}"

[dependencies]
route_property = "route"
endpoint_property = "endpoint"
route_glob = "app/**/{{segments}}/page.tsx"
endpoint_glob = "app/{{path}}/**/route.ts"
absorbed_prefixes = ["platform"]

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
    through load_config. Same example vocabulary as KNOWLEDGE_TOML above."""
    return Config(
        project_name="Example",
        vocabulary=Vocabulary(
            ontology_file="ontology.ttl",
            namespace="https://example.test/ontology#",
            instances="https://example.test/id/",
            prefix="ex",
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
    (tmp_path / "knowledge.toml").write_text(CONFIG_TOML, encoding="utf-8")
    ontology = tmp_path / "ontology"
    ontology.mkdir()
    (ontology / "ontology.ttl").write_text(ONTOLOGY, encoding="utf-8")
    (ontology / "README.md").write_text("# Ontology\n\nThe vocabulary.\n", encoding="utf-8")
    (ontology / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    (tmp_path / ".metadata").mkdir()

    _write_spec(tmp_path, "assets", ASSETS_TTL, "The Assets screen. See [Concepts](Concepts).\n")
    _write_spec(tmp_path, "concepts", CONCEPTS_TTL)
    return paths_mod.get_paths(tmp_path)


@pytest.fixture
def config(repo):
    from knowledge.config import load_config
    return load_config(repo.root)


@pytest.fixture
def repo_with_vocab(repo, config):
    return repo, config.vocabulary
