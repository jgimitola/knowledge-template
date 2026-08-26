from pathlib import Path

import pytest
from rdflib.compare import to_isomorphic

from knowledge import graph, paths as paths_mod
from scripts import extract_wiki

WIKI = Path(__file__).resolve().parents[2] / "monicords_app" / "docs" / "wiki"

# docs/wiki/ still exists after the migration — it holds a README pointing at this
# repository — so the directory is not the signal. Ontology.md is: legacy_graph reads it
# first, and without it there is no baseline to compare against.
requires_wiki = pytest.mark.skipif(
    not (WIKI / "Ontology.md").is_file(),
    reason="the wiki lived in the code repository only until it was retired",
)


def test_split_page_separates_prose_from_turtle():
    text = "# Title\n\nSome prose.\n\n```turtle\napp:X a mon:View .\n```\n\nMore prose.\n"
    prose, blocks = extract_wiki.split_page(text)
    assert blocks == ["app:X a mon:View .\n"]
    assert "```" not in prose
    assert "Some prose." in prose and "More prose." in prose
    assert "\n\n\n" not in prose


@requires_wiki
def test_extraction_produces_a_graph_isomorphic_to_the_wiki(tmp_path):
    """The gate. The migration must not change a single triple."""
    (tmp_path / "knowledge.toml").write_text(
        '[repo]\ncode_repo = "../monicords_app"\n\n[wiki]\nremote = "x"\n', encoding="utf-8"
    )
    (tmp_path / ".metadata").mkdir()
    target = paths_mod.get_paths(tmp_path)

    written = extract_wiki.extract(WIKI, target)

    assert len(written) == 21
    assert "ontology" not in written
    assert "_sidebar" not in written

    before = extract_wiki.legacy_graph(WIKI)
    after = graph.load_graph(target)
    assert len(before) == len(after)
    assert to_isomorphic(before) == to_isomorphic(after)


@requires_wiki
def test_every_spec_gets_id_frontmatter(tmp_path):
    (tmp_path / "knowledge.toml").write_text(
        '[repo]\ncode_repo = "../monicords_app"\n\n[wiki]\nremote = "x"\n', encoding="utf-8"
    )
    (tmp_path / ".metadata").mkdir()
    target = paths_mod.get_paths(tmp_path)
    extract_wiki.extract(WIKI, target)

    md_path = paths_mod.spec_md(target, "loans-out")
    text = md_path.read_text(encoding="utf-8")
    assert text.startswith("---\nid: loans-out\n---\n")
    assert "```turtle" not in text
    assert b"\r" not in md_path.read_bytes()
    assert b"\r" not in target.ontology_ttl.read_bytes()
    assert b"\r" not in target.ontology_readme.read_bytes()
    assert b"\r" not in target.ontology_version.read_bytes()


@requires_wiki
def test_the_ontology_is_not_a_spec(tmp_path):
    (tmp_path / "knowledge.toml").write_text(
        '[repo]\ncode_repo = "../monicords_app"\n\n[wiki]\nremote = "x"\n', encoding="utf-8"
    )
    (tmp_path / ".metadata").mkdir()
    target = paths_mod.get_paths(tmp_path)
    extract_wiki.extract(WIKI, target)

    assert not (target.specs / "ontology").exists()
    assert target.ontology_ttl.is_file()
    assert "@prefix mon:" in target.ontology_ttl.read_text(encoding="utf-8")
    assert target.ontology_version.read_text(encoding="utf-8").strip() == "1.0.0"
    assert "Why RDFS and not OWL" in target.ontology_readme.read_text(encoding="utf-8")
