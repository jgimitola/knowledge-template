### Task 9: `knowledge init`

**Files:**

- Create: `src/knowledge/init.py`
- Modify: `src/knowledge/cli.py` (`cmd_init`, parser)
- Test: `tests/test_init.py`

**Interfaces:**

- Consumes: `config.load_config` from Task 2.
- Produces:
  - `init.Answers(project_name, base_iri, prefix, instance_prefix, code_repo, publish_target, dependency_preset)`
  - `init.slugify(name: str) -> str`
  - `init.substitute(root: Path, values: dict[str, str]) -> list[str]` (returns the paths it rewrote)
  - `init.remaining_placeholders(root: Path) -> list[str]`
  - `init.run(root: Path, answers: Answers) -> list[str]`
  - `init.MANIFEST: tuple[str, ...]`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_init.py`:

```python
import pytest

from knowledge import init
from knowledge.config import load_config


def build_template(tmp_path):
    """A miniature of the shipped template: placeholders in every manifest file."""
    (tmp_path / "knowledge.toml").write_text(
        "[template]\nunconfigured = true\n\n"
        '[project]\nname = "{{PROJECT_NAME}}"\n\n'
        "[vocabulary]\n"
        'ontology_file = "ontology.ttl"\n'
        'namespace = "{{BASE_IRI}}ontology#"\n'
        'instances = "{{BASE_IRI}}id/"\n'
        'prefix = "{{PREFIX}}"\n'
        'instance_prefix = "app"\n\n'
        '[repo]\ncode_repo = "{{CODE_REPO}}"\n',
        encoding="utf-8",
    )
    ontology = tmp_path / "ontology"
    ontology.mkdir()
    (ontology / "ontology.ttl").write_text(
        "@prefix {{PREFIX}}: <{{BASE_IRI}}ontology#> .\n"
        "@prefix app: <{{BASE_IRI}}id/> .\n",
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
    assert init.slugify("Acme Widgets, Inc.") == "acmewidgets"
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_init.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'knowledge.init'`.

- [ ] **Step 3: Write `src/knowledge/init.py`**

```python
"""`knowledge init` — bind the template to one project, once.

The template ships with {{PLACEHOLDER}} tokens rather than a working configuration, so a
half-configured repository is impossible to mistake for a configured one: every placeholder
that survives is visible, and `--check` fails on it.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from knowledge.config import load_config

PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")

# Files that carry placeholders. Everything else in the template is already generic.
MANIFEST = (
    "knowledge.toml",
    "ontology/README.md",
    "docs/README.template.md",
    ".claude/agents/interviewer.md",
    ".claude/agents/writer.md",
    "integrations/code-repo/.claude/skills/knowledge-base/SKILL.md",
)

# Directories a placeholder sweep must not walk into.
SKIPPED_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules", ".worktrees"}
TEXT_SUFFIXES = {".md", ".toml", ".ttl", ".yaml", ".yml", ".py", ".json", ".txt", ""}


@dataclass(frozen=True)
class Answers:
    project_name: str
    base_iri: str
    prefix: str
    instance_prefix: str
    code_repo: str
    publish_target: str
    dependency_preset: str


def slugify(name: str) -> str:
    """A prefix has to be a legal Turtle prefix, so anything that is not a letter or a
    digit goes, and what is left is lowercased."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _values(answers: Answers, ontology_file: str) -> dict[str, str]:
    base = answers.base_iri if answers.base_iri.endswith("/") else answers.base_iri + "/"
    return {
        "PROJECT_NAME": answers.project_name,
        "BASE_IRI": base,
        "PREFIX": answers.prefix,
        "INSTANCE_PREFIX": answers.instance_prefix,
        "CODE_REPO": answers.code_repo,
        "ONTOLOGY_FILE": ontology_file,
        "PUBLISH_TARGET": answers.publish_target,
    }


def substitute(root: Path, values: dict[str, str], manifest=MANIFEST) -> list[str]:
    """Rewrite every {{TOKEN}} in the manifest. A token with no value is left alone, so it
    shows up in `remaining_placeholders` rather than becoming an empty string silently."""
    rewritten: list[str] = []
    for relative in manifest:
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        new = PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), text)
        if new != text:
            path.write_text(new, encoding="utf-8", newline="\n")
            rewritten.append(relative)
    return rewritten


