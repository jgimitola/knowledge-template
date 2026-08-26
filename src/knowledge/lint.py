"""Mechanical checks on the graph's ontology conformance.

Everything here is the part of the writer's audit step that does not need a model: an
invented predicate or class, a concept declared locally instead of referenced, a rule
comment that just restates its label, a name that breaks the pattern its kind is supposed
to follow (ontology/README.md's naming table). `validate --strict` runs this on every push,
so the agent is checked rather than trusted for exactly this part of its job.
"""

from __future__ import annotations

import re

from rdflib import RDF, RDFS, Graph, URIRef

from knowledge.graph import APP, MON
from knowledge.paths import Paths

FIELD_NAME = re.compile(r"^[A-Z][A-Za-z0-9]*_[a-z][A-Za-z0-9]*$")


def _local(term) -> str:
    return str(term).rsplit("#", 1)[-1].rsplit("/", 1)[-1]


def known_terms(g: Graph) -> tuple[set[str], set[str]]:
    """(classes, properties) the ontology itself declares under mon:."""
    classes = {str(s) for s in g.subjects(RDF.type, RDFS.Class) if str(s).startswith(MON)}
    properties = {
        str(s) for s in g.subjects(RDF.type, RDF.Property) if str(s).startswith(MON)
    }
    return classes, properties


def invented_predicates(g: Graph) -> list[str]:
    """Every mon: predicate actually asserted, that the ontology never declared."""
    _, properties = known_terms(g)
    used = {str(p) for p in g.predicates() if str(p).startswith(MON)}
    return sorted(used - properties)


def invented_types(g: Graph) -> list[str]:
    """Every mon: class actually asserted with `a`, that the ontology never declared."""
    classes, _ = known_terms(g)
    used = {str(o) for o in g.objects(None, RDF.type) if str(o).startswith(MON)}
    return sorted(used - classes)


def restated_rule_comments(g: Graph) -> list[str]:
    """A comment that just repeats the label carries no reason a reader could not already
    infer from the label alone — the whole point of a mon:Rule's rdfs:comment."""

    def norm(text: str) -> str:
        return text.strip().rstrip(".").lower()

    offenders = []
    for rule in g.subjects(RDF.type, URIRef(MON + "Rule")):
        label = next((str(o) for o in g.objects(rule, RDFS.label)), "")
        comment = next((str(o) for o in g.objects(rule, RDFS.comment)), "")
        if not comment or norm(comment) == norm(label):
            offenders.append(str(rule))
    return sorted(offenders)


def naming_violations(g: Graph) -> list[str]:
    """Fields follow `<Owner>_<field>`; every other individual avoids the underscore that
    pattern reserves for fields (ontology/README.md's naming table)."""
    offenders = []
    fields = set(g.subjects(RDF.type, URIRef(MON + "Field")))
    for term in fields:
        if not FIELD_NAME.match(_local(term)):
            offenders.append(f"{term} does not match the <Owner>_<field> pattern")
    non_fields = {
        s for s in g.subjects(RDF.type, None)
        if str(s).startswith(APP) and s not in fields
    }
    for term in non_fields:
        if "_" in _local(term):
            offenders.append(f"{term} uses an underscore, which is reserved for fields")
    return sorted(offenders)


def _superclasses(g: Graph) -> dict[URIRef, set[URIRef]]:
    """Every class each class inherits from, transitively over rdfs:subClassOf.

    Without this, mon:contains — declared over mon:InterfaceElement — would flag every
    triple in the corpus, because nothing is ever typed as mon:InterfaceElement directly.
    mon:Module, mon:View and mon:Section are all subclasses of it.
    """
    direct: dict[URIRef, set[URIRef]] = {}
    for sub, sup in g.subject_objects(RDFS.subClassOf):
        direct.setdefault(sub, set()).add(sup)
    closure: dict[URIRef, set[URIRef]] = {}
    for cls in direct:
        seen: set[URIRef] = set()
        queue = [cls]
        while queue:
            for parent in direct.get(queue.pop(), ()):
                if parent not in seen:
                    seen.add(parent)
                    queue.append(parent)
        closure[cls] = seen
    return closure


