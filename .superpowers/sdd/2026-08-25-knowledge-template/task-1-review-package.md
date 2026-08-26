# Task 1 review package

BASE: 4b825dc642cb6eb9a060e54bf8d69288fbee4904 (empty tree — new repository)
HEAD: 2976990

## Commits
```
2976990 chore: drop the monicords migration scripts and their test
f187a4a chore: remove pytest output artifact
21b38af chore: seed the template from monicords-knowledge's tooling
```

## Tracked files at HEAD
```
.gitattributes
.gitignore
.pre-commit-config.yaml
.prettierignore
.prettierrc.mjs
knowledge.toml
ontology/VERSION
pyproject.toml
src/knowledge/__init__.py
src/knowledge/cli.py
src/knowledge/config.py
src/knowledge/contradictions.py
src/knowledge/db.py
src/knowledge/deps.py
src/knowledge/gitcmd.py
src/knowledge/graph.py
src/knowledge/lifecycle.py
src/knowledge/lint.py
src/knowledge/paths.py
src/knowledge/publish.py
src/knowledge/scan.py
tests/conftest.py
tests/test_cli_deps.py
tests/test_cli_publish.py
tests/test_cli_read.py
tests/test_cli_write.py
tests/test_contradictions.py
tests/test_db.py
tests/test_deps.py
tests/test_gitcmd.py
tests/test_graph.py
tests/test_lifecycle.py
tests/test_lint.py
tests/test_paths.py
tests/test_publish.py
tests/test_round_trip.py
tests/test_scan.py
uv.lock
```

## Byte-identity check: copied files vs their monicords-knowledge sources

Each line: OK = identical to source, DIFFERS = modified, MISSING = absent from source.
```
OK        .gitattributes
OK        .gitignore
OK        .pre-commit-config.yaml
OK        .prettierignore
OK        .prettierrc.mjs
AUTHORED  knowledge.toml (new file, content below)
AUTHORED  ontology/VERSION (new file, content below)
AUTHORED  pyproject.toml (new file, content below)
OK        src/knowledge/__init__.py
OK        src/knowledge/cli.py
OK        src/knowledge/config.py
OK        src/knowledge/contradictions.py
OK        src/knowledge/db.py
OK        src/knowledge/deps.py
OK        src/knowledge/gitcmd.py
OK        src/knowledge/graph.py
OK        src/knowledge/lifecycle.py
OK        src/knowledge/lint.py
OK        src/knowledge/paths.py
OK        src/knowledge/publish.py
OK        src/knowledge/scan.py
OK        tests/conftest.py
OK        tests/test_cli_deps.py
OK        tests/test_cli_publish.py
OK        tests/test_cli_read.py
OK        tests/test_cli_write.py
OK        tests/test_contradictions.py
OK        tests/test_db.py
OK        tests/test_deps.py
OK        tests/test_gitcmd.py
OK        tests/test_graph.py
OK        tests/test_lifecycle.py
OK        tests/test_lint.py
OK        tests/test_paths.py
OK        tests/test_publish.py
OK        tests/test_round_trip.py
OK        tests/test_scan.py
OK        uv.lock
```

## Files present in monicords-knowledge but NOT copied (intended exclusions)
```
.claude/agents/interviewer.md
.claude/agents/writer.md
.claude/settings.json
.github/workflows/ci.yml
.github/workflows/publish.yml
.github/workflows/stale.yml
.metadata/dump.sql
.python-version
README.md
docs/superpowers/plans/2026-08-23-knowledge-agents.md
docs/superpowers/plans/2026-08-25-knowledge-template.md
docs/superpowers/specs/2026-08-22-knowledge-agents-design.md
docs/superpowers/specs/2026-08-25-knowledge-template-design.md
ontology/README.md
ontology/monicords.ttl
scripts/__init__.py
scripts/extract_wiki.py
scripts/seed_statuses.py
specs/architecture/spec.md
specs/architecture/spec.ttl
specs/assets/spec.md
specs/assets/spec.ttl
specs/concepts/spec.md
specs/concepts/spec.ttl
specs/expenses-calendar/spec.md
specs/expenses-calendar/spec.ttl
specs/expenses-log/spec.md
specs/expenses-log/spec.ttl
specs/expenses-plan/spec.md
specs/expenses-plan/spec.ttl
specs/expenses/spec.md
specs/expenses/spec.ttl
specs/home/spec.md
specs/home/spec.ttl
specs/incomes-detail/spec.md
specs/incomes-detail/spec.ttl
specs/incomes/spec.md
specs/incomes/spec.ttl
specs/loans-out/spec.md
specs/loans-out/spec.ttl
specs/onboarding-landing/spec.md
specs/onboarding-landing/spec.ttl
specs/onboarding-welcome/spec.md
specs/onboarding-welcome/spec.ttl
specs/onboarding-workspace/spec.md
specs/onboarding-workspace/spec.ttl
specs/onboarding/spec.md
specs/onboarding/spec.ttl
specs/profile-account/spec.md
specs/profile-account/spec.ttl
specs/profile-categories/spec.md
specs/profile-categories/spec.ttl
specs/profile-password/spec.md
specs/profile-password/spec.ttl
specs/profile-settings/spec.md
specs/profile-settings/spec.ttl
specs/profile-workspaces/spec.md
specs/profile-workspaces/spec.ttl
specs/profile/spec.md
specs/profile/spec.ttl
tests/test_extraction.py
```

## Newly authored file contents

### pyproject.toml
```
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

### knowledge.toml
```
[repo]
code_repo = ""

[wiki]
remote = ""
```

### ontology/VERSION
```
1.0.0
```

## Line endings and trailing whitespace
```
CRLF files (should be none):
0
files with trailing whitespace (should be none):
```

## Test result claimed by implementer
```
........................................................................ [ 97%]
...                                                                      [100%]
147 passed in 7.62s
```
