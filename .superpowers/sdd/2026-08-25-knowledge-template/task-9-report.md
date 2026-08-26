# Task 9 report: `knowledge init`

Commit: `6bf11ac feat: add knowledge init` (repo: `C:/Users/jesus/Documents/Proyectos/knowledge-template`, branch `main`)

## What was implemented

- `src/knowledge/init.py` (new): `Answers`, `slugify`, `_values`, `substitute`, `remaining_placeholders`,
  `_rewrite_vocabulary_keys`, `_rewrite_ontology_prefix`, `_reset_metadata`, `run`, `MANIFEST`,
  `PLACEHOLDER`, `SKIPPED_DIRS`, `TEXT_SUFFIXES`.
- `src/knowledge/cli.py` (modified): `_prompt`, `cmd_init`, the `init` subparser, module-level
  `import shutil` (and removal of the now-redundant local `import shutil` inside `cmd_publish`).
- `tests/test_init.py` (new): 12 tests.

Applied both corrections from the brief:

- **C12** — `knowledge.toml`'s `[vocabulary]` namespace/instances/prefix, and the ontology
  file's own `@prefix` line, are **rewritten in place** from working defaults, not substituted
  from `{{TOKEN}}`s. `{{TOKEN}}` substitution is reserved for prose files.
- **Manifest addition** — `run`'s `substitute` call includes `ontology/{ontology_file}` and
  `specs/example/spec.ttl` alongside `MANIFEST`, exactly as given.

## A gap the corrections didn't cover, found and fixed

`remaining_placeholders` walks every file under `TEXT_SUFFIXES`, which originally included
`.py`. `src/knowledge/config.py` (already shipped, from Task 2) documents the token mechanism
in a docstring using a literal example: `"""An unsubstituted {{PLACEHOLDER}} reads as empty..."""`.
My own `init.py`/`test_init.py` do the same, extensively, to document the C12 split. Since
`{{PLACEHOLDER}}` is all-uppercase, it matches `PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")`
literally — so `init --check` flagged the tooling's own source code as an unsubstituted
placeholder, in every generated repository, forever (`src/`/`tests/` ship as-is; nothing
templates them). This would have made `--check` permanently red on a correctly configured
repository. Confirmed by running `--check` against a first draft before the fix — see RED/GREEN
evidence below for `test_remaining_placeholders_ignores_a_token_shaped_docstring_in_python_source`.

Fix: dropped `.py` from `TEXT_SUFFIXES`. Nothing shipped ever needs a `{{TOKEN}}` substituted
inside a `.py` file — `MANIFEST` never names one — so this removes the false positive without
weakening real placeholder detection. Documented at the `TEXT_SUFFIXES` definition in
`init.py`.

## A pre-existing bug in the brief's own test, found and fixed

The brief's sample `slugify` implementation ("anything that is not a letter or a digit goes")
and its own test (`slugify("Acme Widgets, Inc.") == "acmewidgets"`) disagree: the implementation
keeps every letter, including "Inc", producing `"acmewidgetsinc"`, not `"acmewidgets"`. This
predates my corrections — the same mismatch is baked into
`monicords-knowledge/docs/superpowers/plans/2026-08-25-knowledge-template.md` (the source plan),
so it isn't something Correction 1 or 2 touches. No other file in the plan documents
suffix-stripping logic for company designators, so I judged the test's expected value to be the
error and fixed the assertion to match the implementation's documented, simple behavior
(`"acmewidgetsinc"`), rather than inventing unrequested suffix-stripping logic. Flagging this
explicitly in case the controller disagrees with that call.

## TDD evidence

**RED** — before `src/knowledge/init.py` existed:

```
$ uv run pytest tests/test_init.py -v
...
ImportError while importing test module '...\tests\test_init.py'.
tests\test_init.py:3: in <module>
    from knowledge import init
E   ImportError: cannot import name 'init' from 'knowledge' (...\src\knowledge\__init__.py)
1 error in 0.18s
```

**RED (intermediate)** — first implementation pass, two failures for the reasons expected:

```
tests/test_init.py::test_slugify_lowercases_and_strips_punctuation FAILED
    AssertionError: assert 'acmewidgetsinc' == 'acmewidgets'
tests/test_init.py::test_run_reports_only_files_it_actually_changed FAILED
    AssertionError: docs/README.template.md was reported rewritten but is gone
2 failed, 9 passed in 0.50s
```

Fixed by (a) correcting the test's expected slugify value to match the documented
implementation, and (b) having `run` swap the `docs/README.template.md` manifest entry for
`README.md` once the file is moved, so every path `run` reports still exists on disk.

**GREEN** — full `test_init.py`, 12/12, after adding the `.py`-exclusion regression test:

