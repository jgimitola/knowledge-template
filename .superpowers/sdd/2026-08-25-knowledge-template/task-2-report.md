# Task 2 report: Configuration schema and vocabulary object

## What was implemented

Exactly the brief's steps 1–9, working from `C:/Users/jesus/Documents/Proyectos/knowledge-template`:

1. Created `src/knowledge/vocab.py` — `Checks` and `Vocabulary` dataclasses, verbatim from the
   brief (byte-for-byte diffed against the brief's code block after implementation; identical).
2. Replaced `src/knowledge/config.py` — full schema (`Config`, `Survey`, `Dependencies`,
   `Sidebar`, `Publish`, `ConfigError`, `load_config`), verbatim from the brief (also
   byte-for-byte diffed; identical).
3. Threaded `Config` through `cli.open_repo` (`get_paths()` with no argument, per decision #1 —
   this is the Task-3 stepping stone, not anticipating it) and updated all 23 call sites:
   - Commands that don't yet use config: unpacked into `_config`.
   - `cmd_verify`, `cmd_stale`, `cmd_publish`, `cmd_dep`: unpacked into `config` and their
     redundant internal `load_config(paths.root)` calls were deleted, using the threaded value
     instead. The brief's prose named only `cmd_stale`/`cmd_publish` explicitly, but the same
     internal-reload pattern existed in `cmd_verify` and `cmd_dep` too (both assign to a local
     `config` right after `open_repo`); I applied the same "thread it once" treatment to all
     four for consistency, since duplicating the same TOML read on every mutating command
     contradicts the point of Step 6. No behavior change — same values either way.
   - `cmd_publish`'s two `config.wiki_remote` reads became `config.publish.remote` (the new
     schema's field name for the same value).
4. Wrote the full `knowledge.toml` template, copied verbatim from
   `docs/superpowers/specs/2026-08-25-knowledge-template-design.md`'s "Configuration" section
   (the brief pointed at "the spec's Configuration section" without inlining it — found and
   diffed exact-match against that design doc).
5. Fixed everything the schema change broke beyond what Step 8 called out. The brief's Step 8
   only mentioned extending `conftest.repo`'s fixture TOML, but the 2-field → 7-field `Config`
   also broke: direct `Config(code_repo=..., wiki_remote="x")` constructions in
   `test_deps.py`/`test_lifecycle.py`/`test_round_trip.py`, inline `[repo]/[wiki]` TOML text in
   `test_cli_deps.py`/`test_cli_publish.py`/`test_cli_write.py`, and a `test_paths.py` test that
   asserted on `load_config`'s old two-field output. Fixed all of it (see Files changed below);
   the baseline requirement was "the suite must still be green," which these breakages violated
   before the fix.

## TDD evidence

**RED** — `uv run pytest tests/test_vocab.py tests/test_config.py -v`, before `vocab.py`/`config.py`
existed:
```
ERROR collecting tests/test_vocab.py
ModuleNotFoundError: No module named 'knowledge.vocab'
ERROR collecting tests/test_config.py
ImportError: cannot import name 'ConfigError' from 'knowledge.config'
=========================== short test summary info ===========================
ERROR tests/test_vocab.py
ERROR tests/test_config.py
!!!!!!!!!!!!!!!!!!! Interrupted: 2 errors during collection !!!!!!!!!!!!!!!!!!!
```
Expected exactly this per the brief's Step 2 — both modules were new/renamed symbols that did
not exist yet.

**GREEN** — same command, after writing `vocab.py` and `config.py`:
```
tests/test_vocab.py::test_term_and_instance_build_iris PASSED
tests/test_vocab.py::test_is_term_and_is_instance_discriminate PASSED
tests/test_vocab.py::test_qname_shortens_known_namespaces_and_passes_others_through PASSED
tests/test_vocab.py::test_sparql_prefixes_declare_both_project_namespaces_and_the_fixed_ones PASSED
tests/test_config.py::test_full_config_round_trips PASSED
tests/test_config.py::test_minimal_config_defaults_every_optional_section PASSED
tests/test_config.py::test_placeholders_read_as_empty PASSED
tests/test_config.py::test_template_marker_is_reported PASSED
tests/test_config.py::test_missing_required_key_names_it PASSED
tests/test_config.py::test_unknown_publish_target_is_rejected PASSED
============================= 10 passed in 0.20s ==============================
```

**Full suite** — `uv run pytest -v`, after cli.py/knowledge.toml/test fixture updates:
```
============================= 156 passed in 7.57s ==============================
```
No warnings, no skips. Baseline was 147 (per decisions doc); 147 − 1 (removed the now-redundant
`test_config_resolves_the_code_repo_relative_to_the_root` from `test_paths.py`, superseded by
`test_config.py`) + 10 new (`test_vocab.py` ×4, `test_config.py` ×6) = 156. Verified.

## Files changed

- `src/knowledge/vocab.py` — new, verbatim from brief.
- `src/knowledge/config.py` — replaced, verbatim from brief.
- `src/knowledge/cli.py` — `open_repo` signature/body, all 23 call sites, `wiki_remote` →
  `publish.remote`.
- `knowledge.toml` — full template, verbatim from the design doc's Configuration section.
- `tests/test_vocab.py`, `tests/test_config.py` — new, verbatim from brief.
- `tests/conftest.py` — added `write_knowledge_toml()` (full minimal TOML with monicords
  vocabulary values, per decision #2) and `make_config()` helpers; `repo` fixture now uses
  `write_knowledge_toml`.
- `tests/test_cli_deps.py`, `tests/test_cli_publish.py`, `tests/test_cli_write.py` — inline
  `[repo]/[wiki]` TOML text replaced with `write_knowledge_toml(...)` calls.
- `tests/test_deps.py`, `tests/test_lifecycle.py`, `tests/test_round_trip.py` — direct
  `Config(code_repo=..., wiki_remote=...)` constructions replaced with `make_config(...)`.
- `tests/test_paths.py` — removed `test_config_resolves_the_code_repo_relative_to_the_root`
  (tested `load_config`'s old two-field shape; fully superseded by `test_config.py`) and its
  now-unused `load_config` import.

Commit: `feat: read the full project configuration from knowledge.toml`.

## Self-review

- Diffed `vocab.py` and `config.py` against the brief's fenced code blocks with `diff` —
  byte-identical.
- Diffed `knowledge.toml` against the design doc's Configuration section — byte-identical.
- Checked every `open_repo(args)` call site was updated (23 total; grep-verified none missed).
- Checked staged blob content (`git show :<file>`) for CRLF and trailing whitespace — none.
  (The working-tree files show CRLF locally because `core.autocrlf=true` is set globally on
  this machine; `.gitattributes`' `eol=lf` normalizes on `git add`/commit regardless, which
  `db.py`, an untouched tracked file, confirms — 0 CRLF bytes in its blob. The committed content
  is LF-only.)
- No new lint/type-check step is configured for this Python project (pre-commit only runs
  prettier on markdown/yaml at commit time, and pytest/`knowledge validate` at push time), so I
  did not run anything beyond `uv run pytest`.

## Concerns

1. **Scope beyond the brief's explicit Step 8 note.** Step 8 says fixture updates "may need"
   extending in `test_cli_*.py`/`conftest.py`. In practice the schema change broke six more
   test files through direct `Config(...)` construction and inline TOML text that Step 8 didn't
   name. I fixed all of them to keep the suite green per the decisions doc's explicit baseline
   requirement, adding two conftest helpers (`write_knowledge_toml`, `make_config`) that aren't
   in the brief's interface list. This felt like the correct call — the alternative was a
   broken suite — but flagging it since it's a materially larger diff than the brief's steps
   alone describe.
2. **The four-function `load_config` cleanup** (removing it from `cmd_verify`/`cmd_dep` too,
   not just the two the brief named) is a judgment call, explained above. Values are identical
   either way; happy to revert to literal-brief-only (`cmd_stale`/`cmd_publish`) if preferred.
3. **The shipped `knowledge.toml`'s `prefix = "{{PREFIX}}"` will not load via `load_config`**
   once `open_repo` calls it unconditionally (as Step 6 requires): `prefix` is a whole-value
   placeholder, so `_clean` empties it, and `_required` then raises `ConfigError`. This means
   `knowledge scan`/`validate`/etc. run against this repository's own unconfigured
   `knowledge.toml` will fail with a clear `error: knowledge.toml: vocabulary.prefix is
   required` (caught cleanly by `main()`'s `except RuntimeError`, not a traceback) until
   `knowledge init` (Task 9) substitutes it. Not a test failure — nothing in this task's suite
   or in the pre-commit hook (pytest/knowledge-validate are pre-push-only, and this task only
   committed) exercises it — but worth knowing before anyone runs `knowledge` commands or
   `git push` against this working tree before Task 9 lands.

No blockers. Tests are pristine (156 passed, 0 warnings, 0 skips).

## Fix round 1: ship working vocabulary defaults

Coordinator finding: concern (3) above was a real defect — `[vocabulary]`'s `namespace`,
`instances` and `prefix` are machine-parsed (by `load_config` itself, and separately by
rdflib's Turtle parser reading the ontology file's `@prefix` line), so shipping them as
`{{...}}` tokens breaks both `load_config` on the shipped `knowledge.toml` (blocking
`knowledge init` itself, which needs to read the `[template]` marker) and any future ontology
seed (`@prefix {{PREFIX}}:` is not legal Turtle). Ruling: values a machine parses ship as
working defaults; only prose-carried tokens (`{{PROJECT_NAME}}`, `{{CODE_REPO}}`) stay as
placeholders.

### What changed

`knowledge.toml`'s `[vocabulary]` block: `namespace`, `instances`, `prefix` changed from
`{{BASE_IRI}}ontology#` / `{{BASE_IRI}}id/` / `{{PREFIX}}` to working defaults
`https://example.com/ontology#` / `https://example.com/id/` / `ex`. Added a comment above the
block explaining these three are parsed rather than read, so they ship working and `knowledge
init` rewrites them in place, and that `[template]` is what actually marks the repo
unconfigured. Everything else in the file is untouched — `{{PROJECT_NAME}}` in `[project]` and
`[publish.sidebar]`, `{{CODE_REPO}}` in `[repo]`, `[template]`, the check keys, `[[ask]]`,
`[dependencies]`, `[publish]`.

### Load check

```
$ uv run python -c "from pathlib import Path; from knowledge.config import load_config; c = load_config(Path('.')); print(c.vocabulary.prefix, c.vocabulary.namespace, c.unconfigured)"
ex https://example.com/ontology# True
```
Matches the expected output exactly.

### Tests

```
$ uv run pytest tests/test_config.py tests/test_vocab.py -v
============================= 10 passed in 0.05s ==============================

$ uv run pytest -v
============================= 156 passed in 7.61s ==============================
```
No warnings, no skips — unchanged from before the fix (this change only touches the shipped
`knowledge.toml`, which no test in the suite loads directly).

Commit: `901c7b8` — `fix: ship working vocabulary defaults so the template loads before init`
