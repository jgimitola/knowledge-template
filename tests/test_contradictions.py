from knowledge import contradictions, graph


def test_functional_conflicts_finds_two_routes_on_one_view(repo, config, write_spec):
    write_spec(repo.root, "duplicate-route",
               'app:Assets a ex:View ; ex:route "/somewhere-else" .\n')
    g = graph.load_graph(repo, config.vocabulary)
    conflicts = contradictions.functional_conflicts(g, config.vocabulary)
    assert (
        "https://example.test/id/Assets", "route", ["/platform/assets", "/somewhere-else"]
    ) in conflicts


def test_functional_conflicts_is_empty_for_a_single_route(repo, config):
    g = graph.load_graph(repo, config.vocabulary)
    assert contradictions.functional_conflicts(g, config.vocabulary) == []
