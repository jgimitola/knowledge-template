# Task 5 Report: Configure the functional-property list

## What was implemented

Moved `functional_conflicts`'s list of single-valued properties out of the module-level
`FUNCTIONAL_PROPERTIES` constant in `src/knowledge/contradictions.py` and into
`vocab.checks.functional_properties`, which `knowledge.toml`'s `[vocabulary]`
`functional_properties` key already populated (per the C13 `vocab` plumbing already in
place before this task started).

- `functional_conflicts(g, vocab)` now reads `vocab.checks.functional_properties`. When
  empty, it returns `None` — a project with no functional properties configured has
  nothing to check, which is different from checking and finding nothing. The docstring
  documents this explicitly, following the house style set by
  `lint.restated_rule_comments`'s docstring (nothing-to-check vs. nothing-found).
- `cmd_contradictions` in `src/knowledge/cli.py` now has three reporting branches:
  - `functional_conflicts` → `None` prints `skipped (not configured): functional-property
    conflicts`
  - `locally_redeclared_concepts` → `None` (already returned `None` since Task 4) prints
    `skipped (not configured): locally redeclared concepts`
  - `graph.dangling_terms` never returns `None`, so its branch is unchanged.
- `graph.dangling_terms(g, vocab)` was already being called with `vocab` — no change
  needed there; the brief's instruction to "pass `config.vocabulary` into
  `graph.dangling_terms` too" was already satisfied by the C13 plumbing.

## Files changed

- `src/knowledge/contradictions.py` — removed `FUNCTIONAL_PROPERTIES` constant; sourced
  the property list from `vocab.checks.functional_properties`; added the `None` sentinel
  and its docstring explanation.
- `src/knowledge/cli.py` — `cmd_contradictions` now branches on `None` for both
  `functional_conflicts` and `locally_redeclared_concepts`, printing a distinct
  "skipped (not configured)" line instead of silently treating an empty/absent result as
  a pass.
- `tests/test_contradictions.py` — added two tests from the brief, adapted per ruling C6
  (requested `write_spec` as a fixture argument, not imported from `tests.conftest`).

## TDD evidence

### RED

Added the two brief tests to `tests/test_contradictions.py`
(`test_conflict_is_found_for_a_configured_functional_property` and
`test_no_configured_properties_returns_none`), then ran:

```
uv run pytest tests/test_contradictions.py -v
```

Result: 3 passed, 1 failed.

`test_conflict_is_found_for_a_configured_functional_property` passed immediately because
the default `config` fixture's `functional_properties` already matched the hardcoded
constant's values, and `functional_conflicts` already accepted `vocab` for `vocab.term()`
lookups (pre-existing C13 plumbing) — so that path was already exercised correctly before
my change. `test_no_configured_properties_returns_none` failed for the expected reason:

```
FAILED tests/test_contradictions.py::test_no_configured_properties_returns_none
AssertionError: assert [] is None
 +  where [] = functional_conflicts(g, vocab)
```

This confirms the pre-change code always returned a list (from the module-level
`FUNCTIONAL_PROPERTIES` constant) regardless of `vocab.checks.functional_properties`,
which is exactly the gap this task closes.

### GREEN

After rewriting `contradictions.py` and `cli.py`:

```
uv run pytest tests/test_contradictions.py -v
```

```
tests/test_contradictions.py::test_functional_conflicts_finds_two_routes_on_one_view PASSED
tests/test_contradictions.py::test_functional_conflicts_is_empty_for_a_single_route PASSED
tests/test_contradictions.py::test_conflict_is_found_for_a_configured_functional_property PASSED
tests/test_contradictions.py::test_no_configured_properties_returns_none PASSED
4 passed in 0.07s
```

Full suite:

```
uv run pytest -q
166 passed in 6.96s
```

(Baseline was 164; +2 new tests = 166. No warnings, no skips.)

## Skipped-check CLI output

Built a throwaway repo at `/tmp/skip_demo` with a `knowledge.toml` that omits
`functional_properties`, `concept_class`, and `concept_spec` entirely (so both checks have
nothing to check), and ran:

