from knowledge import graph, lint


def test_invented_predicates_finds_an_undeclared_property(repo, config, write_spec):
    write_spec(repo.root, "typo", 'app:Assets a ex:View ; ex:rout "/x" .\n')
    g = graph.load_graph(repo, config.vocabulary)
    assert "https://example.test/ontology#rout" in lint.invented_predicates(g, config.vocabulary)


def test_invented_predicates_is_empty_for_a_clean_graph(repo, config):
    g = graph.load_graph(repo, config.vocabulary)
    assert lint.invented_predicates(g, config.vocabulary) == []


def test_invented_types_finds_an_undeclared_class(repo, config, write_spec):
    write_spec(repo.root, "typo", 'app:Thing a ex:Widget ; rdfs:label "Thing"@en .\n')
    g = graph.load_graph(repo, config.vocabulary)
    assert "https://example.test/ontology#Widget" in lint.invented_types(g, config.vocabulary)


def test_restated_rule_comments_flags_a_comment_that_repeats_the_label(repo, config, write_spec):
    write_spec(repo.root, "lazy", """\
app:LazyRule a ex:Rule ;
    rdfs:label   "Amount is required"@en ;
    rdfs:comment "Amount is required."@en .
""")
    g = graph.load_graph(repo, config.vocabulary)
    assert "https://example.test/id/LazyRule" in lint.restated_rule_comments(g, config.vocabulary)


def test_restated_rule_comments_accepts_a_comment_that_explains_why(repo, config, write_spec):
    write_spec(repo.root, "explained", """\
app:ExplainedRule a ex:Rule ;
    rdfs:label   "Amount is required"@en ;
    rdfs:comment "An asset with no amount cannot be summed into any total."@en .
""")
    g = graph.load_graph(repo, config.vocabulary)
    assert ("https://example.test/id/ExplainedRule"
            not in lint.restated_rule_comments(g, config.vocabulary))


def test_restated_rule_comments_flags_a_missing_comment(repo, config, write_spec):
    write_spec(repo.root, "silent", 'app:SilentRule a ex:Rule ; rdfs:label "No note"@en .\n')
    g = graph.load_graph(repo, config.vocabulary)
    assert "https://example.test/id/SilentRule" in lint.restated_rule_comments(g, config.vocabulary)


def test_naming_violations_accepts_the_documented_field_pattern(repo, config, write_spec):
    write_spec(repo.root, "goodfield",
               'app:Asset_name a ex:Field ; rdfs:label "Name"@en .\n')
    g = graph.load_graph(repo, config.vocabulary)
    assert lint.naming_violations(g, config.vocabulary) == []


def test_naming_violations_flags_a_field_missing_its_owner_prefix(repo, config, write_spec):
    write_spec(repo.root, "badfield", 'app:name a ex:Field ; rdfs:label "Name"@en .\n')
    g = graph.load_graph(repo, config.vocabulary)
    assert any(
        "app:name" in msg or "id/name" in msg
        for msg in lint.naming_violations(g, config.vocabulary)
    )


def test_naming_violations_flags_an_underscore_outside_a_field(repo, config, write_spec):
    write_spec(repo.root, "badview",
               'app:Assets_List a ex:View ; rdfs:label "Assets List"@en .\n')
    g = graph.load_graph(repo, config.vocabulary)
    assert any("Assets_List" in msg for msg in lint.naming_violations(g, config.vocabulary))


def test_locally_redeclared_concepts_flags_a_concept_declared_outside_its_home_spec(
    repo, config, write_spec
):
    write_spec(repo.root, "duplicate",
               'app:Workspace a ex:Concept ; rdfs:label "Workspace"@en .\n')
    ids = graph.spec_ids(repo)
    offenders = lint.locally_redeclared_concepts(repo, config.vocabulary, ids)
    assert any("Workspace" in msg and "duplicate" in msg for msg in offenders)


def test_locally_redeclared_concepts_is_empty_when_concepts_lives_only_on_its_own_page(
    repo, config
):
    ids = graph.spec_ids(repo)
    assert lint.locally_redeclared_concepts(repo, config.vocabulary, ids) == []


