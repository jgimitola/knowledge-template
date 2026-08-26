# Task 4 report: Make the five vocabulary-aware lint checks configurable

**Status: DONE**

## What I implemented

Working from `C:/Users/jesus/Documents/Proyectos/knowledge-template`, per the brief, on top
of Task 3's mechanical `vocab` threading (already in place before I started).

- `src/knowledge/lint.py`:
  - Deleted the module-level `FIELD_NAME` regex (the `from knowledge.graph import APP, MON`
    import was already gone, per Task 3's extension).
  - `restated_rule_comments(g, vocab)`: reads `vocab.checks.rule_class` instead of the
    literal `"Rule"`; returns `None` when `rule_class` is empty.
  - `naming_violations(g, vocab)`: split into its two independently-configurable halves —
    a `field_name_pattern` regex check and an `underscore_reserved` check — each run only
    if configured. Also returns `None` when `field_class` itself is empty, since neither
    half can identify what a "field" is without it (see "Deviation from the brief" below).
  - `ungrounded_literals(paths, vocab, ids)` (renamed from `ungrounded_empty_states`):
    iterates `vocab.checks.verbatim_string_properties` instead of hardcoding `"emptyState"`;
    returns `None` when that tuple is empty.
  - `locally_redeclared_concepts(paths, vocab, ids)`: reads `vocab.checks.concept_class`
    and `vocab.checks.concept_spec` instead of the literals `"Concept"`/`"concepts"`;
    returns `None` when either is empty.
  - `domain_range_violations` was untouched — Task 3 had already replaced its `MON`/`APP`
    checks with `vocab.is_term`/`vocab.qname`, and the brief's Step 3 confirms no further
    change is needed there.
  - `known_terms`, `invented_predicates`, `invented_types` were untouched — they take
    `vocab` already and have no configurable terms to read (they're driven entirely by
    `vocab.is_term`, which is namespace-based, not a check name).

- `src/knowledge/cli.py`:
  - `_check(name, items: Sequence[str] | None, ok_message, strict)`: gained an
    `items is None` branch that prints `skipped (not configured): <name>` and returns
    `False` (never fails the run, and never prints a pass).
  - `cmd_validate`: updated the `ungrounded_empty_states` call site to
    `lint.ungrounded_literals`, and reworded that one check's `name`/`ok_message` from
    "empty-state string(s)"/"every empty state appears..." to "ungrounded literal(s)"/
    "every verbatim string appears..." since the check no longer concerns one specific
    predicate. No other call site changed — `config.vocabulary` was already threaded in by
    Task 3, and `lint.invented_predicates(g, v) + lint.invented_types(g, v)` is unaffected
    since neither of those two ever returns `None`.

- `tests/test_lint.py`: added the four tests from the brief's Step 1, and renamed the three
  existing `ungrounded_empty_states` tests to call `ungrounded_literals`. Per ruling C6, the
  new `test_ungrounded_literals_covers_every_configured_property` requests `write_spec` as a
  fixture argument rather than `from tests.conftest import write_spec`.

- `tests/conftest.py`: `make_config()`'s `Checks()` was empty (`rule_class=""`,
  `field_class=""`, etc.) even though its docstring says "Same example vocabulary as
  KNOWLEDGE_TOML above" — KNOWLEDGE_TOML's `[vocabulary]` table sets all of these. This was
  silently fine before my change because the pre-Task-4 lint functions ignored `vocab.checks`
  and used hardcoded literals. Once the checks read `vocab.checks`, this made
  `restated_rule_comments`/`naming_violations` return `None` for `make_config`'s callers,
  breaking `tests/test_round_trip.py::test_a_spec_can_be_scaffolded_modeled_and_verified`
  (asserts `== []`, not `is None`). I filled in `Checks(...)` to match KNOWLEDGE_TOML's
  values, which fixes the test and makes `make_config` actually deliver what its docstring
  promises. `tests/test_deps.py` and `tests/test_lifecycle.py` also use `make_config` but
  never touch `vocab.checks`, so they are unaffected (confirmed by the full suite run below).