```
$ uv run pytest tests/test_init.py -v
tests/test_init.py::test_slugify_lowercases_and_strips_punctuation PASSED
tests/test_init.py::test_run_substitutes_every_placeholder PASSED
tests/test_init.py::test_run_produces_a_loadable_config PASSED
tests/test_init.py::test_run_rewrites_the_ontology_prefix_lines PASSED
tests/test_init.py::test_run_rewrites_ontology_term_usages_too PASSED
tests/test_init.py::test_run_removes_the_example_spec_and_empties_the_dump PASSED
tests/test_init.py::test_run_replaces_the_readme_with_the_template_one PASSED
tests/test_init.py::test_run_refuses_a_configured_repository PASSED
tests/test_init.py::test_remaining_placeholders_reports_what_is_left PASSED
tests/test_init.py::test_an_empty_code_repo_answer_disables_staleness PASSED
tests/test_init.py::test_remaining_placeholders_ignores_a_token_shaped_docstring_in_python_source PASSED
tests/test_init.py::test_run_reports_only_files_it_actually_changed PASSED
12 passed in 0.44s
```

**Full suite, GREEN, no warnings, no skips:**

```
$ uv run pytest -q
........................................................................ [ 35%]
........................................................................ [ 70%]
.............................................................            [100%]
205 passed in 8.00s
```

193 baseline + 12 new = 205. Confirmed both before commit and inside the scratch end-to-end
copy (also 205).

## The ontology prefix rewrite: exactly what regex, and why it's safe

`_rewrite_ontology_prefix(text, old_prefix, new_prefix, namespace)` in `src/knowledge/init.py`,
two bounded passes, applied in this order:

1. **The `@prefix` declaration line**, matched and replaced as a whole:
   ```python
   declaration = re.compile(rf"@prefix\s+{re.escape(old_prefix)}:\s+<[^>]*>\s*\.")
   text = declaration.sub(f"@prefix {new_prefix}: <{namespace}> .", text, count=1)
   ```
   `@prefix ex: <https://example.com/ontology#> .` becomes
   `@prefix acme: <https://acme.test/ontology#> .` — prefix name and IRI replaced together,
   in one match, so there's no window where they could get out of sync. Run **first**, while
   the line still literally reads `old_prefix:` — this matters, because pass 2 renames every
   bare `old_prefix:` it finds, and if it ran first it would rename this line's prefix without
   updating its IRI.