```
$ cd /tmp/skip_demo && uv run --project <repo> python -m knowledge.cli contradictions
skipped (not configured): functional-property conflicts
skipped (not configured): locally redeclared concepts
no mechanical contradictions found
```

Both skip lines print distinctly, and `dangling_terms` (never `None`) still runs
normally and found nothing in this minimal fixture.

## Self-review

- **Completeness**: both `functional_conflicts` and the `cmd_contradictions` three-branch
  update are done. `graph.dangling_terms` already had `vocab` threaded through from
  Task/ruling C13 — verified rather than assumed by reading the current call site.
- **No overbuilding**: only the second half specified in the task context was touched.
  Did not re-touch the `vocab` plumbing, `MON`, or any other check.
- **Naming accuracy**: `functional_conflicts` signature and return type match the brief
  exactly (`list[tuple[str, str, list[str]]] | None`).
- **`None` sentinel documented**: yes, in `functional_conflicts`'s docstring, mirroring
  `restated_rule_comments`'s "nothing to check is not the same as nothing found" phrasing.
- **Tests verify real behavior**: `test_no_configured_properties_returns_none` actually
  exercises the empty-config path via `dataclasses.replace`, not a mock. The existing
  `test_functional_conflicts_is_empty_for_a_single_route` still asserts `== []` (not
  `is None`), which is correct since the `config` fixture's default vocabulary keeps
  `functional_properties` populated — verified this didn't need updating.
- **Pristine output**: full suite is 166 passed, 0 warnings, 0 skips.
- **Diff scope**: `git diff` for this commit touches exactly `contradictions.py`,
  `cli.py`, and `tests/test_contradictions.py` — no stray files, no leftover
  `FUNCTIONAL_PROPERTIES` references anywhere in the tree (verified via grep).
- **Style**: LF line endings and no trailing whitespace confirmed on all three changed
  files before committing.

## Concerns

None. One observation, not a defect: when every functional-property/redeclaration check
is unconfigured and `dangling_terms` finds nothing, `cmd_contradictions` still prints "no
mechanical contradictions found" after the two skip lines. That's the pattern Task 4
already established for `locally_redeclared_concepts` alone; extending it consistently to
`functional_conflicts` seemed correct rather than inventing a different combined-skip
message, but flagging it in case the controller wants a different combined message when
*all* checks are skipped.

---

## Fix round 1 of 5

**Finding**: the flagged concern was upgraded to a defect by the controller. When both
configurable checks (`functional_conflicts`, `locally_redeclared_concepts`) were
unconfigured, `cmd_contradictions` still printed the bare `no mechanical contradictions
found` — a verdict on the whole corpus — even though only `dangling_terms` (one of three
checks) actually ran. That is the exact "checked and clean" vs. "cannot be checked"
conflation the `None` sentinel exists to prevent, and it is not the pattern
`cmd_validate` set (that command prints one line per check and never emits a summary that
outranks its own per-check output).

### Message logic (new)

`cmd_contradictions` in `src/knowledge/cli.py` now tracks a `skipped` counter, incremented
each time `functional_conflicts` or `locally_redeclared_concepts` returns `None`. The
final summary (printed only when `found` is `False`, i.e. nothing was found among the
checks that ran) now branches on that counter:

```python
if not found:
    if skipped:
        print(
            f"no contradictions found by the checks that ran"
            f" ({skipped} skipped — see above)"
        )
    else:
        print("no mechanical contradictions found")
```

- **At least one skipped** → `no contradictions found by the checks that ran (N skipped
  — see above)` — a count and a pointer upward, no restating which checks, cannot be read
  as a verdict on checks that did not run.
- **None skipped** → `no mechanical contradictions found`, unchanged from before.

### Test added

`tests/test_cli_read.py::test_contradictions_summary_accounts_for_skipped_checks` — pairs
with the existing `test_contradictions_reports_none_on_a_clean_graph` (all configured,
clean) to pin both branches. It takes the `seeded` fixture's on-disk `knowledge.toml`,
strips out `concept_class`/`concept_spec` and `functional_properties` (so both
configurable checks return `None`), reruns `contradictions --include-drafts`, and asserts:

