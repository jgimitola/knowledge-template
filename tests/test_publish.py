from knowledge import db, publish, scan


def test_strip_frontmatter_removes_only_the_leading_block():
    text = "---\nid: assets\n---\n\n# Assets\n\nProse with --- inside.\n"
    assert publish.strip_frontmatter(text) == "# Assets\n\nProse with --- inside.\n"


def test_render_page_has_no_frontmatter_and_no_turtle(repo):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    page = publish.render_page(conn, repo, "assets")
    assert not page.startswith("---")
    assert "```turtle" not in page
    assert "# Assets" in page


def test_write_pages_names_files_by_wiki_page(repo, tmp_path):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    written = publish.write_pages(conn, repo, tmp_path)
    assert sorted(written) == ["Assets.md", "Concepts.md", "Ontology.md", "_Sidebar.md"]
    assert (tmp_path / "Assets.md").is_file()


def test_write_pages_skips_a_spec_that_does_not_publish(repo, tmp_path):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    conn.execute("UPDATE spec SET publishes_to_wiki = 0 WHERE id = 'concepts'")
    written = publish.write_pages(conn, repo, tmp_path)
    assert "Concepts.md" not in written
    assert "Assets.md" in written


def test_the_sidebar_is_generated_and_lists_published_pages(repo, tmp_path):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    publish.write_pages(conn, repo, tmp_path)
    sidebar = (tmp_path / "_Sidebar.md").read_text(encoding="utf-8")
    assert "[Assets](Assets)" in sidebar
    assert "[Ontology](Ontology)" in sidebar


def test_the_sidebar_labels_home_as_home_not_its_page_title(repo, tmp_path):
    home_dir = repo.specs / "home"
    home_dir.mkdir()
    (home_dir / "spec.md").write_text(
        "---\nid: home\n---\n\n# Monicords\n\nProse.\n", encoding="utf-8"
    )
    (home_dir / "spec.ttl").write_text("", encoding="utf-8")
    conn = db.connect(repo)
    scan.scan(conn, repo)
    publish.write_pages(conn, repo, tmp_path)
    sidebar = (tmp_path / "_Sidebar.md").read_text(encoding="utf-8")
    assert "[Home](Home)" in sidebar
    assert "[Monicords](Home)" not in sidebar


def test_the_reference_section_files_architecture_after_ontology(repo, tmp_path):
    arch_dir = repo.specs / "architecture"
    arch_dir.mkdir()
    (arch_dir / "spec.md").write_text(
        "---\nid: architecture\n---\n\n# Architecture\n\nProse.\n", encoding="utf-8"
    )
    (arch_dir / "spec.ttl").write_text("", encoding="utf-8")
    conn = db.connect(repo)
    scan.scan(conn, repo)
    publish.write_pages(conn, repo, tmp_path)
    sidebar = (tmp_path / "_Sidebar.md").read_text(encoding="utf-8")

    before_reference, _, after_reference = sidebar.partition("**Reference**")
    assert "[Architecture](Architecture)" not in before_reference

    ontology_index = after_reference.index("[Ontology](Ontology)")
    architecture_index = after_reference.index("[Architecture](Architecture)")
    assert ontology_index < architecture_index


def test_write_pages_writes_lf_line_endings_on_every_platform(repo, tmp_path):
    """The wiki is a git repo; alternating CRLF (Windows) and LF (CI) publishes would rewrite
    every line of every page on every run."""
    conn = db.connect(repo)
    scan.scan(conn, repo)
    written = publish.write_pages(conn, repo, tmp_path)
    assert written
    for name in written:
        assert b"\r" not in (tmp_path / name).read_bytes()


def test_the_ontology_page_comes_from_its_readme(repo, tmp_path):
    conn = db.connect(repo)
    scan.scan(conn, repo)
    publish.write_pages(conn, repo, tmp_path)
    assert "The vocabulary." in (tmp_path / "Ontology.md").read_text(encoding="utf-8")