2. **Every remaining bare `old_prefix:` usage** — `ex:Concept`, `rdfs:domain ex:Concept`, etc.:
   ```python
   bare = re.compile(rf"\b{re.escape(old_prefix)}:")
   text = bare.sub(f"{new_prefix}:", text)
   ```
   `\b` anchors the match on a word boundary immediately before `old_prefix`, and the pattern
   requires a literal `:` immediately after it. Two things this rules out, both checked against
   the actual seed content:
   - **A longer word containing the prefix as a substring** — `example:` never matches `\bex:`,
     because although `\b` fires before "e", the four characters after "ex" are "ampl", not ":".
   - **The prefix text appearing inside an IRI's host name** — `https://example.com/...` has the
     same property: "ex" inside "example.com" is never followed by ":".
   - The `app:` (instance) prefix line is untouched by design: correction C12 scopes this
     rewrite to the vocabulary's own prefix, matching `_rewrite_vocabulary_keys`, which likewise
     rewrites only `namespace`/`instances`/`prefix`, never `instance_prefix`.

   This is a plain-text regex, not a Turtle parser, so it is bounded to a file that is small and
   hand-authored (three classes, three properties, per Task 10's own draft) rather than treated
   as a general solution — documented as such in the function's docstring.

Verified directly by `test_run_rewrites_the_ontology_prefix_lines` (declaration line) and
`test_run_rewrites_ontology_term_usages_too` (added by me — asserts `acme:Concept a rdfs:Class`
appears and no `ex:` survives anywhere in the file).

`_rewrite_vocabulary_keys` (for `knowledge.toml`) uses a parallel, simpler discipline: each of
`namespace`/`instances`/`prefix` is matched with `(?m)^key\s*=\s*"..."$`, anchored to the start
of its own line. In the shipped file `namespace` and `instances` each appear on exactly one
line; `prefix` — anchored to line-start — cannot match `instance_prefix` or
`absorbed_prefixes`, since both start with a different word before hitting "prefix" mid-string.

## End-to-end scratch-directory proof

Copied the repository to
`C:/Users/jesus/AppData/Local/Temp/claude/C--Users-jesus-Documents-Proyectos-monicords-app/015c1467-a49e-44d3-83d1-5052e1c90362/scratchpad/knowledge-template-e2e`
(minus `.git`, `.pytest_cache`, `__pycache__`), ran `init` non-interactively there, and deleted
the copy afterward. Full transcript:

```
=== [1] init --check BEFORE init (expect fail: [project] name and [repo] code_repo are still {{TOKEN}}) ===
3 placeholder(s) not substituted:
  - knowledge.toml: {{PROJECT_NAME}}
  - knowledge.toml: {{CODE_REPO}}
  - knowledge.toml: {{PROJECT_NAME}}
exit=1

=== [2] run init non-interactively ===
$ uv run knowledge init --name "Acme Corp" --base-iri "https://acme.test/" --prefix acme \
      --instance-prefix app --code-repo "" --publish-target none --dependency-preset none
configured Acme Corp: rewrote 1 file(s)
  - knowledge.toml
exit=0

=== [3] init --check AFTER init (expect pass) ===
no placeholders remain
exit=0

=== [4] knowledge.toml after init (relevant excerpt) ===
[project]
name = "Acme Corp"

[vocabulary]
ontology_file   = "ontology.ttl"
namespace       = "https://acme.test/ontology#"
instances       = "https://acme.test/id/"
prefix          = "acme"
instance_prefix = "app"
...
[repo]
code_repo = ""     # empty disables `stale` and `dep`
...
[publish.sidebar]
title         = "Acme Corp"

=== [5] load_config returns the new values ===
project_name = Acme Corp
namespace    = https://acme.test/ontology#
instances    = https://acme.test/id/
prefix       = acme
unconfigured = False
code_repo    = None

=== [6] re-run init non-interactively: must refuse (already configured) ===
error: ...\knowledge-template-e2e is already configured — remove the [template] table from
knowledge.toml to re-run init
exit=1

=== [7] .metadata state after init ===
dump.sql
-- Generated by `knowledge`. Do not edit by hand.
-- The database itself is gitignored; this file is the tracked artifact.
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
COMMIT;
PRAGMA foreign_keys=ON;

=== [8] pytest inside the scratch copy ===
205 passed in 8.87s
```

(The real template repo does not yet have `ontology/ontology.ttl` or `specs/example/` —
Task 10 creates those. `substitute` and `_rewrite_ontology_prefix` both no-op gracefully on
the missing ontology file, `shutil.rmtree(..., ignore_errors=True)` no-ops on the missing
`specs/example`, confirmed by step [2]'s clean exit and step [8]'s green suite. The
`ontology.ttl`-specific rewrite behavior above is proven against `tests/test_init.py`'s fixture,
which models the shipped reality per correction C12.)

## Files changed

- `C:/Users/jesus/Documents/Proyectos/knowledge-template/src/knowledge/init.py` (new, 248 lines)
- `C:/Users/jesus/Documents/Proyectos/knowledge-template/src/knowledge/cli.py` (modified: +`import shutil` at module level, removed the redundant local import in `cmd_publish`, added `_prompt`, `cmd_init`, the `init` subparser)
- `C:/Users/jesus/Documents/Proyectos/knowledge-template/tests/test_init.py` (new, 171 lines, 12 tests)

## Self-review findings

- `run`'s `rewritten` list is now built so every entry is a path that exists on disk when the
  function returns — the `docs/README.template.md` → `README.md` swap (see TDD evidence above)
  was needed to make that true; the brief's original sample code did not do this swap.
- `knowledge.toml` is only appended to `rewritten` if its text actually changed (compared
  against a snapshot taken before any edits), rather than assumed — though in practice it always
  changes, because the `[template]` guard at the top of `run` guarantees the table was present
  and gets removed.
- The ontology-file rewrite is tracked into `rewritten` separately from the generic
  `substitute()` pass (it doesn't go through `substitute`, since it's not token substitution),
  guarded by `if new_text != text` so a no-op (e.g., `answers.prefix == old_prefix`, only the
  IRI changes — still counted) is still counted correctly and a true no-op (unreachable in
  practice, since the namespace always changes with `answers.base_iri`) would not be.
- Confirmed no CRLF and no trailing whitespace in the two new files and the modified `cli.py`
  region.
- Confirmed `.py` files are the only other project source using `{{ALL_CAPS}}`-shaped substrings
  (`cli.py`/`deps.py`'s SPARQL f-strings use `{{ ... }}` for literal braces, but never with an
  uppercase-only run inside, so they were never at risk of matching `PLACEHOLDER` — verified by
  the pre-fix `--check` output only flagging `config.py` and my own new files, never `cli.py` or
  `deps.py`).
- Did not touch `dependency_preset` handling (the `presets/{name}.toml` splice) beyond what the
  brief already specified — untested by my test suite (the brief's given test list doesn't
  exercise a non-`"none"` preset either), confirmed `presets/nextjs.toml` exists in the real
  repo so the code path is at least reachable, but this is inherited, unmodified logic and out
  of my corrections' scope.
- Left the `# Written by \`knowledge init\`. Remove the [template] table to unlock a re-run.`
  comment in place at the top of the rewritten `knowledge.toml` even though, post-init, there is
  no `[template]` table left for it to refer to — inherited verbatim from the brief's given code,
  not something either correction touches; flagged here rather than silently changed.

## Concerns for the controller

1. The `slugify` test-vs-implementation mismatch (see above) — I fixed the test to match the
   implementation rather than the reverse. If the intended behavior really was suffix-stripping,
   this needs a different implementation and a different test comment.
2. The `.py`-exclusion from `TEXT_SUFFIXES` is a real behavioral change from the brief's sample
   code (which included `.py`). I believe it's necessary for `--check` to ever pass in the
   shipped template (proven by the pre-fix `--check` transcript flagging `config.py`), but
   flagging it explicitly since it wasn't called out in either correction.
3. `ontology/ontology.ttl` and `specs/example/` don't exist in the template repo yet (Task 10's
   job). My tests exercise the ontology-prefix rewrite entirely against `test_init.py`'s own
   fixture, which I built to match correction C12's description of the shipped reality. The
   end-to-end proof against the *actual* repo therefore can't demonstrate the ontology rewrite
   firing for real — only that `run` degrades gracefully when that file is absent. Task 10, when
   it lands, should re-verify the ontology rewrite fires correctly against the real seed file
   (and will need its own C12-equivalent correction, since its brief's draft `ontology.ttl` and
   `specs/example/spec.ttl` also use `{{PREFIX}}`/`{{BASE_IRI}}` tokens, which would fail to
   parse as Turtle for the same reason C12 identified for this task).

