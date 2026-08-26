# Task 3 report: Move the ontology filename and the graph namespaces onto the config

**Status: DONE** (escalated mid-task, resumed and completed per the coordinator's ruling —
see "Scope extension" below).

## What I implemented

Per the brief, plus the coordinator's ruling extending the same threading into
`contradictions.py`, `lint.py` and `deps.py`:

- `src/knowledge/paths.py`: `get_paths(start=None, ontology_file="ontology.ttl")` — the
  ontology filename is now a parameter instead of the literal `"monicords.ttl"`.
- `src/knowledge/graph.py`: deleted `MON`, `APP`, `SPARQL_PREFIXES`, `SANITY_QUERIES`.
  `load_graph`, `load_spec_graph`, `run_query`, `dangling_terms` all take a
  `vocab: Vocabulary` and use `vocab.prefix`/`vocab.namespace`/`vocab.instance_prefix`/
  `vocab.instances`/`vocab.sparql_prefixes`/`vocab.is_term`/`vocab.is_instance` in place of
  the deleted constants. Added `graph.surveys(config) -> list[tuple[str, str]]`. Renamed
  `wiki_page_name` to `page_name`.
- `src/knowledge/scan.py`, `src/knowledge/publish.py`: renamed the `wiki_page_name` import
  and its one call site each to `page_name`. Nothing else in `publish.py` touched (Task 7
  owns the rest, per the brief's own decision #3).
- `src/knowledge/cli.py`: `open_repo` now does `find_root()` → `load_config(root)` →
  `get_paths(root, config.vocabulary.ontology_file)`. `cmd_validate`, `cmd_graph`,
  `cmd_query`, `cmd_describe`, `cmd_ask`, `cmd_contradictions` all thread
  `config.vocabulary` into their `graph.*` (and now `lint.*`/`contradictions.*`) calls.
  `cmd_describe`'s bare-term default is `config.vocabulary.instance_prefix`. `cmd_ask`
  iterates `graph.surveys(config)` and prints a clear message when empty, replacing the
  built-in `SANITY_QUERIES` dict entirely. `cmd_dep` and `cmd_stale` pass
  `config.vocabulary` into `deps.derived_globs`/`deps.uncheckable`. The `"ask"` subparser's
  help text and the top-level `description=` no longer say "monicords" or "built-in".
- `src/knowledge/contradictions.py`: `functional_conflicts(g, vocab)` — `MON + prop`
  becomes `vocab.term(prop)`. `FUNCTIONAL_PROPERTIES` and every other term name unchanged.
- `src/knowledge/lint.py`: `known_terms`, `invented_predicates`, `invented_types`,
  `restated_rule_comments`, `naming_violations`, `domain_range_violations`,
  `ungrounded_empty_states` (kept this name — Task 4 renames it),
  `locally_redeclared_concepts` all take `vocab: Vocabulary`. `MON`/`APP` string-prefix
  checks become `vocab.is_term`/`vocab.is_instance`; hardcoded IRIs become
  `vocab.term("Rule")`/`vocab.term("Field")`/`vocab.term("Concept")`/
  `vocab.term("emptyState")`; the `f"mon:{_local(t)}"` formatter becomes `vocab.qname(t)`.
  `FIELD_NAME` regex and every class/property name are still literal — Task 4 owns making
  them configurable.
- `src/knowledge/deps.py`: `derived_globs(paths, vocab, spec_id)`,
  `spec_globs(conn, paths, vocab, spec_id)`, `uncheckable(conn, paths, vocab)` — matching
  the coordinator's target signatures exactly. `check(conn, paths, config, demote,
  code_repo=None)` is unchanged in shape; it now reads `config.vocabulary` internally and
  passes it to `spec_globs`. The two derived-glob SPARQL strings build their predicate as
  `f"{vocab.prefix}:route"` / `f"{vocab.prefix}:endpoint"` instead of a hardcoded `mon:`.
  `route`/`endpoint` as property *names* stay literal — Task 6 owns configuring those.

## Scope extension (the coordinator's decision, not mine)

Mid-task I found that Step 4's required `vocab` parameter breaks three source files
outside the brief's file list — `contradictions.py` (imports `MON`), `lint.py` (imports
`APP, MON`, calls `load_spec_graph` with the old arity), `deps.py` (calls
`load_spec_graph`/`run_query` with the old arity) — each explicitly owned by a later task
(5, 4, 6) with its own target interface. I stopped and reported this rather than guess,
per the brief's own instruction to do exactly that. The coordinator confirmed the defect,
ruled to extend Task 3 to cover the minimal mechanical threading in all three files (using
each later task's own declared target signature so nothing needs rework), and explicitly
said every term name stays hardcoded — no configurability added. I implemented exactly
that ruling; see the file-by-file list above.

## Tests

TDD evidence — RED then GREEN, both against the full suite:

**RED** (test changes only, source reverted via `git stash push -- src/...`, then popped
back after capturing the run):

```
$ uv run pytest -q
...
49 failed, 111 passed in 8.30s
```

Representative failures, each for the expected reason:
- `test_round_trip.py::test_a_spec_can_be_scaffolded_modeled_and_verified` —
  `TypeError: load_graph() takes from 1 to 2 positional arguments but 3 were given`
- `test_graph.py::test_page_name_round_trips_every_shape` — `AttributeError` (old
  `graph.wiki_page_name` still exists, `graph.page_name` does not)
- `test_graph.py::test_surveys_come_from_the_config` — `AttributeError` (`graph.surveys`
  does not exist)
- `test_graph.py::test_the_graph_parses_and_holds_both_specs`,
  `test_cli_read.py::test_graph_writes_a_turtle_file`, and 8 more — `FileNotFoundError` for
  `ontology/monicords.ttl` (the conftest fixture now writes `ontology/ontology.ttl`, but
  the old `paths.get_paths()` still hardcodes the old filename)
- `test_lint.py::*` (18 tests), `test_contradictions.py::*` (2 tests),
  `test_deps.py::test_derived_globs_come_from_the_specs_own_triples` and 7 more — the
  extended-scope files, failing on the old 1-arg (`lint.*(g)`) / 2-arg
  (`deps.derived_globs(paths, spec_id)`) call shapes now missing `vocab`

**GREEN** (full implementation restored):

```
$ uv run pytest -v
...
============================= 160 passed in 7.66s =============================
```

160 = the 156-test baseline + 4 new tests from the brief's Step 1
(`test_load_graph_binds_the_configured_prefixes`,
`test_run_query_prepends_the_configured_prefixes`,
`test_dangling_terms_uses_the_configured_namespaces`, `test_surveys_come_from_the_config`).
0 skips, no warnings section in the output (pristine).

I also sanity-checked the CLI directly against this repository's own (still-unconfigured,
Task-10-pending) `knowledge.toml`:

```
$ uv run knowledge scan
added 0, moved 0, unchanged 0, missing 0, demoted 0
$ uv run knowledge validate --strict
0 spec(s)

