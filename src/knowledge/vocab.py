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
