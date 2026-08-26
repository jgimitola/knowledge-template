from knowledge import graph
from knowledge.vocab import Vocabulary


def test_the_graph_parses_and_holds_both_specs(repo, config):
    g = graph.load_graph(repo, config.vocabulary)
    labels = {row[0] for row in graph.run_query(g, config.vocabulary,
                                                 "SELECT ?l WHERE { ?s rdfs:label ?l }")}
    assert "Assets" in labels
    assert "Workspace" in labels


def test_load_graph_can_be_limited_to_some_specs(repo, config):
    g = graph.load_graph(repo, config.vocabulary, ["assets"])
    routes = graph.run_query(g, config.vocabulary, "SELECT ?r WHERE { ?s ex:route ?r }")
    assert routes == [("/platform/assets",)]
    labels = {row[0] for row in graph.run_query(g, config.vocabulary,
                                                 "SELECT ?l WHERE { ?s rdfs:label ?l }")}
    assert "Workspace" not in labels


def test_spec_ids_are_sorted_folder_names(repo):
    assert graph.spec_ids(repo) == ["assets", "concepts"]


def test_dangling_terms_finds_a_referenced_but_undeclared_node(repo, config, write_spec):
    write_spec(repo.root, "orphan", 'app:Orphan a ex:View ; ex:relatesTo app:NeverDeclared .\n')
    g = graph.load_graph(repo, config.vocabulary)
    assert "https://example.test/id/NeverDeclared" in graph.dangling_terms(g, config.vocabulary)


def test_dangling_terms_is_empty_for_a_complete_graph(repo, config):
    g = graph.load_graph(repo, config.vocabulary)
    assert graph.dangling_terms(g, config.vocabulary) == []


def test_page_name_round_trips_every_shape():
    assert graph.page_name("home") == "Home"
    assert graph.page_name("loans-out") == "Loans-Out"
    assert graph.page_name("expenses-calendar") == "Expenses-Calendar"
    assert graph.page_name("profile-account") == "Profile-Account"


def test_broken_links_reports_a_link_to_a_page_that_does_not_exist(repo, write_spec):
    write_spec(repo.root, "lonely", "app:Lonely a ex:View ; rdfs:label \"Lonely\"@en .\n",
               "Points at [Nowhere](Nowhere).\n")
    broken = graph.broken_links(repo, graph.spec_ids(repo))
    assert any("Nowhere" in entry for entry in broken)


def test_broken_links_accepts_a_section_anchor_and_the_ontology_page(repo, write_spec):
    write_spec(repo.root, "anchored", "app:Anchored a ex:View ; rdfs:label \"A\"@en .\n",
               "See [workspace](Concepts#workspace) and [Ontology](Ontology).\n")
    assert graph.broken_links(repo, graph.spec_ids(repo)) == []


def test_the_serialised_graph_carries_the_configured_prefixes(repo, config):
    text = graph.load_graph(repo, config.vocabulary).serialize(format="turtle")
    assert "@prefix ex:" in text
    assert "@prefix app:" in text


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
