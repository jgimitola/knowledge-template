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
