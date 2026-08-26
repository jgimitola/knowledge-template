import pytest

from knowledge.config import ConfigError, load_config

FULL = """\
[project]
name = "Example"

[vocabulary]
ontology_file = "example.ttl"
namespace = "https://example.com/ontology#"
instances = "https://example.com/id/"
prefix = "ex"
instance_prefix = "app"
rule_class = "Rule"
concept_class = "Concept"
concept_spec = "concepts"
field_class = "Field"
field_name_pattern = "^[A-Z][A-Za-z0-9]*_[a-z][A-Za-z0-9]*$"
underscore_reserved = true
functional_properties = ["route", "editable"]
verbatim_string_properties = ["emptyState"]

[[ask]]
name = "modules"
query = "SELECT ?l WHERE { ?m a ex:Module ; rdfs:label ?l }"

[repo]
code_repo = "../code"

[dependencies]
route_property = "route"
route_glob = "app/**/{segments}/page.tsx"
absorbed_prefixes = ["platform"]

[publish]
target = "github-wiki"
remote = "https://example.com/x.wiki.git"

[publish.sidebar]
title = "Example"
order = ["home", "concepts"]
nested_under = { "concepts" = "home" }
"""

MINIMAL = """\
[project]
name = "Example"

[vocabulary]
ontology_file = "ontology.ttl"
namespace = "https://example.com/ontology#"
instances = "https://example.com/id/"
prefix = "ex"
instance_prefix = "app"
"""


def write(tmp_path, text):
    (tmp_path / "knowledge.toml").write_text(text, encoding="utf-8")
    return tmp_path


def test_full_config_round_trips(tmp_path):
    config = load_config(write(tmp_path, FULL))
    assert config.project_name == "Example"
    assert config.vocabulary.prefix == "ex"
    assert config.vocabulary.checks.functional_properties == ("route", "editable")
    assert config.vocabulary.checks.underscore_reserved is True
    assert [s.name for s in config.surveys] == ["modules"]
    assert config.code_repo is not None and config.code_repo.name == "code"
    assert config.dependencies.absorbed_prefixes == ("platform",)
    assert config.publish.target == "github-wiki"
    assert config.publish.sidebar.nested_under == {"concepts": "home"}


def test_minimal_config_defaults_every_optional_section(tmp_path):
    config = load_config(write(tmp_path, MINIMAL))
    assert config.vocabulary.checks.rule_class == ""
    assert config.surveys == ()
    assert config.code_repo is None
    assert config.dependencies.derives is False
    assert config.publish.target == "none"
    assert config.publish.sidebar.order == ()


def test_placeholders_read_as_empty(tmp_path):
    text = MINIMAL + '\n[repo]\ncode_repo = "{{CODE_REPO}}"\n'
    config = load_config(write(tmp_path, text))
    assert config.code_repo is None


def test_template_marker_is_reported(tmp_path):
    text = "[template]\nunconfigured = true\n\n" + MINIMAL
    assert load_config(write(tmp_path, text)).unconfigured is True
    assert load_config(write(tmp_path, MINIMAL)).unconfigured is False


def test_missing_required_key_names_it(tmp_path):
    text = '[project]\nname = "Example"\n\n[vocabulary]\nprefix = "ex"\n'
    with pytest.raises(ConfigError) as exc:
        load_config(write(tmp_path, text))
    assert "vocabulary.namespace" in str(exc.value)


def test_unknown_publish_target_is_rejected(tmp_path):
    text = MINIMAL + '\n[publish]\ntarget = "carrier-pigeon"\n'
    with pytest.raises(ConfigError) as exc:
        load_config(write(tmp_path, text))
    assert "carrier-pigeon" in str(exc.value)
