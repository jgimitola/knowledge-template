### Task 1: Bootstrap the template repository

Create the new repository with the files that need no changes, and prove the copied test suite passes before anything is edited. Nothing monicords-specific in content is copied — but the _code_ still contains monicords constants at this point, and that is expected: Tasks 2–9 remove them.

**Files:**

- Create: `../knowledge-template/` (git repository)
- Copy verbatim from `../monicords-knowledge/`: `src/knowledge/*.py`, `tests/*.py`, `uv.lock`, `.gitignore`, `.pre-commit-config.yaml`, `.prettierrc.mjs`, `.prettierignore`, `.gitattributes`
- Create: `../knowledge-template/pyproject.toml`
- Create: `../knowledge-template/knowledge.toml` (temporary, replaced in Task 2)
- Create: `../knowledge-template/ontology/VERSION`

**Interfaces:**

- Consumes: nothing.
- Produces: a repository at `../knowledge-template` where `uv run pytest` passes, and where `uv run knowledge --help` runs.

- [ ] **Step 1: Create the repository and copy the files that need no editing**

Run from `../monicords-knowledge`:

```bash
mkdir -p ../knowledge-template
cd ../knowledge-template
git init -b main
mkdir -p src/knowledge tests ontology
cp ../monicords-knowledge/src/knowledge/*.py src/knowledge/
cp ../monicords-knowledge/tests/*.py tests/
cp ../monicords-knowledge/uv.lock .
cp ../monicords-knowledge/.gitignore .
cp ../monicords-knowledge/.pre-commit-config.yaml .
cp ../monicords-knowledge/.prettierrc.mjs .
cp ../monicords-knowledge/.prettierignore .
cp ../monicords-knowledge/.gitattributes .
printf '1.0.0\n' > ontology/VERSION
```

Do **not** copy `scripts/`, `specs/`, `.metadata/`, `.github/`, `docs/`, `README.md`, `knowledge.toml`, or `.claude/`.

- [ ] **Step 2: Write `pyproject.toml`**

Create `../knowledge-template/pyproject.toml`:

```toml
[project]
name = "knowledge"
version = "0.1.0"
description = "Authoring, tracking and publishing for a knowledge base"
requires-python = ">=3.13"
dependencies = [
    "rdflib==7.6.0",
]

[project.scripts]
knowledge = "knowledge.cli:main"

[dependency-groups]
dev = [
    "pre-commit==4.4.0",
    "pytest==8.3.4",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/knowledge"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 3: Write a temporary `knowledge.toml` so `paths.find_root` works**

Create `../knowledge-template/knowledge.toml`:

```toml
[repo]
code_repo = ""

[wiki]
remote = ""
```

- [ ] **Step 4: Run the copied test suite**

Run: `cd ../knowledge-template && uv sync --all-extras --dev && uv run pytest -v`
Expected: PASS. Every test builds its own fixture repository in `tmp_path`, so none of them needs the files that were not copied.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: seed the template from monicords-knowledge's tooling"
```

---