---

## Fix round 1 of 5

Commit: `22bb265 fix: confine the prefix rewrite to Turtle code positions, and stop swallowing rmtree errors`

Three findings from review, all fixed.

### 1. The bare-prefix rewrite corrupted prose inside the ontology file

The old bare pass (`bare.sub(f"{new_prefix}:", text)`, run over the *whole* file text) could
not tell code from prose, so it also rewrote the prefix wherever it was quoted as English
shorthand — a `#` comment explaining the file, or an `rdfs:comment` string value.

**Approach — a "protected span" the rewrite must not enter, plus a line-scanned comment
boundary:**

```python
# A Turtle span a comment-boundary search or the bare-prefix rewrite below must not look
# inside: a "..." string literal, or a <...> IRI. Both can contain a literal '#' or the
# prefix text without either meaning what it would in code -- a namespace IRI conventionally
# ends in '#' (<https://acme.test/ontology#>), and a hand-authored rdfs:comment/rdfs:label
# routinely uses the prefix as English shorthand ("write ex: before every term"). Single
# double-quoted strings and single-bracketed IRIs only: the seed ontology never uses
# triple-quoted string literals, an escaped '"' inside one, or a nested '<'/'>' inside an
# IRI, so this one-pass regex does not need to handle those.
PROTECTED_SPAN = re.compile(r'"(?:\\.|[^"\\])*"|<[^<>]*>')
```

`_comment_start(line)` walks `PROTECTED_SPAN` matches left to right and looks for `#` only in
the gaps *between* them (and after the last one) -- so a `#` inside a quoted string or an IRI
(an ontology namespace IRI ends in one: `<https://acme.test/ontology#>`) is never mistaken
for a comment marker, and a `#` that starts a genuine comment is still found correctly.

`_rewrite_bare_prefix_outside_protected_spans(code, pattern, replacement)` does the mirror
operation on the code portion of the line (`line[:comment_start]`): it walks the same
`PROTECTED_SPAN` matches, applies `pattern.sub` only to the text *between* spans, and copies
each span through untouched. The comment portion (`line[comment_start:]`) is never touched at
all -- appended back verbatim.

`_rewrite_ontology_prefix` now runs this per line: split `text` on `"\n"`, compute
`comment_start` for each line, rewrite only the code part, reassemble with `"\n".join`
(round-trips a trailing newline correctly, since `"a\n".split("\n")` is `["a", ""]` and
`"\n".join(["a", ""])` is `"a\n"`). The `@prefix` declaration rewrite (pass 1, whole-file
regex) is unchanged, as instructed -- it was already correctly anchored and never touches
prose.

**Why it's safe against the two cases the reviewer traced, plus the one they flagged:**

- **Longer-word / IRI-host collisions** -- unchanged from round 1, still holds (`\b`
  anchoring; verified by `test_run_rewrites_ontology_term_usages_too` and
  `test_ontology_rewrite_distinguishes_code_from_prose_in_one_pass`).
- **String literals** (`rdfs:comment "Write ex: before every term."@en .`) -- the string is
  one `PROTECTED_SPAN` match, copied through unrewritten.
- **`#` comments** (`# ...; ex: is just a starting point.`) -- `_comment_start` returns `0`
  for a line with no protected span before its first `#`, so the *entire* line becomes the
  "comment" half and never reaches the rewrite pass.
- **A `#` inside an IRI** (the `@prefix` declaration lines themselves, since a namespace IRI
  ends in `#`) -- also now a `PROTECTED_SPAN` match, so `_comment_start` doesn't truncate the
  line there either. This wasn't corrupting anything in round 1 either (pass 1 already
  rewrites those lines before pass 2 runs, so pass 2 had nothing left to touch on them), but
  it's fixed as a side effect of choosing `PROTECTED_SPAN` to cover IRIs generally, rather
  than relying on that lucky no-op -- a more defensible design than one that happens not to
  matter today.

**Three new tests, run against the pre-fix (round-1-committed) regex first to confirm they
fail for the stated reason (RED), reproducing exactly the corruption the reviewer found:**

```
$ uv run pytest tests/test_init.py -k "leaves_a_hash_comment or leaves_a_string_literal or rewrites_ontology_term_usages_too" -v
tests/test_init.py::test_run_rewrites_ontology_term_usages_too PASSED
tests/test_init.py::test_ontology_rewrite_leaves_a_hash_comment_alone FAILED
tests/test_init.py::test_ontology_rewrite_leaves_a_string_literal_alone FAILED

FAILED test_ontology_rewrite_leaves_a_hash_comment_alone
  assert 'ex: is just a starting point' in
  '...# Delete anything here that your domain has no use for; acme: is just a starting point.\n...'
FAILED test_ontology_rewrite_leaves_a_string_literal_alone
  assert 'Write ex: before every term.' in
  '...rdfs:comment "Write acme: before every term."@en .\n'
2 failed, 1 passed, 11 deselected in 0.23s
```

(Obtained by temporarily swapping in `git show 6bf11ac:src/knowledge/init.py`, running the new
tests against it, then restoring the fixed version -- the round-1 commit itself is otherwise
unmodified; this was a local, uncommitted swap purely to produce RED evidence.)