def domain_range_violations(g: Graph) -> list[str]:
    """A declared predicate used with a subject or object of the wrong type.

    The five checks above catch invented terms. This catches the other half of ontology
    conformance: a real mon: predicate asserted where the ontology says it cannot go —
    mon:emptyState, whose domain is mon:InterfaceElement, hung on a mon:Field.

    Two tolerances keep it free of false positives. Untyped terms are skipped, because
    graph.dangling_terms already owns those and a term with no rdf:type cannot be judged
    against a class. Ranges outside mon: are skipped, because xsd:string and rdfs:Literal
    describe a literal's datatype, which is not a class an individual is typed with.
    """
    supers = _superclasses(g)

    def types_of(term) -> set[URIRef]:
        found: set[URIRef] = set()
        for cls in g.objects(term, RDF.type):
            found.add(cls)
            found |= supers.get(cls, set())
        return found

    def describe(types: set[URIRef]) -> str:
        return ", ".join(f"mon:{_local(t)}" for t in sorted(types, key=str))

    offenders = []
    for prop in g.subjects(RDF.type, RDF.Property):
        if not str(prop).startswith(MON):
            continue
        domains = set(g.objects(prop, RDFS.domain))
        ranges = {r for r in g.objects(prop, RDFS.range) if str(r).startswith(MON)}
        if not domains and not ranges:
            continue
        name = f"mon:{_local(prop)}"
        for subject, obj in g.subject_objects(prop):
            subject_types = types_of(subject)
            if domains and subject_types and not (domains & subject_types):
                offenders.append(
                    f"{subject} is {describe(subject_types)}, but {name} declares"
                    f" rdfs:domain {describe(domains)}"
                )
            if not ranges or not isinstance(obj, URIRef):
                continue
            object_types = types_of(obj)
            if object_types and not (ranges & object_types):
                offenders.append(
                    f"{obj} is {describe(object_types)}, but {name} declares"
                    f" rdfs:range {describe(ranges)}"
                )
    return sorted(offenders)


def ungrounded_empty_states(paths: Paths, ids) -> list[str]:
    """A mon:emptyState literal no sentence in the owning spec.md states.

    mon:emptyState is the one predicate whose value is a verbatim UI string rather than a
    paraphrase, which makes "does the prose say this?" a question code can answer. The
    writer's graph-to-prose rule says a triple the prose does not support is removed; this
    is that rule, mechanised, for the one predicate it can be mechanised for. mon:format is
    paraphrase by design and mon:defaultsTo often is too — neither belongs here.

    The prose is hard-wrapped, so the comparison collapses runs of whitespace first. Without
    that, a string straddling a line break reads as ungrounded when it is not: three of the
    corpus's fifteen grounded literals are wrapped that way.
    """
    from knowledge.graph import load_spec_graph
    from knowledge.paths import spec_md

    empty_state = URIRef(MON + "emptyState")
    offenders = []
    for spec_id in ids:
        path = spec_md(paths, spec_id)
        if not path.is_file():
            continue
        prose = re.sub(r"\s+", " ", path.read_text(encoding="utf-8"))
        for subject, literal in load_spec_graph(paths, spec_id).subject_objects(empty_state):
            if str(literal) not in prose:
                offenders.append(
                    f"{subject} has mon:emptyState {str(literal)!r},"
                    f" which no sentence of {spec_id}/spec.md states"
                )
    return sorted(offenders)


def locally_redeclared_concepts(paths: Paths, ids) -> list[str]:
    """A concept declared once on the `concepts` spec and referenced everywhere else is
    what turns independent specs into one connected graph. Declaring it again on some other
    spec is the same fact twice, free to drift apart from the original."""
    from knowledge.graph import load_spec_graph

    concept = URIRef(MON + "Concept")
    offenders = []
    for spec_id in ids:
        if spec_id == "concepts":
            continue
        g = load_spec_graph(paths, spec_id)
        for term in g.subjects(RDF.type, concept):
            offenders.append(f"{term} declared on {spec_id!r} instead of concepts")
    return sorted(offenders)
