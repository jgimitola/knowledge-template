"""A spec moves from scaffold to modeled to verified, exercising every CLI-backing
function an agent calls, in the order an agent calls them. Design's "Round trip" testing
item: extract (scaffold), model, validate, and confirm the graph parses and its claims
resolve.
"""

from __future__ import annotations

from knowledge import db, graph, lifecycle, lint, scan
from tests.conftest import make_config

FIXTURE_TTL = """\
app:Budgets a mon:Module ;
    rdfs:label   "Budgets"@en ;
    rdfs:comment "Monthly spending limits per category."@en ;
    mon:contains app:BudgetsList .

app:BudgetsList a mon:View ;
    rdfs:label "Budgets"@en ;
    mon:partOf app:Budgets ;
    mon:route  "/platform/budgets" .

app:BudgetsAreMonthly a mon:Rule ;
    rdfs:label     "A budget resets every calendar month"@en ;
    mon:appliesTo  app:Budgets ;
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

    g = graph.load_graph(repo, ["budgets"])
    assert graph.dangling_terms(g) == []
    assert lint.invented_predicates(g) == []
    assert lint.invented_types(g) == []
    assert lint.restated_rule_comments(g) == []
    assert lint.naming_violations(g) == []

    config = make_config(repo.root)
    lifecycle.verify(conn, repo, config, "budgets", by="jesus", prune=[], commit="abc123")

    row = list(conn.execute(
        "SELECT status, modeled_by, verified_by FROM spec WHERE id='budgets'"
    ))
    assert row == [("verified", "writer", "jesus")]