**GREEN**, same three tests, fixed version restored:

```
$ uv run pytest tests/test_init.py -k "leaves_a_hash_comment or leaves_a_string_literal or rewrites_ontology_term_usages_too" -v
tests/test_init.py::test_run_rewrites_ontology_term_usages_too PASSED
tests/test_init.py::test_ontology_rewrite_leaves_a_hash_comment_alone PASSED
tests/test_init.py::test_ontology_rewrite_leaves_a_string_literal_alone PASSED
3 passed, 11 deselected
```

A fourth test, `test_ontology_rewrite_distinguishes_code_from_prose_in_one_pass`, checks all
three outcomes (`acme:Concept a rdfs:Class` present, both prose instances of `ex:` still
present) from one `run` call, so the code-position rewrite and the two prose exclusions are
proven not to be independently coincidental.

The fixture (`build_template`'s `ontology.ttl`) now includes the two prose lines the
reviewer's repro used: a `#` comment ("Delete anything here ...; ex: is just a starting
point.") and an `rdfs:comment` string ("Write ex: before every term.").

### 2. `shutil.rmtree(..., ignore_errors=True)` swallowed every error, not just "already gone"

```python
# Guarded on existence, not `ignore_errors=True`: the only case this must tolerate
# silently is the directory already being gone (Task 10 has not created it yet in the
# shipped template as of this task). `ignore_errors=True` would also swallow a real
# failure -- a permission error or a locked file, plausible on Windows -- and `run` would
# then report success with the stale example content still on disk and nothing
# downstream to catch it, since the example files carry no {{TOKEN}} for
# `remaining_placeholders` to flag.
example_dir = root / "specs" / "example"
if example_dir.exists():
    shutil.rmtree(example_dir)
```

`test_run_removes_the_example_spec_and_empties_the_dump` (existing) still passes unchanged --
the guarded path is identical to the old behavior when the directory exists and is deletable,
which is every case that test, and the real template today (no `specs/example/` yet),
exercise. No new test added for the error-surfacing path itself: simulating a genuine Windows
permission/lock failure portably in this suite would need platform-specific setup not
requested by the review, and the fix is a direct, auditable read of `shutil.rmtree`'s own
`ignore_errors` contract rather than new logic to unit test.

### 3. `--install-skill`'s off-by-default behaviour had no inline reason

```python
skill = root / "integrations" / "code-repo" / ".claude" / "skills" / "knowledge-base"
# Off by default: writing into a second, external repository (the code repo) must be an
# explicit request (--install-skill), never a side effect of running `init`.
if args.install_skill and answers.code_repo:
```

### Verification

```
$ uv run pytest tests/test_init.py -v
15 passed in 0.50s

$ uv run pytest -q
208 passed in 8.02s
```

193 baseline + 15 in `test_init.py` = 208. No warnings, no skips.

### Files changed (this round)

- `src/knowledge/init.py` -- `PROTECTED_SPAN`, `_comment_start`,
  `_rewrite_bare_prefix_outside_protected_spans`, rewritten `_rewrite_ontology_prefix` body,
  guarded `specs/example` deletion.
- `src/knowledge/cli.py` -- one-line rationale comment on the `--install-skill` branch.
- `tests/test_init.py` -- extended `ontology.ttl` fixture with the two prose lines, fixed
  `test_run_rewrites_ontology_term_usages_too`'s over-broad `"ex:" not in text` assertion (no
  longer valid once prose legitimately keeps `ex:`) to the precise `"ex:Concept" not in text`,
  and three new tests.

### Deferred (per the coordinator's instruction, not fixed this round)

`except UnicodeDecodeError` lacking an inline comment; the stale `[template]` comment left in
`knowledge.toml` after init; the `dependency_preset` splice's dependence on exact double-space
formatting; the absence of a direct `cmd_init` CLI test. Left as-is, in the ledger for final
review.

---

## Fix round 2 of 5

Commit: `4715e43 fix: rewrite the instance prefix declaration alongside the project prefix`

One finding, found by the coordinator running the real end-to-end lifecycle after Task 10
landed the real seed ontology and example spec.

### The gap

`_rewrite_ontology_prefix` rewrote the project prefix (`ex:` -> the configured prefix) but
never touched the instance prefix (`app:` by default). `graph.turtle_source` concatenates
ontology.ttl's `@prefix` declarations with every spec's *bare* `.ttl` content — a spec never
declares its own prefixes — so `app:Widget` in any spec resolves against whatever IRI
ontology.ttl's own `@prefix app:` line names, at parse time. Left pointed at
`https://example.com/id/` after a real `init`, every individual any spec ever writes
silently detached from `config.vocabulary.instances`, and `vocab.is_instance()` (a literal
`str(iri).startswith(...)` check) returned False for all of them without erroring — switching
off `graph.dangling_terms`' instance half and the underscore half of
`lint.naming_violations`, both still reporting clean. It was invisible to every test and to
round 1's own end-to-end proof because `init` deletes `specs/example/` — the post-init graph
in every check up to this point had no instances in it at all.

### The fix