CONFORMANT_TTL = """\
app:Budgets a ex:Module ;
    rdfs:label   "Budgets"@en ;
    ex:contains app:BudgetsList .

app:BudgetsList a ex:View ;
    rdfs:label   "Budgets"@en ;
    ex:partOf   app:Budgets ;
    ex:route    "/platform/budgets" ;
    ex:scopedTo app:Workspace ;
    ex:displays app:Budget_limit .

app:Budget_limit a ex:Field ;
    rdfs:label "Limit"@en ;
    ex:format "An amount in the local currency."@en .
"""


def test_domain_range_violations_flags_a_field_carrying_an_interface_element_predicate(
    repo, config, write_spec
):
    """emptyState declares rdfs:domain InterfaceElement; a Field is not one."""
    write_spec(repo.root, "misplaced", """\
app:Loan_installments a ex:Field ;
    rdfs:label     "Installments"@en ;
    ex:emptyState "No installments yet." .
""")
    g = graph.load_graph(repo, config.vocabulary)
    assert any(
        "Loan_installments" in msg and "emptyState" in msg
        for msg in lint.domain_range_violations(g, config.vocabulary)
    )


def test_domain_range_violations_flags_an_object_of_the_wrong_type(repo, config, write_spec):
    """displays declares rdfs:range Field; app:Workspace is a Concept."""
    write_spec(repo.root, "wrongobject", """\
app:Panel a ex:Section ;
    rdfs:label   "Panel"@en ;
    ex:displays app:Workspace .
""")
    g = graph.load_graph(repo, config.vocabulary)
    assert any(
        "displays" in msg and "Workspace" in msg
        for msg in lint.domain_range_violations(g, config.vocabulary)
    )


def test_domain_range_violations_accepts_conformant_individuals_across_the_subclass_closure(
    repo, config, write_spec
):
    """The acceptance case is only meaningful because this fixture is full of triples the
    check actually inspects: contains and partOf between a Module and a View, both of which
    conform only through rdfs:subClassOf InterfaceElement. Drop the closure and this test
    fails."""
    write_spec(repo.root, "budgets", CONFORMANT_TTL)
    g = graph.load_graph(repo, config.vocabulary)
    assert lint.domain_range_violations(g, config.vocabulary) == []


def test_domain_range_violations_ignores_a_literal_range(repo, config, write_spec):
    """route's range is xsd:string. A literal has no rdf:type to check it against, so the
    check must skip it rather than call every route a violation."""
    write_spec(repo.root, "budgets", CONFORMANT_TTL)
    g = graph.load_graph(repo, config.vocabulary)
    assert not any("route" in msg for msg in lint.domain_range_violations(g, config.vocabulary))


def test_ungrounded_empty_states_flags_a_string_no_sentence_states(repo, config, write_spec):
    write_spec(repo.root, "invented", """\
app:InventedTable a ex:Section ;
    rdfs:label     "Table"@en ;
    ex:emptyState "No rows to show." .
""", prose="A table of five columns, footed with a count of what it holds.\n")
    ids = graph.spec_ids(repo)
    assert any(
        "InventedTable" in msg and "No rows to show." in msg
        for msg in lint.ungrounded_empty_states(repo, config.vocabulary, ids)
    )


def test_ungrounded_empty_states_accepts_a_string_the_prose_states(repo, config, write_spec):
    write_spec(repo.root, "grounded", """\
app:GroundedTable a ex:Section ;
    rdfs:label     "Table"@en ;
    ex:emptyState "No workspaces yet." .
""", prose="With nothing to show the table reads **No workspaces yet.**\n")
    ids = graph.spec_ids(repo)
    assert lint.ungrounded_empty_states(repo, config.vocabulary, ids) == []


def test_ungrounded_empty_states_accepts_a_string_the_prose_hard_wraps(repo, config, write_spec):
    """The prose is hard-wrapped at 90 columns, so a literal can straddle a line break. A
    byte-for-byte substring test calls that ungrounded when it is not."""
    write_spec(repo.root, "wrapped", """\
app:WrappedTable a ex:Section ;
    rdfs:label     "Table"@en ;
    ex:emptyState "No deductions yet." .
""", prose="The monthly column is red. With none recorded the section reads **No\ndeductions yet.**\n")
    ids = graph.spec_ids(repo)
    assert lint.ungrounded_empty_states(repo, config.vocabulary, ids) == []
