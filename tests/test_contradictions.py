from knowledge import contradictions, graph
from tests.conftest import write_spec


def test_functional_conflicts_finds_two_routes_on_one_view(repo):
    write_spec(repo.root, "duplicate-route",
               'app:Assets a mon:View ; mon:route "/somewhere-else" .\n')
    g = graph.load_graph(repo)
    conflicts = contradictions.functional_conflicts(g)
    assert (
        "https://monicords.com/id/Assets", "route", ["/platform/assets", "/somewhere-else"]
    ) in conflicts


def test_functional_conflicts_is_empty_for_a_single_route(repo):
    assert contradictions.functional_conflicts(graph.load_graph(repo)) == []
