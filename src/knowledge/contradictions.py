"""Mechanical contradiction checks: the part of the interviewer's per-answer check that is
a SPARQL-shaped query rather than a judgement call.
"""

from __future__ import annotations

from collections import defaultdict

from rdflib import Graph, URIRef

from knowledge.graph import MON

# Properties the ontology documents as single-valued, plus mon:defaultsTo and mon:route —
# the design's own two examples of what this check looks for. "Functional by convention"
# because RDFS never enforces it (ontology/README.md, "Properties with literal values").
FUNCTIONAL_PROPERTIES = ("route", "editable", "required", "viewport", "defaultsTo")


def functional_conflicts(g: Graph) -> list[tuple[str, str, list[str]]]:
    """(subject, property, sorted values) for every subject asserting more than one value
    on a property that is supposed to hold at most one — two mon:route values on one view,
    two mon:defaultsTo on one field."""
    seen: dict[tuple[str, str], set[str]] = defaultdict(set)
    for prop in FUNCTIONAL_PROPERTIES:
        for subject, obj in g.subject_objects(URIRef(MON + prop)):
            seen[(str(subject), prop)].add(str(obj))
    return sorted(
        (subject, prop, sorted(values))
        for (subject, prop), values in seen.items()
        if len(values) > 1
    )
