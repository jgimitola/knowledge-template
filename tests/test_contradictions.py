from dataclasses import replace

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


def test_conflict_is_found_for_a_configured_functional_property(repo, config, write_spec):
    write_spec(
        repo.root,
        "twice",
        'app:Twice a ex:View ;\n'
        '    rdfs:label "Twice"@en ;\n'
        '    ex:route "/a" ;\n'
        '    ex:route "/b" .\n',
    )
    vocab = config.vocabulary
    g = graph.load_graph(repo, vocab, ["twice"])
    found = contradictions.functional_conflicts(g, vocab)
    assert len(found) == 1
    subject, prop, values = found[0]
    assert prop == "route"
    assert values == ["/a", "/b"]


def test_no_configured_properties_returns_none(repo, config):
    vocab = replace(
        config.vocabulary,
        checks=replace(config.vocabulary.checks, functional_properties=()),
    )
    g = graph.load_graph(repo, vocab)
    assert contradictions.functional_conflicts(g, vocab) is None
