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

MON = "https://monicords.com/ontology#"
APP = "https://monicords.com/id/"

MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

SPARQL_PREFIXES = """
PREFIX mon:     <https://monicords.com/ontology#>
PREFIX app:     <https://monicords.com/id/>
PREFIX rdf:     <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:    <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd:     <http://www.w3.org/2001/XMLSchema#>
PREFIX skos:    <http://www.w3.org/2004/02/skos/core#>
PREFIX dcterms: <http://purl.org/dc/terms/>
"""

SANITY_QUERIES = {
    "modules": "SELECT ?label WHERE { ?m a mon:Module ; rdfs:label ?label } ORDER BY ?label",
    "views and their routes": """
        SELECT ?label ?route WHERE { ?v a mon:View ; rdfs:label ?label ; mon:route ?route }
        ORDER BY ?route
    """,
    "what the user sees only on narrow screens": """
        SELECT ?label WHERE { ?s mon:viewport "narrow" ; rdfs:label ?label } ORDER BY ?label
    """,
    "rules, and what each constrains": """
        SELECT ?rule ?target WHERE {
          ?r a mon:Rule ; rdfs:label ?rule ; mon:constrains ?t .
          OPTIONAL { ?t rdfs:label ?tl }
          BIND(COALESCE(?tl, REPLACE(STR(?t), "^.*[#/]", "")) AS ?target)
        } ORDER BY ?rule
    """,
    "fields the user cannot edit": """
        SELECT ?label WHERE { ?f mon:editable false ; rdfs:label ?label } ORDER BY ?label
    """,
    "concepts and how many things reference them": """
        SELECT ?label (COUNT(?s) AS ?references) WHERE {
          ?c a mon:Concept ; rdfs:label ?label . ?s ?p ?c .
        } GROUP BY ?label ORDER BY DESC(?references)
    """,
}


def spec_ids(paths: Paths) -> list[str]:
    if not paths.specs.is_dir():
        return []
    return sorted(d.name for d in paths.specs.iterdir() if (d / "spec.md").is_file())


def wiki_page_name(spec_id: str) -> str:
    """assets -> Assets, loans-out -> Loans-Out. Inverse of str.lower() on a page stem."""
    return "-".join(word.capitalize() for word in spec_id.split("-"))


def turtle_source(paths: Paths, ids: Sequence[str]) -> str:
    chunks = [f"# --- ontology ---\n{paths.ontology_ttl.read_text(encoding='utf-8')}"]
    for spec_id in ids:
        path = spec_ttl(paths, spec_id)
        if path.is_file():
            chunks.append(f"# --- {spec_id} ---\n{path.read_text(encoding='utf-8')}")
    return "\n".join(chunks)


def load_graph(paths: Paths, ids: Sequence[str] | None = None) -> Graph:
    g = Graph()
    g.bind("mon", MON)
    g.bind("app", APP)
    g.parse(data=turtle_source(paths, spec_ids(paths) if ids is None else ids), format="turtle")
    return g


def load_spec_graph(paths: Paths, spec_id: str) -> Graph:
    """The ontology plus one spec, so the spec's own triples can be isolated."""
    return load_graph(paths, [spec_id])


def run_query(g: Graph, sparql: str) -> list[tuple[str, ...]]:
    return [tuple(str(value) for value in row) for row in g.query(SPARQL_PREFIXES + sparql)]


def dangling_terms(g: Graph) -> list[str]:
    typed = {s for s in g.subjects(RDF.type, None) if isinstance(s, URIRef)}
    used = {
        term
        for triple in g
        for term in triple
        if isinstance(term, URIRef) and str(term).startswith((MON, APP))
    }
    return sorted(str(term) for term in used - typed)


def broken_links(paths: Paths, ids: Sequence[str]) -> list[str]:
    """Links in prose point at wiki page names, which are derived from spec ids."""
    known = {wiki_page_name(spec_id) for spec_id in spec_ids(paths)} | {"Ontology"}
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
