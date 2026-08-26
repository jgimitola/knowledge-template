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

# Every term below is copied from ontology/monicords.ttl with the same rdf:type and the same
# rdfs:domain / rdfs:range, so a test written against this ontology tests the real vocabulary.
# The subClassOf edges and the domain/range declarations are what domain_range_violations reads.
ONTOLOGY = """\
@prefix mon:     <https://monicords.com/ontology#> .
@prefix app:     <https://monicords.com/id/> .
@prefix rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs:    <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:     <http://www.w3.org/2001/XMLSchema#> .
@prefix skos:    <http://www.w3.org/2004/02/skos/core#> .
@prefix dcterms: <http://purl.org/dc/terms/> .

mon:InterfaceElement a rdfs:Class ; rdfs:label "Interface element"@en .
mon:Module a rdfs:Class ; rdfs:subClassOf mon:InterfaceElement ; rdfs:label "Module"@en .
mon:View a rdfs:Class ; rdfs:subClassOf mon:InterfaceElement ; rdfs:label "View"@en .
mon:Section a rdfs:Class ; rdfs:subClassOf mon:InterfaceElement ; rdfs:label "Section"@en .
mon:Field a rdfs:Class ; rdfs:label "Field"@en .
mon:Action a rdfs:Class ; rdfs:label "Action"@en .
mon:Concept a rdfs:Class ; rdfs:label "Domain concept"@en .
mon:Rule a rdfs:Class ; rdfs:label "Rule"@en .

mon:contains a rdf:Property ; rdfs:label "contains"@en ;
    rdfs:domain mon:InterfaceElement ; rdfs:range mon:InterfaceElement .
mon:partOf a rdf:Property ; rdfs:label "part of"@en ;
    rdfs:domain mon:InterfaceElement ; rdfs:range mon:InterfaceElement .
mon:displays a rdf:Property ; rdfs:label "displays"@en ;
    rdfs:domain mon:InterfaceElement ; rdfs:range mon:Field .
mon:scopedTo a rdf:Property ; rdfs:label "scoped to"@en ;
    rdfs:domain mon:InterfaceElement ; rdfs:range mon:Concept .
mon:appliesTo a rdf:Property ; rdfs:label "applies to"@en ; rdfs:domain mon:Rule .
mon:relatesTo a rdf:Property ; rdfs:label "relates to"@en ;
    rdfs:domain mon:Concept ; rdfs:range mon:Concept .
mon:route a rdf:Property ; rdfs:label "route"@en ;
    rdfs:domain mon:View ; rdfs:range xsd:string .
mon:endpoint a rdf:Property ; rdfs:label "endpoint"@en ;
    rdfs:domain mon:Action ; rdfs:range xsd:string .
mon:emptyState a rdf:Property ; rdfs:label "empty state"@en ;
    rdfs:domain mon:InterfaceElement ; rdfs:range xsd:string .
mon:format a rdf:Property ; rdfs:label "format"@en ;
    rdfs:domain mon:Field ; rdfs:range xsd:string .
"""

ASSETS_TTL = """\
app:Assets a mon:View ;
    rdfs:label   "Assets"@en ;
    mon:route    "/platform/assets" ;
    mon:scopedTo app:Workspace .
"""

CONCEPTS_TTL = """\
app:Workspace a mon:Concept ;
    rdfs:label "Workspace"@en .
"""


def write_spec(root, spec_id, ttl, prose="Some prose.\n"):
    directory = root / "specs" / spec_id
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "spec.md").write_text(
        f"---\nid: {spec_id}\n---\n\n# {spec_id.replace('-', ' ').title()}\n\n{prose}",
        encoding="utf-8",
    )
    (directory / "spec.ttl").write_text(ttl, encoding="utf-8")
    return directory


# knowledge.toml now requires a full [vocabulary] table (Task 2). These stay the monicords
# namespaces on purpose — graph.py still has MON as a module constant at this point, so a
# fixture using different namespaces would break every test that parses ONTOLOGY/ASSETS_TTL
# above. Task 3 rewrites the fixture and the constant together.
KNOWLEDGE_TOML = """\
[project]
name = "Monicords"

[vocabulary]
ontology_file = "monicords.ttl"
namespace = "https://monicords.com/ontology#"
instances = "https://monicords.com/id/"
prefix = "mon"
instance_prefix = "app"

[repo]
code_repo = "{code_repo}"

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
    through load_config. Same monicords vocabulary as KNOWLEDGE_TOML above."""
    return Config(
        project_name="Monicords",
        vocabulary=Vocabulary(
            ontology_file="monicords.ttl",
            namespace="https://monicords.com/ontology#",
            instances="https://monicords.com/id/",
            prefix="mon",
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
    write_knowledge_toml(tmp_path)
    ontology = tmp_path / "ontology"
    ontology.mkdir()
    (ontology / "monicords.ttl").write_text(ONTOLOGY, encoding="utf-8")
    (ontology / "README.md").write_text("# Ontology\n\nThe vocabulary.\n", encoding="utf-8")
    (ontology / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    (tmp_path / ".metadata").mkdir()

    write_spec(tmp_path, "assets", ASSETS_TTL, "The Assets screen. See [Concepts](Concepts).\n")
    write_spec(tmp_path, "concepts", CONCEPTS_TTL)
    return paths_mod.get_paths(tmp_path)