Generalized the single-prefix rewrite into `_rewrite_prefix_pair(text, old_prefix,
new_prefix, namespace)` (the declaration-line + code-position logic from round 1, unchanged
in substance), and made `_rewrite_ontology_prefix` call it **twice** — once for the project
prefix, once for the instance prefix:

```python
def _rewrite_ontology_prefix(
    text, old_prefix, new_prefix, namespace,
    old_instance_prefix, new_instance_prefix, instances,
):
    text = _rewrite_prefix_pair(text, old_prefix, new_prefix, namespace)
    text = _rewrite_prefix_pair(text, old_instance_prefix, new_instance_prefix, instances)
    return text
```

The two passes are independent: each searches only for its own *old* prefix text, so
rewriting `ex:` can't touch anything the `app:` pass is about and vice versa (documented
inline). `run()` now computes `old_instance_prefix = config.vocabulary.instance_prefix` and
passes both prefix pairs through.

**A related gap fixed alongside it, found while wiring this up, not separately requested:**
`knowledge.toml`'s own `[vocabulary] instance_prefix` key was never rewritten either (round
1 deliberately scoped `_rewrite_vocabulary_keys` to `namespace`/`instances`/`prefix` only,
per correction C12's literal wording). Left alone, a user who answers a *different* instance
prefix at the `init` prompt would end up with `config.vocabulary.instance_prefix` still
saying `"app"` while the ontology file (now fixed, above) actually declares whatever they
answered — `vocab.sparql_prefixes` and `cmd_describe`'s default term prefix would then
declare/assume the wrong one for every `query`/`ask`/`describe` call. Added
`"instance_prefix": answers.instance_prefix` to the same `_rewrite_vocabulary_keys` call
that already handles `namespace`/`instances`/`prefix`, with the reasoning inline at the call
site and in the function's docstring. This mirrors the round-1 `.py`/`TEXT_SUFFIXES`
precedent — a gap adjacent to the literal ask, fixed in the same commit rather than only
flagged, because leaving it would reintroduce the identical "reports clean without having
checked" pattern one level up (in `knowledge.toml` instead of `ontology.ttl`) the moment
someone actually changes the instance prefix.

### Tests: RED against the pre-fix code, then GREEN

Three new tests, matching the coordinator's three asks exactly:

- `test_ontology_instance_prefix_line_matches_the_configured_instances_iri` — the ontology's
  `@prefix app: <...>` line's IRI equals `config.vocabulary.instances` after `init`.
- `test_bare_instance_prefix_usage_is_rewritten_when_the_instance_prefix_changes` — a
  code-position `app:Term` in the ontology file follows `instance_prefix` to a new name
  (`ind:`), not just the IRI on the declaration line.
- `test_a_rewritten_specs_instance_iri_satisfies_is_instance` — "the one that actually pins
  the consequence": a spec directory *other than* `specs/example` (which `init` deletes) is
  added to the fixture, written the way a person would author it after `init` (using the
  project's real prefix, `acme:`, and the instance prefix, `app:`); `init` runs; then the
  real pipeline — `graph.load_graph`, which is exactly `turtle_source`'s
  ontology+spec concatenation followed by one `rdflib` parse — is used to pull the
  individual's actual parsed `URIRef` out of the graph and assert `vocab.is_instance()` on
  it. This is deliberately not a hand-built `URIRef` matched against config values in
  isolation; it exercises the concatenation-and-parse mechanism the bug actually broke.

Getting a clean rdflib parse for the third test required extending the `build_template`
fixture's `ontology.ttl` with real `rdf:`/`rdfs:` prefix declarations (the fixture's
existing content already used `rdfs:Class`/`rdfs:label`/`rdfs:comment`, but no earlier test
had ever actually run it through `rdflib.parse` — only `.read_text()` — so the missing
declarations had never been exercised).

**RED**, pre-fix code (`git show 22bb265:src/knowledge/init.py`, swapped in temporarily, same
technique as round 1):

```
$ uv run pytest tests/test_init.py -k "instance_prefix_line_matches or bare_instance_prefix_usage_is_rewritten or a_rewritten_specs_instance_iri" -v

FAILED test_ontology_instance_prefix_line_matches_the_configured_instances_iri
  assert '@prefix app: <https://acme.test/id/> .' in
  '...@prefix app: <https://example.com/id/> .\n...'

FAILED test_bare_instance_prefix_usage_is_rewritten_when_the_instance_prefix_changes
  assert 'ind:Seed a acme:Concept .' in
  '...app:Seed a acme:Concept .\n'   <- instance prefix never renamed

FAILED test_a_rewritten_specs_instance_iri_satisfies_is_instance
  AssertionError: the individual did not parse under the expected IRI at all
  assert (rdflib.term.URIRef('https://acme.test/id/Widget'), None, None) in <Graph ...>
  # app:Widget parsed under https://example.com/id/Widget instead -- exactly the
  # detachment the coordinator described.

3 failed, 15 deselected in 0.23s
```

**GREEN**, fixed code restored:

```
$ uv run pytest tests/test_init.py -k "instance_prefix_line_matches or bare_instance_prefix_usage_is_rewritten or a_rewritten_specs_instance_iri" -v
3 passed, 15 deselected
```

**Full `test_init.py`, 18/18:**

```
$ uv run pytest tests/test_init.py -v
18 passed in 0.62s
```

