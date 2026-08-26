import pytest

from knowledge import paths


def make_repo(tmp_path):
    (tmp_path / "knowledge.toml").write_text(
        '[repo]\ncode_repo = "../code"\n\n'
        '[wiki]\nremote = "https://example.com/x.wiki.git"\n',
        encoding="utf-8",
    )
    (tmp_path / "specs" / "assets").mkdir(parents=True)
    return tmp_path


def test_find_root_walks_up_from_a_nested_directory(tmp_path):
    root = make_repo(tmp_path)
    assert paths.find_root(root / "specs" / "assets") == root


def test_find_root_raises_when_there_is_no_marker(tmp_path):
    with pytest.raises(RuntimeError, match="knowledge.toml"):
        paths.find_root(tmp_path)


def test_paths_are_derived_from_the_root(tmp_path):
    root = make_repo(tmp_path)
    p = paths.get_paths(root)
    assert p.specs == root / "specs"
    assert p.ontology_ttl == root / "ontology" / "ontology.ttl"
    assert p.db == root / ".metadata" / "knowledge.db"
    assert p.dump == root / ".metadata" / "dump.sql"
    assert paths.spec_md(p, "assets") == root / "specs" / "assets" / "spec.md"
    assert paths.spec_ttl(p, "assets") == root / "specs" / "assets" / "spec.ttl"
