import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.run(
        [sys.executable, "-m", "knowledge.cli", *args],
        cwd=ROOT, capture_output=True, text=True,
    )


def test_the_shipped_template_validates_as_it_stands():
    assert run("scan").returncode == 0
    result = run("validate", "--strict")
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_shipped_template_still_has_its_placeholders():
    """`init --check` must FAIL here — the template is the one repository where
    placeholders are correct. A generated repository asserts the opposite."""
    assert run("init", "--check").returncode == 1


def test_the_example_ontology_is_not_loaded():
    from knowledge.graph import turtle_source
    from knowledge.paths import get_paths
    paths = get_paths(ROOT, "ontology.ttl")
    assert "webapp" not in turtle_source(paths, ["example"])
    assert "Module" not in turtle_source(paths, ["example"])


AGENT_FILES = (
    ".claude/agents/interviewer.md",
    ".claude/agents/writer.md",
    "integrations/code-repo/.claude/skills/knowledge-base/SKILL.md",
)


def test_the_agents_name_no_project():
    for relative in AGENT_FILES:
        text = (ROOT / relative).read_text(encoding="utf-8").lower()
        assert "monicords" not in text, relative
        assert "app:workspace" not in text, relative


def test_the_agents_are_all_in_the_init_manifest():
    from knowledge.init import MANIFEST
    for relative in AGENT_FILES:
        assert relative in MANIFEST, relative


DOCS = (
    "README.md",
    "LICENSE",
    "docs/GUIDE.md",
    "docs/README.template.md",
    "docs/recipes/github-actions.md",
    "docs/recipes/github-wiki-publishing.md",
    "docs/recipes/nextjs-dependencies.md",
)


def test_every_document_exists_and_names_no_project():
    for relative in DOCS:
        path = ROOT / relative
        assert path.is_file(), relative
        if relative == "LICENSE":
            continue
        assert "monicords" not in path.read_text(encoding="utf-8").lower(), relative


def test_the_guide_documents_installing_the_hooks():
    text = (ROOT / "docs" / "GUIDE.md").read_text(encoding="utf-8")
    assert "pre-commit install --hook-type pre-commit --hook-type pre-push" in text