## Deviation from the brief — and why

The brief's literal `naming_violations` code only returns `None` when
`field_name_pattern` is empty **and** `underscore_reserved` is `False`. But the brief's own
`test_unconfigured_checks_return_none_rather_than_passing` (Step 1) sets `field_class=""`
while leaving `field_name_pattern`/`underscore_reserved` at their configured (truthy)
defaults, and asserts `naming_violations(g, vocab) is None`. Under the brief's literal
implementation this returns `[]`, not `None` — I ran it and confirmed the failure (see RED
evidence below).

I resolved this by adding `if not checks.field_class: return None` ahead of the
pattern/underscore branch. This is not scope creep on top of the brief's intent: both halves
of `naming_violations` need `field_class` to know what "a field" is — the pattern check has
nothing to iterate without it, and the underscore check has nothing to exempt without it —
so an unset `field_class` makes the whole check meaningless, not half-meaningful. This is a
one-line addition, keeps the two-halves split the task asked for, and makes the brief's own
test pass. I did not weaken or skip the test to work around this.

## TDD evidence

### RED

Command: `uv run pytest tests/test_lint.py -v` (after adding the Step-1 tests and renaming
the three `ungrounded_empty_states` tests, before touching `lint.py`/`cli.py`):

```
FAILED tests/test_lint.py::test_ungrounded_literals_flags_a_string_no_sentence_states
FAILED tests/test_lint.py::test_ungrounded_literals_accepts_a_string_the_prose_states
FAILED tests/test_lint.py::test_ungrounded_literals_accepts_a_string_the_prose_hard_wraps
FAILED tests/test_lint.py::test_configured_checks_run - AttributeError: modul...
FAILED tests/test_lint.py::test_unconfigured_checks_return_none_rather_than_passing
FAILED tests/test_lint.py::test_underscore_rule_is_separable_from_the_field_pattern
FAILED tests/test_lint.py::test_ungrounded_literals_covers_every_configured_property
======================== 7 failed, 15 passed in 0.42s =========================
```

Why this is the expected failure: the three renamed tests fail because
`lint.ungrounded_literals` doesn't exist yet (only `ungrounded_empty_states` does); the four
new tests fail because `lint` doesn't have `ungrounded_literals` at all yet
(`AttributeError`), and the checks that do exist (`restated_rule_comments`,
`naming_violations`) still unconditionally return a list — never `None` — so
`is None` assertions fail with `AssertionError: assert [] is None`. Exactly what the brief's
Step 2 predicts.

After implementing `lint.py`'s five functions (but before the `field_class` fix above), a
second RED surfaced from the brief's own test:

```
FAILED tests/test_lint.py::test_unconfigured_checks_return_none_rather_than_passing
E       AssertionError: assert [] is None
E        +  where [] = <function naming_violations ...>(..., checks=Checks(rule_class='',
concept_class='', concept_spec='concepts', field_class='', field_name_pattern='^[A-Z]...',
underscore_reserved=True, ...))
```

This is the gap described above — resolved by the `field_class` guard.

### GREEN

Command: `uv run pytest tests/test_lint.py tests/test_cli_read.py -v`

