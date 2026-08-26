"""Assemble the RDF graph from the ontology plus each spec's colocated Turtle.

This replaces scripts/wiki_graph.py in the code repository. The difference is where the
Turtle comes from: fenced blocks inside markdown before, a sibling .ttl file now. The
ontology is always loaded first because it declares the prefixes and vocabulary every
spec's Turtle is written against.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from rdflib import RDF, Graph, URIRef

from knowledge.paths import Paths, spec_md, spec_ttl
from knowledge.vocab import Vocabulary

MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def spec_ids(paths: Paths) -> list[str]:
    if not paths.specs.is_dir():
        return []
    return sorted(d.name for d in paths.specs.iterdir() if (d / "spec.md").is_file())


def page_name(spec_id: str) -> str:
    """assets -> Assets, loans-out -> Loans-Out. Inverse of str.lower() on a page stem."""
    return "-".join(word.capitalize() for word in spec_id.split("-"))


def turtle_source(paths: Paths, ids: Sequence[str]) -> str:
    chunks = [f"# --- ontology ---\n{paths.ontology_ttl.read_text(encoding='utf-8')}"]
    for spec_id in ids:
        path = spec_ttl(paths, spec_id)
        if path.is_file():
            chunks.append(f"# --- {spec_id} ---\n{path.read_text(encoding='utf-8')}")
    return "\n".join(chunks)


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


def broken_links(paths: Paths, ids: Sequence[str]) -> list[str]:
    """Links in prose point at wiki page names, which are derived from spec ids."""
    known = {page_name(spec_id) for spec_id in spec_ids(paths)} | {"Ontology"}
    broken: list[str] = []
    for spec_id in ids:
        path = spec_md(paths, spec_id)
        if not path.is_file():
            continue
        for text, target in MD_LINK.findall(path.read_text(encoding="utf-8")):
            if target.startswith(("http", "#")):
                continue
            if target.split("#", 1)[0] not in known:
                broken.append(f"{spec_id}: [{text}]({target})")
    return broken
