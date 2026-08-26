"""A spec moves from scaffold to modeled to verified, exercising every CLI-backing
function an agent calls, in the order an agent calls them. Design's "Round trip" testing
item: extract (scaffold), model, validate, and confirm the graph parses and its claims
resolve.
"""

from __future__ import annotations

from knowledge import db, graph, lifecycle, lint, scan
from tests.conftest import make_config

FIXTURE_TTL = """\
app:Budgets a ex:Module ;
    rdfs:label   "Budgets"@en ;
    rdfs:comment "Monthly spending limits per category."@en ;
    ex:contains app:BudgetsList .

app:BudgetsList a ex:View ;
    rdfs:label "Budgets"@en ;
    ex:partOf app:Budgets ;
    ex:route  "/platform/budgets" .

app:BudgetsAreMonthly a ex:Rule ;
    rdfs:label     "A budget resets every calendar month"@en ;
    ex:appliesTo  app:Budgets ;
    rdfs:comment   "Spending against a category clears at midnight on the first, so a limit hit in March says nothing about April."@en .
"""


def test_a_spec_can_be_scaffolded_modeled_and_verified(repo):
    conn = db.connect(repo)
    md = lifecycle.new_spec(repo, "budgets", "Budgets")
    md.write_text(
        md.read_text(encoding="utf-8") + "\nA monthly limit per category.\n",
        encoding="utf-8",
    )
    (repo.specs / "budgets" / "spec.ttl").write_text(FIXTURE_TTL, encoding="utf-8")
    scan.scan(conn, repo)

    lifecycle.mark_modeled(conn, repo, "budgets", by="writer", ontology_version="1.0.0")

    config = make_config(repo.root)
    vocab = config.vocabulary
    g = graph.load_graph(repo, vocab, ["budgets"])
    assert graph.dangling_terms(g, vocab) == []
    assert lint.invented_predicates(g, vocab) == []
    assert lint.invented_types(g, vocab) == []
    assert lint.restated_rule_comments(g, vocab) == []
    assert lint.naming_violations(g, vocab) == []

    lifecycle.verify(conn, repo, config, "budgets", by="jesus", prune=[], commit="abc123")

    row = list(conn.execute(
        "SELECT status, modeled_by, verified_by FROM spec WHERE id='budgets'"
    ))
    assert row == [("verified", "writer", "jesus")]
