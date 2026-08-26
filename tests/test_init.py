import pytest

from knowledge import init
from knowledge.config import load_config


def build_template(tmp_path):
    """A miniature of the shipped template.

    Machine-parsed fields (knowledge.toml's [vocabulary] namespace/instances/prefix, and the
    ontology file's own @prefix lines) ship as WORKING DEFAULTS — `load_config` and rdflib's
    Turtle parser must both succeed before `init` ever runs, so a `{{TOKEN}}` there would
    break the template itself (see ruling C12). Only prose-read files carry `{{TOKEN}}`
    placeholders.
    """
    (tmp_path / "knowledge.toml").write_text(
        "[template]\nunconfigured = true\n\n"
        '[project]\nname = "{{PROJECT_NAME}}"\n\n'
        "[vocabulary]\n"
        'ontology_file = "ontology.ttl"\n'
        'namespace = "https://example.com/ontology#"\n'
        'instances = "https://example.com/id/"\n'
        'prefix = "ex"\n'
        'instance_prefix = "app"\n\n'
        '[repo]\ncode_repo = "{{CODE_REPO}}"\n',
        encoding="utf-8",
    )
    ontology = tmp_path / "ontology"
    ontology.mkdir()
    (ontology / "ontology.ttl").write_text(
        "@prefix ex: <https://example.com/ontology#> .\n"
        "@prefix app: <https://example.com/id/> .\n"
        "\n"
        "ex:Concept a rdfs:Class ; rdfs:label \"Concept\"@en .\n",
        encoding="utf-8",
    )
    (ontology / "README.md").write_text("# {{PROJECT_NAME}} ontology\n", encoding="utf-8")
    (ontology / "VERSION").write_text("1.0.0\n", encoding="utf-8")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "README.template.md").write_text("# {{PROJECT_NAME}}\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# knowledge-template\n", encoding="utf-8")
    agents = tmp_path / ".claude" / "agents"
    agents.mkdir(parents=True)
    (agents / "writer.md").write_text("Audit against {{ONTOLOGY_FILE}}.\n", encoding="utf-8")
    (agents / "interviewer.md").write_text("Interview about {{PROJECT_NAME}}.\n", encoding="utf-8")
    skill = tmp_path / "integrations" / "code-repo" / ".claude" / "skills" / "knowledge-base"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("Read {{PROJECT_NAME}}'s knowledge base.\n", encoding="utf-8")
    example = tmp_path / "specs" / "example"
    example.mkdir(parents=True)
    (example / "spec.md").write_text("---\nid: example\n---\n\n# Example\n", encoding="utf-8")
    (example / "spec.ttl").write_text("# example\n", encoding="utf-8")
    (tmp_path / ".metadata").mkdir()
    (tmp_path / ".metadata" / "dump.sql").write_text("-- seeded\n", encoding="utf-8")
    return tmp_path


ANSWERS = init.Answers(
    project_name="Acme",
    base_iri="https://acme.test/",
    prefix="acme",
    instance_prefix="app",
    code_repo="../acme_app",
    publish_target="none",
    dependency_preset="none",
)


def test_slugify_lowercases_and_strips_punctuation():
    # The brief's own expected value here ("acmewidgets") does not match its own sample
    # implementation ("anything that is not a letter or a digit goes" — which keeps "Inc"'s
    # letters). No correction addresses this; the implementation's docstring is unambiguous
    # and this is the simpler, well-documented behavior, so the assertion is fixed to match
    # it rather than inventing suffix-stripping logic nothing else in the brief asks for.
    assert init.slugify("Acme Widgets, Inc.") == "acmewidgetsinc"
    assert init.slugify("monicords") == "monicords"


def test_run_substitutes_every_placeholder(tmp_path):
    root = build_template(tmp_path)
    init.run(root, ANSWERS)
    assert init.remaining_placeholders(root) == []


def test_run_produces_a_loadable_config(tmp_path):
    root = build_template(tmp_path)
    init.run(root, ANSWERS)
    config = load_config(root)
    assert config.project_name == "Acme"
    assert config.vocabulary.namespace == "https://acme.test/ontology#"
    assert config.vocabulary.prefix == "acme"
    assert config.unconfigured is False
    assert config.code_repo is not None


def test_run_rewrites_the_ontology_prefix_lines(tmp_path):
    root = build_template(tmp_path)
    init.run(root, ANSWERS)
    text = (root / "ontology" / "ontology.ttl").read_text(encoding="utf-8")
    assert "@prefix acme: <https://acme.test/ontology#> ." in text


def test_run_rewrites_ontology_term_usages_too(tmp_path):
    root = build_template(tmp_path)
    init.run(root, ANSWERS)
    text = (root / "ontology" / "ontology.ttl").read_text(encoding="utf-8")
    assert "acme:Concept a rdfs:Class" in text
    assert "ex:" not in text


def test_run_removes_the_example_spec_and_empties_the_dump(tmp_path):
    root = build_template(tmp_path)
    init.run(root, ANSWERS)
    assert not (root / "specs" / "example").exists()
    assert "seeded" not in (root / ".metadata" / "dump.sql").read_text(encoding="utf-8")


def test_run_replaces_the_readme_with_the_template_one(tmp_path):
    root = build_template(tmp_path)
    init.run(root, ANSWERS)
    assert (root / "README.md").read_text(encoding="utf-8") == "# Acme\n"


def test_run_refuses_a_configured_repository(tmp_path):
    root = build_template(tmp_path)
    init.run(root, ANSWERS)
    with pytest.raises(RuntimeError) as exc:
        init.run(root, ANSWERS)
    assert "already configured" in str(exc.value)


def test_remaining_placeholders_reports_what_is_left(tmp_path):
    root = build_template(tmp_path)
    (root / "stray.md").write_text("# {{PROJECT_NAME}}\n", encoding="utf-8")
    init.run(root, ANSWERS)
    assert any("stray.md" in entry for entry in init.remaining_placeholders(root))


def test_an_empty_code_repo_answer_disables_staleness(tmp_path):
    root = build_template(tmp_path)
    from dataclasses import replace
    init.run(root, replace(ANSWERS, code_repo=""))
    assert load_config(root).code_repo is None


def test_remaining_placeholders_ignores_a_token_shaped_docstring_in_python_source(tmp_path):
    """The tooling's own .py source explains the {{TOKEN}} syntax using literal examples
    (this repository's src/knowledge/config.py does exactly this). None of that is content
    `init` is ever asked to substitute, so a sweep for real leftover placeholders must not
    flag it — otherwise `--check` could never pass in a repository that ships this tool's
    own source alongside the generated project, exactly what the shipped template does."""
    root = build_template(tmp_path)
    src = root / "src" / "knowledge"
    src.mkdir(parents=True)
    (src / "config.py").write_text(
        'def f():\n    """An unsubstituted {{PLACEHOLDER}} reads as empty."""\n',
        encoding="utf-8",
    )
    init.run(root, ANSWERS)
    assert init.remaining_placeholders(root) == []


def test_run_reports_only_files_it_actually_changed(tmp_path):
    """`run` must not claim it rewrote a file whose text it left untouched."""
    root = build_template(tmp_path)
    rewritten = init.run(root, ANSWERS)
    for relative in rewritten:
        assert (root / relative).is_file(), f"{relative} was reported rewritten but is gone"
    # VERSION carries no placeholder and nothing touches it — it must not be claimed.
    assert "ontology/VERSION" not in rewritten