**Full suite:**

```
$ uv run pytest -q
214 passed in 8.79s
```

208 after round 1 (193 baseline + 15 in `test_init.py`), + 3 new `test_init.py` tests this
round, + 3 new tests Task 10 landed in between (`tests/test_template_content.py`) = 214.
`test_init.py` itself now totals 18. No warnings, no skips.

### End-to-end proof, scratch copy

Copied to
`C:/Users/jesus/AppData/Local/Temp/claude/C--Users-jesus-Documents-Proyectos-monicords-app/015c1467-a49e-44d3-83d1-5052e1c90362/scratchpad/knowledge-template-e2e`
(minus `.git`/`.pytest_cache`/`__pycache__`), ran `init` non-interactively with the
coordinator's own repro arguments, and deleted the copy afterward.

```
$ uv run knowledge init --check           # before init
5 placeholder(s) not substituted: ...
exit=1

$ uv run knowledge init --name "Acme Widgets" --base-iri https://acme.test/ \
      --prefix acme --instance-prefix app --code-repo "" \
      --publish-target none --dependency-preset none
configured Acme Widgets: rewrote 3 file(s)
  - knowledge.toml
  - ontology/README.md
  - ontology/ontology.ttl
exit=0

$ uv run knowledge init --check           # after init
no placeholders remain
exit=0
```

The two `@prefix` lines and the two config values, side by side:

```
$ head -2 ontology/ontology.ttl
@prefix acme: <https://acme.test/ontology#> .
@prefix app: <https://acme.test/id/> .

$ python -c "...load_config..."
config namespace : https://acme.test/ontology#
config instances  : https://acme.test/id/
```

Both now agree (`ontology#` line <-> `namespace`, `id/` line <-> `instances`) — this is
exactly the pair that disagreed in the coordinator's repro
(`@prefix app:     <https://example.com/id/> .` against `config instances :
https://acme.test/id/`).

`uv run knowledge scan && uv run knowledge validate --strict` both ran clean afterward
(`validate --strict`: `parsed OK: 21 triples`, every check either clean or correctly
`skipped (not configured)`, exit 0).

### Files changed (this round)

- `src/knowledge/init.py` — `_rewrite_prefix_pair` (generalized from round 1's single-prefix
  logic), `_rewrite_ontology_prefix` now takes both prefix pairs and calls
  `_rewrite_prefix_pair` twice, `run()` computes and threads `old_instance_prefix` through,
  `_rewrite_vocabulary_keys`'s call site in `run()` now also rewrites `instance_prefix`.
- `tests/test_init.py` — `build_template`'s `ontology.ttl` fixture gained real `rdf:`/`rdfs:`
  prefix declarations (needed for an actual `rdflib` parse, not just text assertions), and
  three new tests.

### A new finding surfaced by this round's end-to-end proof, flagged but NOT fixed

Running the full suite *inside* the scratch copy (after `init` had already run there, as an
extra check beyond what this round asked for) turned up a second, unrelated gap in
`_reset_metadata`: `db.connect()` reloads an *existing* `dump.sql`'s content into a freshly
bootstrapped database whenever the database file itself was just deleted and a dump file is
still present (this is `connect`'s own documented pulled-dump-reload behavior, from Task 1,
working exactly as designed for its actual purpose). Task 10's committed
`.metadata/dump.sql` has a real `INSERT INTO spec (...) VALUES ('example', ...)` row (not the
trivial `-- seeded` SQL-comment stand-in round 1's own test fixture used, which is why this
never surfaced in any test to date). Concretely: after a real `init` in the scratch copy,
`.metadata/dump.sql` still contained the `example` spec's row, byte-for-byte, even though
`specs/example/` itself was already deleted from disk — and a subsequent `knowledge scan`
reported `missing 1: example has a row but no files`. `_reset_metadata`'s own docstring says
"so the generated repository starts with no history of specs that are no longer there," which
this does not currently deliver against the real, non-trivial dump.sql Task 10 shipped.