```
tests/test_lint.py::test_invented_predicates_finds_an_undeclared_property PASSED
tests/test_lint.py::test_invented_predicates_is_empty_for_a_clean_graph PASSED
tests/test_lint.py::test_invented_types_finds_an_undeclared_class PASSED
tests/test_lint.py::test_restated_rule_comments_flags_a_comment_that_repeats_the_label PASSED
tests/test_lint.py::test_restated_rule_comments_accepts_a_comment_that_explains_why PASSED
tests/test_lint.py::test_restated_rule_comments_flags_a_missing_comment PASSED
tests/test_lint.py::test_naming_violations_accepts_the_documented_field_pattern PASSED
tests/test_lint.py::test_naming_violations_flags_a_field_missing_its_owner_prefix PASSED
tests/test_lint.py::test_naming_violations_flags_an_underscore_outside_a_field PASSED
tests/test_lint.py::test_locally_redeclared_concepts_flags_a_concept_declared_outside_its_home_spec PASSED
tests/test_lint.py::test_locally_redeclared_concepts_is_empty_when_concepts_lives_only_on_its_own_page PASSED
tests/test_lint.py::test_domain_range_violations_flags_a_field_carrying_an_interface_element_predicate PASSED
tests/test_lint.py::test_domain_range_violations_flags_an_object_of_the_wrong_type PASSED
tests/test_lint.py::test_domain_range_violations_accepts_conformant_individuals_across_the_subclass_closure PASSED
tests/test_lint.py::test_domain_range_violations_ignores_a_literal_range PASSED
tests/test_lint.py::test_ungrounded_literals_flags_a_string_no_sentence_states PASSED
tests/test_lint.py::test_ungrounded_literals_accepts_a_string_the_prose_states PASSED
tests/test_lint.py::test_ungrounded_literals_accepts_a_string_the_prose_hard_wraps PASSED
tests/test_lint.py::test_configured_checks_run PASSED
tests/test_lint.py::test_unconfigured_checks_return_none_rather_than_passing PASSED
tests/test_lint.py::test_underscore_rule_is_separable_from_the_field_pattern PASSED
tests/test_lint.py::test_ungrounded_literals_covers_every_configured_property PASSED
tests/test_cli_read.py [... all 15 PASSED ...]
============================= 37 passed in 1.02s ==============================
```

Full suite: `uv run pytest -q`

```
........................................................................ [ 43%]
........................................................................ [ 87%]
....................                                                     [100%]
164 passed in 7.84s
```

164 = the 160-test baseline + the 4 new tests added in Step 1 (the three renamed tests are
not new, they replace existing ones 1:1). No warnings, no skips, no errors.

Confirmed the `make_config` fix caused no other regressions by diffing before/after: without
it, exactly one test fails (`test_round_trip.py::test_a_spec_can_be_scaffolded_modeled_and_verified`,
163 passed / 1 failed); with it, all 164 pass. `tests/test_deps.py` and
`tests/test_lifecycle.py`, the other two `make_config` callers, pass identically either way
since neither touches `vocab.checks`.

## Manual end-to-end demonstration of "skipped"

The repository's own root `knowledge.toml` is the shipped template
(`[template] unconfigured = true`), with `concept_class`, `field_class`, and
`verbatim_string_properties` deliberately empty — but it has no `ontology/ontology.ttl` yet,
so `knowledge validate` can't run against it directly. I built a throwaway repo in `/tmp`
(now deleted) using the same shape as the test fixtures, with `concept_class=""`,
`field_class=""`, `field_name_pattern=""`, `underscore_reserved=false`,
`verbatim_string_properties=[]`, and ran the real CLI end to end:

```
$ uv run knowledge scan
added 2, moved 0, unchanged 0, missing 0, demoted 0
  +  assets
  +  concepts

$ uv run knowledge validate --strict
2 spec(s)
parsed OK: 11 triples
no dangling references
all internal links resolve
no invented ontology terms
every rule's comment says more than its label
skipped (not configured): naming violation(s)
skipped (not configured): concept(s) redeclared locally instead of referenced
every predicate stays inside its declared domain and range
skipped (not configured): ungrounded literal(s) no prose states
$ echo exit=$?
exit=0
```

Confirms: a skipped check never prints a pass message, is visually distinct
("skipped (not configured): ..."), and — correctly — never fails `--strict` (exit 0), since
"not configured" and "checked and clean" both return `False` from `_check` but are printed
differently. `rule_class="Rule"` stayed configured in this demo repo, and its check printed
the ordinary pass message ("every rule's comment says more than its label"), showing
configured and unconfigured checks sit side by side correctly in the same run.

