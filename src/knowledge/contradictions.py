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
