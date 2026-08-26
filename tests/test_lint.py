from knowledge import graph, lint
from tests.conftest import write_spec


def test_invented_predicates_finds_an_undeclared_mon_property(repo):
    write_spec(repo.root, "typo", 'app:Assets a mon:View ; mon:rout "/x" .\n')
    g = graph.load_graph(repo)
    assert "https://monicords.com/ontology#rout" in lint.invented_predicates(g)


def test_invented_predicates_is_empty_for_a_clean_graph(repo):
    assert lint.invented_predicates(graph.load_graph(repo)) == []


def test_invented_types_finds_an_undeclared_mon_class(repo):
    write_spec(repo.root, "typo", 'app:Thing a mon:Widget ; rdfs:label "Thing"@en .\n')
    g = graph.load_graph(repo)
    assert "https://monicords.com/ontology#Widget" in lint.invented_types(g)


def test_restated_rule_comments_flags_a_comment_that_repeats_the_label(repo):
    write_spec(repo.root, "lazy", """\
app:LazyRule a mon:Rule ;
    rdfs:label   "Amount is required"@en ;
    rdfs:comment "Amount is required."@en .
""")
    g = graph.load_graph(repo)
    assert "https://monicords.com/id/LazyRule" in lint.restated_rule_comments(g)


def test_restated_rule_comments_accepts_a_comment_that_explains_why(repo):
    write_spec(repo.root, "explained", """\
app:ExplainedRule a mon:Rule ;
    rdfs:label   "Amount is required"@en ;
    rdfs:comment "An asset with no amount cannot be summed into any total."@en .
""")
    g = graph.load_graph(repo)
    assert "https://monicords.com/id/ExplainedRule" not in lint.restated_rule_comments(g)


def test_restated_rule_comments_flags_a_missing_comment(repo):
    write_spec(repo.root, "silent", 'app:SilentRule a mon:Rule ; rdfs:label "No note"@en .\n')
    g = graph.load_graph(repo)
    assert "https://monicords.com/id/SilentRule" in lint.restated_rule_comments(g)


def test_naming_violations_accepts_the_documented_field_pattern(repo):
    write_spec(repo.root, "goodfield",
               'app:Asset_name a mon:Field ; rdfs:label "Name"@en .\n')
    g = graph.load_graph(repo)
    assert lint.naming_violations(g) == []


def test_naming_violations_flags_a_field_missing_its_owner_prefix(repo):
    write_spec(repo.root, "badfield", 'app:name a mon:Field ; rdfs:label "Name"@en .\n')
    g = graph.load_graph(repo)
    assert any("app:name" in msg or "id/name" in msg for msg in lint.naming_violations(g))


def test_naming_violations_flags_an_underscore_outside_a_field(repo):
    write_spec(repo.root, "badview",
               'app:Assets_List a mon:View ; rdfs:label "Assets List"@en .\n')
    g = graph.load_graph(repo)
    assert any("Assets_List" in msg for msg in lint.naming_violations(g))


def test_locally_redeclared_concepts_flags_a_concept_declared_outside_its_home_spec(repo):
    write_spec(repo.root, "duplicate",
               'app:Workspace a mon:Concept ; rdfs:label "Workspace"@en .\n')
    ids = graph.spec_ids(repo)
    offenders = lint.locally_redeclared_concepts(repo, ids)
    assert any("Workspace" in msg and "duplicate" in msg for msg in offenders)


def test_locally_redeclared_concepts_is_empty_when_concepts_lives_only_on_its_own_page(repo):
    ids = graph.spec_ids(repo)
    assert lint.locally_redeclared_concepts(repo, ids) == []


CONFORMANT_TTL = """\
app:Budgets a mon:Module ;
    rdfs:label   "Budgets"@en ;
    mon:contains app:BudgetsList .

app:BudgetsList a mon:View ;
    rdfs:label   "Budgets"@en ;
    mon:partOf   app:Budgets ;
    mon:route    "/platform/budgets" ;
    mon:scopedTo app:Workspace ;
    mon:displays app:Budget_limit .

app:Budget_limit a mon:Field ;
    rdfs:label "Limit"@en ;
    mon:format "An amount in the local currency."@en .
"""


