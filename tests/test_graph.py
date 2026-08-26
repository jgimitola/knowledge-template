from knowledge import graph
from tests.conftest import write_spec


def test_the_graph_parses_and_holds_both_specs(repo):
    g = graph.load_graph(repo)
    labels = {row[0] for row in graph.run_query(g, "SELECT ?l WHERE { ?s rdfs:label ?l }")}
    assert "Assets" in labels
    assert "Workspace" in labels


def test_load_graph_can_be_limited_to_some_specs(repo):
    g = graph.load_graph(repo, ["assets"])
    routes = graph.run_query(g, "SELECT ?r WHERE { ?s mon:route ?r }")
    assert routes == [("/platform/assets",)]
    labels = {row[0] for row in graph.run_query(g, "SELECT ?l WHERE { ?s rdfs:label ?l }")}
    assert "Workspace" not in labels


def test_spec_ids_are_sorted_folder_names(repo):
    assert graph.spec_ids(repo) == ["assets", "concepts"]


def test_dangling_terms_finds_a_referenced_but_undeclared_node(repo):
    write_spec(repo.root, "orphan", 'app:Orphan a mon:View ; mon:relatesTo app:NeverDeclared .\n')
    g = graph.load_graph(repo)
    assert "https://monicords.com/id/NeverDeclared" in graph.dangling_terms(g)


def test_dangling_terms_is_empty_for_a_complete_graph(repo):
    assert graph.dangling_terms(graph.load_graph(repo)) == []


def test_wiki_page_name_round_trips_every_shape():
    assert graph.wiki_page_name("home") == "Home"
    assert graph.wiki_page_name("loans-out") == "Loans-Out"
    assert graph.wiki_page_name("expenses-calendar") == "Expenses-Calendar"
    assert graph.wiki_page_name("profile-account") == "Profile-Account"


def test_broken_links_reports_a_link_to_a_page_that_does_not_exist(repo):
    write_spec(repo.root, "lonely", "app:Lonely a mon:View ; rdfs:label \"Lonely\"@en .\n",
               "Points at [Nowhere](Nowhere).\n")
    broken = graph.broken_links(repo, graph.spec_ids(repo))
    assert any("Nowhere" in entry for entry in broken)


def test_broken_links_accepts_a_section_anchor_and_the_ontology_page(repo):
    write_spec(repo.root, "anchored", "app:Anchored a mon:View ; rdfs:label \"A\"@en .\n",
               "See [workspace](Concepts#workspace) and [Ontology](Ontology).\n")
    assert graph.broken_links(repo, graph.spec_ids(repo)) == []


def test_the_serialised_graph_carries_the_mon_and_app_prefixes(repo):
    text = graph.load_graph(repo).serialize(format="turtle")
    assert "@prefix mon:" in text
    assert "@prefix app:" in text