## Files changed

- `src/knowledge/lint.py`
- `src/knowledge/cli.py`
- `tests/test_lint.py`
- `tests/conftest.py`

## Self-review

- Diffed every change against the brief's Step 3/4 code blocks: `lint.py` and the `_check`
  function match verbatim except the one addition described above (`field_class` guard in
  `naming_violations`).
- No stray renames, no unrelated formatting churn — `git diff --stat` shows only the four
  files above.
- Checked for trailing whitespace (`grep -nP '[ \t]+$'` over the diff hunks — none) and CRLF
  (`grep -qU $'\r'` over each changed file — none; all LF).
- No lint/ruff config exists in this project (only `pytest` + `pre-commit`'s `prettier` for
  markdown/yaml, which doesn't apply to `.py` files), so `npm run validate`-equivalent here
  is the pytest suite, run clean above.
- Confirmed the `cli._check`/`invented_predicates + invented_types` concatenation concern
  from the task instructions is a non-issue: neither `invented_predicates` nor
  `invented_types` returns `Optional` (both are declared `-> list[str]` and never guard on
  an empty `vocab.checks` field — they key off `vocab.is_term`, a namespace test, not a
  named check), so the `+` always operates on two real lists.
- Confirmed `make_config`'s existing two other callers (`test_deps.py`, `test_lifecycle.py`)
  don't read `vocab.checks`, so filling it in is safe for them.

## Concerns

- The `naming_violations` `field_class` guard is a real (small) deviation from the brief's
  literal code, made to satisfy the brief's own test. Flagging it explicitly per the task
  instructions rather than treating it as a silent fix.
- `cmd_validate`'s check name/`ok_message` text for the renamed check changed
  ("empty-state string(s)..." → "ungrounded literal(s)..."). No test pins that exact string
  (grepped for it — none), but it's a user-visible CLI text change worth knowing about.

## Fix round: Add docstring documentation to three configurable checks

**Status: DONE**

A code review found that three of the four `None`-returning functions lacked proper
documentation of the sentinel value. Only `restated_rule_comments` explained it. Added
equivalent paragraphs to `naming_violations`, `ungrounded_literals`, and
`locally_redeclared_concepts`, matching the voice and reasoning level of the existing
docstring.

### Changes made

#### `naming_violations` (lines 75-79)

```python
None when no field class is configured, or when a field class is configured but
neither pattern nor underscore reservation is set. An empty field class makes the
check meaningless: without it, the underscore half has nothing to exempt, so it
would flag every field as a violation. The second condition leaves no checks active
to run, which is different from having checks that all pass.
```

Explains the two independent reasons to return `None`, and provides the reasoning for
the first case: why an unconfigured field class invalidates the underscore check.

#### `ungrounded_literals` (lines 191-193)

```python
None when verbatim_string_properties is empty: a project with no verbatim predicates
configured has nothing for this check to be about, which is different from having
predicates that all appear in the prose.
```

Explains when the check becomes meaningless: no configured properties to check.

#### `locally_redeclared_concepts` (lines 224-226)

```python
None when concept_class or concept_spec is empty: the check cannot identify what a
concept is, or enforce where concepts belong, so it has nothing to check, which is
different from finding concepts that all respect the rule.
```

Explains when either of the two configuration values is empty, why the check cannot run.

### Test results

Command: `uv run pytest tests/test_lint.py -v`
- 22 passed in 0.55s (unchanged; docstrings do not affect test execution)

Command: `uv run pytest -q`
- 164 passed in 7.54s (unchanged; no regressions)

All tests passed without warnings, skips, or errors.

### Commit

Command: `git commit -m "docs: explain the None sentinel in each configurable check"`

```
[main cb02250] docs: explain the None sentinel in each configurable check
 1 file changed, 16 insertions(+), 1 deletion(-)
```

Commit SHA: `cb02250`

### Concerns

None. Docstrings only; no behavior change. Baseline 164 tests still passing.