def remaining_placeholders(root: Path) -> list[str]:
    """"<path>: {{TOKEN}}" for every placeholder still in the tree."""
    found: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        if SKIPPED_DIRS & set(path.relative_to(root).parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for match in PLACEHOLDER.finditer(text):
            found.append(f"{path.relative_to(root).as_posix()}: {match.group(0)}")
    return found


def _reset_metadata(root: Path) -> None:
    """An empty database dumped fresh, so the generated repository starts with no history
    of specs that are no longer there."""
    from knowledge import db
    from knowledge.paths import get_paths

    paths = get_paths(root, load_config(root).vocabulary.ontology_file)
    paths.db.unlink(missing_ok=True)
    conn = db.connect(paths)
    db.save(conn, paths)
    conn.close()
    paths.db.unlink(missing_ok=True)


def run(root: Path, answers: Answers) -> list[str]:
    """Bind the template to one project. Returns the files it rewrote."""
    config = load_config(root)
    if not config.unconfigured:
        raise RuntimeError(
            f"{root} is already configured — remove the [template] table from"
            " knowledge.toml to re-run init"
        )

    ontology_file = config.vocabulary.ontology_file
    values = _values(answers, ontology_file)

    rewritten = substitute(root, values, MANIFEST + (f"ontology/{ontology_file}",))

    text = (root / "knowledge.toml").read_text(encoding="utf-8")
    text = re.sub(r"\[template\]\nunconfigured = true\n\n?", "", text, count=1)
    if answers.publish_target != "none":
        text = text.replace('target  = "none"', f'target  = "{answers.publish_target}"')
    if answers.dependency_preset != "none":
        preset = (root / "presets" / f"{answers.dependency_preset}.toml").read_text(
            encoding="utf-8"
        )
        block = preset.split("[dependencies]", 1)[1]
        text = re.sub(r"\[dependencies\].*?(?=\n\[)", "[dependencies]" + block, text, flags=re.S)
    (root / "knowledge.toml").write_text(text, encoding="utf-8", newline="\n")

    shutil.rmtree(root / "specs" / "example", ignore_errors=True)
    _reset_metadata(root)

    template_readme = root / "docs" / "README.template.md"
    if template_readme.is_file():
        shutil.move(str(template_readme), str(root / "README.md"))
        rewritten.append("README.md")

    return sorted(set(rewritten))
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_init.py -v`
Expected: PASS.

- [ ] **Step 5: Add the `init` subcommand**

In `cli.py`:

```python
def _prompt(question: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{question}{suffix}: ").strip()
    return answer or default


def cmd_init(args: argparse.Namespace) -> int:
    from knowledge import init
    root = find_root()

    if args.check:
        remaining = init.remaining_placeholders(root)
        if remaining:
            print(f"{len(remaining)} placeholder(s) not substituted:")
            for entry in remaining:
                print("  -", entry)
            return 1
        print("no placeholders remain")
        return 0

    name = args.name or _prompt("Project name")
    if not name:
        print("a project name is required", file=sys.stderr)
        return 1
    base_iri = args.base_iri or _prompt("Base IRI", f"https://{init.slugify(name)}.example/")
    prefix = args.prefix or _prompt("Turtle prefix", init.slugify(name))
    answers = init.Answers(
        project_name=name,
        base_iri=base_iri,
        prefix=prefix,
        instance_prefix=args.instance_prefix or _prompt("Instance prefix", "app"),
        code_repo=args.code_repo if args.code_repo is not None
        else _prompt("Code repository path (blank to disable staleness)"),
        publish_target=args.publish_target or _prompt(
            "Publish target (none/directory/github-wiki)", "none"
        ),
        dependency_preset=args.dependency_preset or _prompt(
            "Dependency preset (none/nextjs)", "none"
        ),
    )

    rewritten = init.run(root, answers)
    print(f"configured {name}: rewrote {len(rewritten)} file(s)")
    for relative in rewritten:
        print("  -", relative)

    skill = root / "integrations" / "code-repo" / ".claude" / "skills" / "knowledge-base"
    if args.install_skill and answers.code_repo:
        destination = (root / answers.code_repo).resolve() / ".claude" / "skills" / "knowledge-base"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(skill, destination, dirs_exist_ok=True)
        print(f"installed the reading skill into {destination}")
    elif skill.is_dir():
        print(f"\nthe reading skill is at {skill}")
        print("copy it into your code repository's .claude/skills/, or re-run with --install-skill")

    remaining = init.remaining_placeholders(root)
    if remaining:
        print(f"\nwarning: {len(remaining)} placeholder(s) remain; run `knowledge init --check`")
    return 0
```

Register it, and note that it must not call `open_repo` — the repository is not yet configured:

```python
    init_p = sub.add_parser("init", help="bind this template to one project")
    init_p.add_argument("--check", action="store_true",
                        help="report unsubstituted placeholders and exit non-zero")
    init_p.add_argument("--name")
    init_p.add_argument("--base-iri")
    init_p.add_argument("--prefix")
    init_p.add_argument("--instance-prefix")
    init_p.add_argument("--code-repo")
    init_p.add_argument("--publish-target", choices=["none", "directory", "github-wiki"])
    init_p.add_argument("--dependency-preset", choices=["none", "nextjs"])
    init_p.add_argument("--install-skill", action="store_true",
                        help="copy the reading skill into the code repository")
    init_p.set_defaults(handler=cmd_init)
```

Add `import shutil` to `cli.py`.

- [ ] **Step 6: Run the whole suite**

Run: `uv run pytest -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: add knowledge init"
```

---