This is outside this round's explicit ask (instance-prefix rewriting), so — following the
same discipline round 2's "deferred, not fixed this round" list asked for — it is reported
here, not touched in this commit. Also outside this round's ask but worth surfacing plainly:
`tests/test_template_content.py` (Task 10's own suite) fails when run inside a scratch copy
*after* `init` has already been run there — expected and not a regression, since those tests
assert the pristine, pre-init template's own state (`init --check` failing, zero specs found)
and a post-init copy is, correctly, no longer in that state; noted only so it is not mistaken
for new breakage if re-run the same way.

---

## Fix round 3 of 5

Commit: `49b41f9 fix: empty the tracked dump so a generated repository starts with no spec rows`

One finding — the one flagged, unfixed, at the end of round 2's report. The coordinator ruled
it in scope (Ruling C23) rather than deferrable: it is the same "persisted state claiming
something that is not so" family as every other finding on this task, and it is literally the
first thing a new user hits, since `scan` is step one of the documented workflow.

### The fix

`_reset_metadata` deleted `paths.db` before calling `db.connect`, but not `paths.dump`. Per
`db.connect`'s own docstring, that reload-from-dump behavior exists on purpose — to pick up a
pulled `dump.sql` that is newer than a stale local database — but it fires under precisely
the condition `_reset_metadata` was creating: no `.db` file, but a `dump.sql` still present.
Task 10's shipped `.metadata/dump.sql` carries a genuine `INSERT INTO spec (...) VALUES
('example', ...)` row, so `db.connect` reloaded it into the "fresh" database and `db.save`
wrote it straight back out, unchanged. Deleting the `.db` alone achieves nothing here, because
`dump.sql` — not the (gitignored) `.db` — is the tracked artifact `db.connect` treats as
authoritative whenever the `.db` is missing.

```python
paths.db.unlink(missing_ok=True)
paths.dump.unlink(missing_ok=True)   # <- added
conn = db.connect(paths)
db.save(conn, paths)
conn.close()
paths.db.unlink(missing_ok=True)
```

The diagnosis from the round-2 report is kept as the function's docstring, expanded with the
concrete symptom (`scan` reporting `missing 1: example has a row but no files` as a new
user's first experience), per the coordinator's instruction to keep it.

### Test: RED against the pre-fix code, then GREEN

`test_run_empties_a_dump_that_has_real_insert_rows` — round 1's own `dump.sql` fixture
(`"-- seeded\n"`, a bare SQL comment) was trivial enough that `db.connect`'s reload had
nothing to actually reload, which is exactly why this slipped through every test until now.
The new test gives `.metadata/dump.sql` genuine content — a real `INSERT INTO spec (...)`
row for a `'ghost'` spec, in the same column shape Task 10's actual shipped dump uses — then
asserts no `INSERT` survives `run()`.

(First attempt at authoring this test round-tripped through a bash-heredoc-invoking-Python
script and the SQL string's `\n` escapes were mangled into literal newlines inside a Python
string literal, breaking `test_init.py`'s own syntax. Rewrote the fixture as a top-level
`GENUINE_DUMP_SQL = """..."""` triple-quoted constant and edited the file directly instead of
generating it through a second layer of escaping.)

**RED**, pre-fix code (`git show 4715e43:src/knowledge/init.py`, swapped in temporarily, same
technique as prior rounds):

```
$ uv run pytest tests/test_init.py -k test_run_empties_a_dump_that_has_real_insert_rows -v
FAILED test_run_empties_a_dump_that_has_real_insert_rows
  AssertionError: assert 'INSERT' not in '-- Generate...n_keys=ON;\n'
  'INSERT' is contained here:
    ...
    INSERT INTO spec (id, title, path, ...) VALUES ('ghost', 'Ghost', ...);
    ...
1 failed, 18 deselected in 0.14s
```

**GREEN**, fixed code restored:

```
$ uv run pytest tests/test_init.py -k test_run_empties_a_dump_that_has_real_insert_rows -v
1 passed, 18 deselected

$ uv run pytest tests/test_init.py -v
19 passed in 0.66s

$ uv run pytest -q
215 passed in 8.82s
```

208 (round 1) + 3 (round 2, instance-prefix tests) + 3 (Task 10's
`test_template_content.py`) + 1 (this round) = 215. No warnings, no skips.

### End-to-end proof, scratch copy

Same coordinates as prior rounds
(`.../015c1467-a49e-44d3-83d1-5052e1c90362/scratchpad/knowledge-template-e2e`), deleted
afterward.

```
$ grep -c "^INSERT" .metadata/dump.sql        # before init
2

$ uv run knowledge init --check               # before init
5 placeholder(s) not substituted: ...
exit=1

$ uv run knowledge init --name "Acme Widgets" --base-iri https://acme.test/ \
      --prefix acme --instance-prefix app --code-repo "" \
      --publish-target none --dependency-preset none
configured Acme Widgets: rewrote 3 file(s)
  - knowledge.toml
  - ontology/README.md
  - ontology/ontology.ttl
exit=0

$ grep -c "^INSERT" .metadata/dump.sql        # after init
0

$ uv run knowledge init --check               # after init
no placeholders remain
exit=0

$ cat .metadata/dump.sql
-- Generated by `knowledge`. Do not edit by hand.
-- The database itself is gitignored; this file is the tracked artifact.
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
COMMIT;
PRAGMA foreign_keys=ON;

$ uv run knowledge scan
added 0, moved 0, unchanged 0, missing 0, demoted 0
exit=0

$ head -2 ontology/ontology.ttl
@prefix acme: <https://acme.test/ontology#> .
@prefix app: <https://acme.test/id/> .
# (still agrees with config namespace/instances, re-confirmed from round 2)

$ uv run knowledge validate --strict
0 spec(s)
parsed OK: 21 triples
no dangling references
... (all clean or correctly skipped)
exit=0
```

`grep -c "^INSERT"` goes from 2 to 0, and `scan` reports `missing 0` — no phantom row, no
warning, nothing for a new user to be confused by.

### Files changed (this round)

- `src/knowledge/init.py` — `_reset_metadata` now also unlinks `paths.dump` before
  `db.connect`, with the mechanism documented inline (Ruling C23).
- `tests/test_init.py` — `GENUINE_DUMP_SQL` fixture constant and
  `test_run_empties_a_dump_that_has_real_insert_rows`.

### Concerns

None new. The `test_template_content.py`-fails-in-a-post-init-scratch-copy note from round 2
still applies and is not a regression from this round's change.