```python
def test_contradictions_summary_accounts_for_skipped_checks(seeded, capsys):
    """With every configurable check unconfigured, only dangling_terms actually ran. The
    summary must not read as a verdict on the checks that were skipped."""
    toml_path = seeded.root / "knowledge.toml"
    text = toml_path.read_text(encoding="utf-8")
    text = text.replace('concept_class = "Concept"\nconcept_spec = "concepts"\n', "")
    text = text.replace(
        'functional_properties = ["route", "editable", "required", "viewport", "defaultsTo"]\n',
        "",
    )
    toml_path.write_text(text, encoding="utf-8")

    args = run(["contradictions", "--include-drafts"])
    assert args.handler(args) == 0
    out = capsys.readouterr().out
    assert "no mechanical contradictions found" not in out
    assert "2 skipped" in out
```

### Commands run and output

```
uv run pytest tests/test_contradictions.py tests/test_cli_read.py -v
```

```
tests/test_contradictions.py::test_functional_conflicts_finds_two_routes_on_one_view PASSED
tests/test_contradictions.py::test_functional_conflicts_is_empty_for_a_single_route PASSED
tests/test_contradictions.py::test_conflict_is_found_for_a_configured_functional_property PASSED
tests/test_contradictions.py::test_no_configured_properties_returns_none PASSED
tests/test_cli_read.py::test_list_shows_every_spec PASSED
tests/test_cli_read.py::test_list_filters_by_status PASSED
tests/test_cli_read.py::test_list_filters_to_specs_with_open_questions PASSED
tests/test_cli_read.py::test_list_filters_to_unmodeled_specs PASSED
tests/test_cli_read.py::test_list_unmodeled_catches_content_drift_after_modeling PASSED
tests/test_cli_read.py::test_list_unmodeled_catches_an_outdated_ontology_version PASSED
tests/test_cli_read.py::test_list_unmodeled_catches_a_row_with_no_recorded_audit_hash PASSED
tests/test_cli_read.py::test_show_prints_the_row_and_its_questions PASSED
tests/test_cli_read.py::test_show_reports_an_unknown_id PASSED
tests/test_cli_read.py::test_questions_lists_open_ones PASSED
tests/test_cli_read.py::test_validate_passes_on_a_clean_graph PASSED
tests/test_cli_read.py::test_graph_writes_a_turtle_file PASSED
tests/test_cli_read.py::test_graph_defaults_to_verified_specs_only PASSED
tests/test_cli_read.py::test_contradictions_reports_none_on_a_clean_graph PASSED
tests/test_cli_read.py::test_contradictions_summary_accounts_for_skipped_checks PASSED
tests/test_cli_read.py::test_contradictions_reports_a_functional_conflict PASSED
20 passed in 0.79s
```

Full suite:

```
uv run pytest -q
167 passed in 7.45s
```

(166 → 167: the one new test. No warnings, no skips.)

### CLI output, all-skipped case

Re-ran the same throwaway `/tmp/skip_demo` repo used earlier (a `knowledge.toml` that
omits `functional_properties`, `concept_class`, and `concept_spec` entirely):

```
$ cd /tmp/skip_demo && uv run --project <repo> python -m knowledge.cli contradictions
skipped (not configured): functional-property conflicts
skipped (not configured): locally redeclared concepts
no contradictions found by the checks that ran (2 skipped — see above)
```

(The Bash tool's Windows console codepage garbled the em dash to `?` on first capture;
confirmed via `PYTHONIOENCODING=utf-8` and via raw hex inspection of the source file
—`e2 80 94`, the correct UTF-8 encoding of `—` — that this was a terminal display
artifact, not a bug in the emitted bytes or the source file.)

### Self-review

- Message cannot be misread as a verdict on unrun checks: it explicitly says "found by
  the checks that ran" and names the skip count with a pointer upward.
- Wording avoids restating which checks were skipped, per the ruling.
- Both branches (all-configured-clean, all-skipped) are now pinned by tests.
- Diff is scoped to exactly the two files that needed the change; `git diff` reviewed
  before committing.
- LF line endings and no trailing whitespace confirmed on both changed files.
- Full suite pristine at 167 passed, 0 warnings, 0 skips.

### Commit

`74b6741` — fix: do not report a clean contradictions run when checks were skipped