PARSE FAILED: [Errno 2] No such file or directory: '...\ontology\ontology.ttl'
```

This is the expected, unchanged failure mode — `ontology/ontology.ttl` doesn't exist yet
in this repo (Task 10's job); the point of the check was confirming `open_repo`'s new
`find_root()` → `load_config()` → `get_paths(root, config.vocabulary.ontology_file)` chain
runs cleanly and fails with a clean message, not a traceback, exactly as before.

## Final grep sweep

```
$ grep -rn "monicords\|mon:" src/ tests/ --include="*.py"
src/knowledge/publish.py:5:mon:Actor declarations, so it stays an ordinary spec and publishes like any other page.
```

One hit, and it is the one the brief's own decision #3 names as deliberately out of
scope: publish.py's module docstring, left alone because Task 7 owns the rest of that
file. Everything else in `src/` and `tests/` is clean.

Case-insensitive (`grep -rni`) surfaces three more, all capitalized "Monicords" rather
than the lowercase pattern above, and all in files Task 7 owns outright:
`src/knowledge/publish.py:114` (`lines = ["### Monicords", ""]`, the sidebar's hardcoded
top-level header) and two lines in `tests/test_publish.py` (an example spec title used as
fixture data, asserted to *not* appear verbatim in the sidebar — not a brand assertion).
Left untouched: both files are Task 7's (`Modify: publish.py`; `Test: test_publish.py,
test_cli_publish.py`), and decision #3 only authorized the import rename plus its one call
site in `publish.py` for this task.

## Files changed

```
src/knowledge/__init__.py
src/knowledge/cli.py
src/knowledge/contradictions.py
src/knowledge/deps.py
src/knowledge/graph.py
src/knowledge/lint.py
src/knowledge/paths.py
src/knowledge/publish.py
src/knowledge/scan.py
tests/conftest.py
tests/test_cli_read.py
tests/test_contradictions.py
tests/test_deps.py
tests/test_graph.py
tests/test_lint.py
tests/test_paths.py
tests/test_round_trip.py
```

17 files, +471/-373. No file outside this list was touched. `test_cli_deps.py`,
`test_cli_write.py`, `test_cli_publish.py` needed no edits — their
`write_knowledge_toml()` calls now emit a config matching the fixture's `ex:`/
`ontology.ttl` shape because I updated `conftest.py`'s `KNOWLEDGE_TOML` template
alongside `CONFIG_TOML`; confirmed by the full suite pass, not by inspection alone.

## write_spec fixture (ruling C6)

`tests/conftest.py` keeps the plain implementation as `_write_spec` and exposes it as a
`write_spec` fixture, per the pre-agreed ruling. I converted every existing call site that
previously did `from tests.conftest import write_spec` (in `test_graph.py`,
`test_lint.py`, `test_contradictions.py`, and one in-function import in `test_cli_read.py`)
to request `write_spec` as a fixture argument instead — the fixture *is* `_write_spec`
(zero-arg fixture returning the real function), so a bare top-level import would no longer
be directly callable the old way. `test_deps.py` imported `write_spec` but never called it;
dropped the unused import. `test_round_trip.py` never used it.

## Self-review findings

- Behavior-preservation check: for `contradictions.py`, `lint.py`, `deps.py` I diffed each
  function against its pre-Task-3 body and confirmed the only substantive change is the
  namespace-lookup mechanism (`MON`/`APP` string constant → `vocab.term`/`vocab.is_term`/
  `vocab.is_instance`/`vocab.qname`); every literal term name (`"Rule"`, `"Field"`,
  `"Concept"`, `"emptyState"`, `FUNCTIONAL_PROPERTIES`, `"route"`, `"endpoint"`) and every
  existing test's *assertions* are unchanged — only call signatures and the fixture's
  namespace strings changed. No test needed a new/changed assertion beyond the namespace
  swap, confirming the threading didn't change behavior (the condition the coordinator set
  for not needing to stop again).
- `cmd_ask` genuinely changes behavior (built-in `SANITY_QUERIES` → configured `[[ask]]`
  presets), exactly as Step 5 specifies. No existing test exercised the `ask` command
  (confirmed by grep), so this is a real but untested-before/untested-after behavior
  change that the brief explicitly asked for.
- Minor beyond-brief touch-ups, done because they were one-line and directly served the
  "zero `monicords`/`mon:` hits" goal while I was already in these files: `cli.py`'s
  `description=` and the `"ask"` subparser's `help=` text, and `src/knowledge/__init__.py`'s
  module docstring (three files not in the brief's list, but each a single string literal
  with no test coupling).
- Did not touch: `presets/`, `docs/`, anything under `.superpowers/`, or any file whose
  only issue was documentation prose in a module Task 3 doesn't own (e.g. left
  `publish.py`'s `mon:Actor` line and its `SIDEBAR_ORDER`/`### Monicords` sidebar-header
  content untouched — Task 7's).

## Concerns

None outstanding. The one deliberate residual ("mon:Actor" in `publish.py`'s docstring) is
explicitly assigned to Task 7 by the brief itself, not an oversight.