def test_domain_range_violations_flags_a_field_carrying_an_interface_element_predicate(repo):
    """mon:emptyState declares rdfs:domain mon:InterfaceElement; a mon:Field is not one.

    This is the live violation the corpus actually carried, on app:LoanOut_installments.
    """
    write_spec(repo.root, "misplaced", """\
app:Loan_installments a mon:Field ;
    rdfs:label     "Installments"@en ;
    mon:emptyState "No installments yet." .
""")
    g = graph.load_graph(repo)
    assert any(
        "Loan_installments" in msg and "emptyState" in msg
        for msg in lint.domain_range_violations(g)
    )


def test_domain_range_violations_flags_an_object_of_the_wrong_type(repo):
    """mon:displays declares rdfs:range mon:Field; app:Workspace is a mon:Concept."""
    write_spec(repo.root, "wrongobject", """\
app:Panel a mon:Section ;
    rdfs:label   "Panel"@en ;
    mon:displays app:Workspace .
""")
    g = graph.load_graph(repo)
    assert any(
        "displays" in msg and "Workspace" in msg
        for msg in lint.domain_range_violations(g)
    )


def test_domain_range_violations_accepts_conformant_individuals_across_the_subclass_closure(repo):
    """The acceptance case is only meaningful because this fixture is full of triples the
    check actually inspects: mon:contains and mon:partOf between a Module and a View, both
    of which conform only through rdfs:subClassOf mon:InterfaceElement. Drop the closure and
    this test fails."""
    write_spec(repo.root, "budgets", CONFORMANT_TTL)
    g = graph.load_graph(repo)
    assert lint.domain_range_violations(g) == []


def test_domain_range_violations_ignores_a_literal_range(repo):
    """mon:route's range is xsd:string. A literal has no rdf:type to check it against, so
    the check must skip it rather than call every route a violation."""
    write_spec(repo.root, "budgets", CONFORMANT_TTL)
    g = graph.load_graph(repo)
    assert not any("route" in msg for msg in lint.domain_range_violations(g))


def test_ungrounded_empty_states_flags_a_string_no_sentence_states(repo):
    write_spec(repo.root, "invented", """\
app:InventedTable a mon:Section ;
    rdfs:label     "Table"@en ;
    mon:emptyState "No rows to show." .
""", prose="A table of five columns, footed with a count of what it holds.\n")
    ids = graph.spec_ids(repo)
    assert any(
        "InventedTable" in msg and "No rows to show." in msg
        for msg in lint.ungrounded_empty_states(repo, ids)
    )


def test_ungrounded_empty_states_accepts_a_string_the_prose_states(repo):
    write_spec(repo.root, "grounded", """\
app:GroundedTable a mon:Section ;
    rdfs:label     "Table"@en ;
    mon:emptyState "No workspaces yet." .
""", prose="With nothing to show the table reads **No workspaces yet.**\n")
    ids = graph.spec_ids(repo)
    assert lint.ungrounded_empty_states(repo, ids) == []


def test_ungrounded_empty_states_accepts_a_string_the_prose_hard_wraps(repo):
    """The prose is hard-wrapped at 90 columns, so a literal can straddle a line break. A
    byte-for-byte substring test calls that ungrounded; incomes-detail's 'No deductions
    yet.' is the real case, wrapped between 'No' and 'deductions'."""
    write_spec(repo.root, "wrapped", """\
app:WrappedTable a mon:Section ;
    rdfs:label     "Table"@en ;
    mon:emptyState "No deductions yet." .
""", prose="The monthly column is red. With none recorded the section reads **No\ndeductions yet.**\n")
    ids = graph.spec_ids(repo)
    assert lint.ungrounded_empty_states(repo, ids) == []
