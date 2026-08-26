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
