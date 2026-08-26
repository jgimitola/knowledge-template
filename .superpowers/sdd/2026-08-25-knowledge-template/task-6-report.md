# Task 6 report: Configure the dependency globs

## What I implemented

`C:/Users/jesus/Documents/Proyectos/knowledge-template/src/knowledge/deps.py`:

- Deleted the module constants `DYNAMIC_SEGMENT` and `ROUTE_PREFIXES_ABSORBED_BY_GLOB`.
- Added `_dynamic_delimiters(settings)` — turns `settings.dynamic_segment` (e.g. `"{...}"`,
  `"<...>"`) into an `(opening, closing)` pair via `str.partition("...")`.
- `route_to_glob(route, settings: Dependencies)` and `endpoint_to_glob(endpoint, settings)`
  now take a `Dependencies` and use `settings.absorbed_prefixes`, `settings.route_glob`,
  `settings.endpoint_glob`, `settings.dynamic_replacement` instead of hardcoded Next.js
  values.
- `derived_globs(paths, config: Config, spec_id)` — widened from `vocab` to `config` (ruling
  C4). Returns `set()` immediately when `config.dependencies.derives` is False (the shipped
  default). The SPARQL property names are now `settings.route_property` /
  `settings.endpoint_property` instead of the hardcoded literals `route`/`endpoint`.
- `spec_globs(conn, paths, config, spec_id)` and `uncheckable(conn, paths, config)` — widened
  from `vocab` to `config` per C4; both now pass `config` straight through to
  `derived_globs`.
- `check(conn, paths, config, demote, code_repo=None)` — signature unchanged (already took
  `config`). Added the guard from the brief: raises `RuntimeError("no code repository
  configured — set repo.code_repo in knowledge.toml, or pass --code-repo")` when neither
  `code_repo` nor `config.code_repo` is set. Docstring now explains *why* (silent zero
  findings would be indistinguishable from "checked and found clean").
- Module docstring gained a paragraph pointing at `presets/nextjs.toml` and stating the
  off-by-default behavior explicitly.

`C:/Users/jesus/Documents/Proyectos/knowledge-template/src/knowledge/config.py`:

- `Dependencies.derives` docstring extended with the *why*: a project that hasn't configured
  `[dependencies]` should get no globs rather than a guessed pattern that might silently
  match the wrong thing, or nothing. (Not in the brief's "Files" list, but decision #3 in my
  task brief named this exact docstring, so I updated it.)

`C:/Users/jesus/Documents/Proyectos/knowledge-template/src/knowledge/cli.py`:

- `cmd_stale`: `deps.uncheckable(conn, paths, config.vocabulary)` →
  `deps.uncheckable(conn, paths, config)`.
- `cmd_dep`: `deps.derived_globs(paths, config.vocabulary, args.spec)` →
  `deps.derived_globs(paths, config, args.spec)`.
- `cmd_stale`'s call to `deps.check` was already `config`-shaped; untouched. It does not yet
  catch the new `RuntimeError` from the no-code-repo guard — that CLI-layer message is
  explicitly Task 8's job (ruling C5), not mine.

`C:/Users/jesus/Documents/Proyectos/knowledge-template/presets/nextjs.toml` — created verbatim
from the brief (comments preserved: the route-group and dynamic-segment reasoning). Confirmed
nothing in `src/` reads this file (`grep -rn "presets/nextjs.toml\|presets\b" src/` — no hits).

## Tests

`C:/Users/jesus/Documents/Proyectos/knowledge-template/tests/test_deps.py` — rewritten:

- Added verbatim from the brief: `test_route_glob_absorbs_the_configured_prefix`,
  `test_route_glob_replaces_dynamic_segments`, `test_route_glob_leaves_unabsorbed_prefixes_alone`,
  `test_endpoint_glob_tolerates_a_leading_method`, `test_a_different_framework_needs_no_code_change`,
  `test_derived_globs_are_empty_when_nothing_is_configured`.
- Removed the three tests exercising the old hardcoded, no-`settings`-argument
  `route_to_glob`/`endpoint_to_glob` (`test_route_to_glob_ignores_route_groups`,
  `test_route_to_glob_handles_a_dynamic_segment`, `test_endpoint_to_glob`) — superseded by the
  brief's replacements above.
- Updated the remaining call sites to the new signatures:
  `test_a_dynamic_glob_matches_a_real_nextjs_directory` and
  `test_an_endpoint_glob_matches_a_route_handler_directly_beneath_it` now build their globs via
  a module-level `NEXTJS = Dependencies(...)` constant (identical values to the brief's
  example); `test_derived_globs_come_from_the_specs_own_triples`,
  `test_manual_globs_are_added_to_derived_ones`, `test_uncheckable_lists_a_verified_spec_with_no_dependencies`,
  `test_uncheckable_excludes_a_spec_once_it_has_a_manual_glob` now pass `config` instead of
  `config.vocabulary` (the `repo`/`config` fixtures already carry Next.js-shaped
  `[dependencies]` via `conftest.py`'s `CONFIG_TOML`, so these needed no other change).
- The five `check()`-behavior tests built on `make_config()` (whose default
  `Dependencies()` is empty/off, matching the shipped-default philosophy) now do
  `replace(make_config(...), dependencies=NEXTJS)` so their route-derivation-dependent
  assertions keep exercising real behavior instead of degrading to vacuous truths. I did
  **not** change `make_config`'s own default in `conftest.py` — that file wasn't in this
  task's file list, and its empty-by-default `Dependencies()` is the correct off-by-default
  behavior; the brief's own `test_derived_globs_are_empty_when_nothing_is_configured` models
  exactly this "compose with `dataclasses.replace`" idiom for opting a test into derivation.
- Added one new test not in the brief's Step 1 block, required by decision #2/#3 in my task
  brief: `test_check_refuses_when_no_code_repository_is_configured` — asserts
  `deps.check(conn, repo, no_repo_config, demote=False)` raises `RuntimeError` matching
  `"no code repository configured"` when `config.code_repo` is `None` and no override is
  passed.

### RED (before implementation)

```
uv run pytest tests/test_deps.py -v
...
FAILED tests/test_deps.py::test_route_glob_absorbs_the_configured_prefix - TypeError: route_to_glob() takes 1 positional argument but 2 were given
FAILED tests/test_deps.py::test_route_glob_replaces_dynamic_segments
FAILED tests/test_deps.py::test_route_glob_leaves_unabsorbed_prefixes_alone
FAILED tests/test_deps.py::test_endpoint_glob_tolerates_a_leading_method
FAILED tests/test_deps.py::test_a_different_framework_needs_no_code_change
FAILED tests/test_deps.py::test_derived_globs_are_empty_when_nothing_is_configured
FAILED tests/test_deps.py::test_a_dynamic_glob_matches_a_real_nextjs_directory
FAILED tests/test_deps.py::test_an_endpoint_glob_matches_a_route_handler_directly_beneath_it
FAILED tests/test_deps.py::test_derived_globs_come_from_the_specs_own_triples
FAILED tests/test_deps.py::test_manual_globs_are_added_to_derived_ones - AttributeError: 'Config' object has no attribute 'prefix'
FAILED tests/test_deps.py::test_check_refuses_when_no_code_repository_is_configured - Failed: DID NOT RAISE <class 'RuntimeError'>
FAILED tests/test_deps.py::test_uncheckable_lists_a_verified_spec_with_no_dependencies - AttributeError: 'Config' object has no attribute 'prefix'
FAILED tests/test_deps.py::test_uncheckable_excludes_a_spec_once_it_has_a_manual_glob
======================== 13 failed, 6 passed in 2.00s =========================
```

All failures were for the expected reason: old `deps.py` signatures didn't accept the new
`settings`/`config` arguments, and `check()` had no guard yet.

### GREEN (after implementation)

```
uv run pytest tests/test_deps.py -v
...
======================== 19 passed in 1.88s ========================
```

### Full suite

```
uv run pytest -q
........................................................................ [ 42%]
........................................................................ [ 84%]
...........................                                              [100%]
171 passed in 7.68s
```

167 baseline − 3 removed + 7 added = 171. No warnings, no skips.

## Shipped default when `[dependencies]` is empty

`Dependencies()` with no fields set has `route_property=""`, `route_glob=""`,
`endpoint_property=""`, `endpoint_glob=""`. `Dependencies.derives` is then `False`.
`deps.derived_globs` checks this first and returns `set()` immediately without touching the
graph. `spec_globs` therefore falls back to `manual_globs(conn, spec_id)` only — exactly the
"manual globs only" fallback the task description specifies. Nothing guesses a pattern; a
project that hasn't configured `[dependencies]` gets zero derived globs, not a wrong one.

## Files changed

- `C:/Users/jesus/Documents/Proyectos/knowledge-template/src/knowledge/deps.py`
- `C:/Users/jesus/Documents/Proyectos/knowledge-template/src/knowledge/config.py`
- `C:/Users/jesus/Documents/Proyectos/knowledge-template/src/knowledge/cli.py`
- `C:/Users/jesus/Documents/Proyectos/knowledge-template/presets/nextjs.toml` (new)
- `C:/Users/jesus/Documents/Proyectos/knowledge-template/tests/test_deps.py`

## Self-review

- Diff for `deps.py` matches the brief's Step 3 code block and my task brief's C4 ruling
  exactly (route/endpoint property names sourced from `settings`, not hardcoded literals).
- No stray imports: removed `re` and `knowledge.vocab.Vocabulary` (both now unused in
  `deps.py`), added `knowledge.config.Dependencies` (used as a type hint in three
  functions). Verified via `ast.walk` that every import is referenced.
- `presets/nextjs.toml` is pure data: `grep -rn "presets"` across `src/` returns nothing — no
  code path reads it.
- LF line endings, no trailing whitespace, no CR — checked with `file` and `grep -n '\r\|
  $'` on every touched file.
- `cli.py` diff is a 2-line surgical change, nothing else touched.
- Did not touch `tests/conftest.py`, honoring the task's file list; instead composed
  `Dependencies` via `dataclasses.replace` at the call sites that needed derivation active,
  matching the idiom the brief's own Step-1 test uses.

## Concerns

1. **`_dynamic_delimiters` on a malformed `dynamic_segment` silently misbehaves rather than
   erroring.** I verified this directly (not fixed — the brief did not ask for validation,
   and my task brief explicitly told me to report rather than invent handling):
   - `dynamic_segment="star"` (no `"..."`) → `partition` gives `opening="star", closing=""`.
     `closing=""` makes `part.endswith(closing)` always `True`, so the check degrades to
     "does the segment start with `star`" — almost never true for real routes, so dynamic
     segments then go **undetected** (worse false negative, not a crash).
   - `dynamic_segment=""` → `opening="", closing=""`. Both `startswith("")` and
     `endswith("")` are always `True`, so **every** route segment is treated as dynamic and
     replaced by `dynamic_replacement`, silently corrupting every derived glob (route
     `/settings/profile` → `app/**/*/*`instead of `app/**/settings/profile/page.tsx`).
   Neither case raises. This is a real footgun for a project that mistypes
   `dynamic_segment` in `knowledge.toml`, but implementing validation for it is outside what
   Task 6 asked for — flagging for the controller to decide whether a later task (e.g. a
   `knowledge.toml` schema validator) should catch it.
2. `cmd_stale` in `cli.py` does not yet catch the new `RuntimeError` from `deps.check`'s
   no-code-repo guard — it will currently propagate as an unhandled traceback if a user runs
   `knowledge stale` with no `code_repo` configured and no `--code-repo` flag. This is
   intentional per ruling C5 (Task 8 owns the CLI-layer message); flagging so the controller
   confirms Task 8 is scheduled to close this gap before users see it.

---

## Fix round 1: validate `dynamic_segment` at load time

Ruling: concern (1) above was real and dangerous specifically for the `{}`-typo case (a
plausible mistake whose consequence — a glob that matches no file, forever — is invisible;
`stale` would report the spec "clean" when it was simply never checked). Ruling: validate in
`load_config`, not at derivation time, following the existing `publish.target` pattern
exactly. `<...>`, `[...]`, `:...` etc. must keep working — only a value with no `...` at all
is rejected.

### The validation

`C:/Users/jesus/Documents/Proyectos/knowledge-template/src/knowledge/config.py` — extracted
the inline `Dependencies(...)` construction out of `load_config` into a new `_dependencies(data)`
helper (mirroring `_publish(data)`), and added the check before construction:

```python
def _dependencies(data: dict) -> Dependencies:
    table = data.get("dependencies", {})
    dynamic_segment = _clean(table.get("dynamic_segment")) or "{...}"
    if "..." not in dynamic_segment:
        raise ConfigError(
            f"knowledge.toml: dependencies.dynamic_segment is {dynamic_segment!r};"
            " it must contain '...' to mark where the segment name goes (e.g. '{...}', '<...>')"
        )
    return Dependencies(
        route_property=_clean(table.get("route_property")),
        endpoint_property=_clean(table.get("endpoint_property")),
        route_glob=_clean(table.get("route_glob")),
        endpoint_glob=_clean(table.get("endpoint_glob")),
        absorbed_prefixes=tuple(table.get("absorbed_prefixes", ())),
        dynamic_segment=dynamic_segment,
        dynamic_replacement=_clean(table.get("dynamic_replacement")) or "*",
    )
```

`load_config` now calls `dependencies=_dependencies(data)` and no longer builds `Dependencies`
inline; the stray local `deps = data.get("dependencies", {})` was removed along with it.

The default (`"{...}"`, used when the key is absent) always contains `...`, so an unconfigured
`[dependencies]` table never trips this check — only an explicit, malformed value does.

### Tests

`C:/Users/jesus/Documents/Proyectos/knowledge-template/tests/test_config.py`, added beside
`test_unknown_publish_target_is_rejected`:

- `test_dynamic_segment_without_an_ellipsis_is_rejected` — `dynamic_segment = "{}"` raises
  `ConfigError` naming `dependencies.dynamic_segment` and quoting the bad value.
- `test_dynamic_segment_alternative_delimiters_are_accepted` (parametrized `<...>`, `[...]`)
  — both load fine and round-trip into `config.dependencies.dynamic_segment` unchanged.

RED (before the fix — `test_dynamic_segment_without_an_ellipsis_is_rejected` was the only new
test that could fail, since the other two describe already-working syntax):

```
tests/test_config.py::test_dynamic_segment_without_an_ellipsis_is_rejected FAILED
    Failed: DID NOT RAISE <class 'knowledge.config.ConfigError'>
1 failed, 8 passed in 0.16s
```

GREEN:

```
uv run pytest tests/test_config.py tests/test_deps.py -v
...
tests/test_config.py::test_dynamic_segment_without_an_ellipsis_is_rejected PASSED
tests/test_config.py::test_dynamic_segment_alternative_delimiters_are_accepted[<...>] PASSED
tests/test_config.py::test_dynamic_segment_alternative_delimiters_are_accepted[[...]] PASSED
============================= 28 passed in 1.95s ==============================
```

Full suite:

```
uv run pytest -q
........................................................................ [ 41%]
........................................................................ [ 82%]
..............................                                           [100%]
174 passed in 7.76s
```

174 passed (171 baseline from the main task + 3 new), no warnings, no skips.

### Commit

`c4cc611` — "fix: reject a dynamic_segment that cannot mark a segment"
(`src/knowledge/config.py`, `tests/test_config.py`; 2 files, 35 insertions, 10 deletions).

Concern (2) (`cmd_stale` not yet catching the no-code-repo `RuntimeError`) required no action
per the ruling — it is Task 8's.

---

## Fix round 2: validate glob templates at load time

Ruling: the same footgun `dynamic_segment` was validated for was still open in `route_glob`
and `endpoint_glob` — `str.replace` is a silent no-op when the token is absent, so a typo
like `route_glob = "app/page.tsx"` (missing `{segments}`) collapses every route to the same
literal glob, which matches no real file for most routes; `stale` then reports those specs
clean forever. Structurally the same failure as the `dynamic_segment` case (C16), just in a
sibling field. Extended `_dependencies` with two more checks, same shape as the
`dynamic_segment` one: a non-empty `route_glob` must contain `{segments}`, a non-empty
`endpoint_glob` must contain `{path}`. Empty stays legal — `derives` already gates on
exactly that, and the shipped default (derivation off) must keep loading with no
`[dependencies]` table at all.

### The validation

`C:/Users/jesus/Documents/Proyectos/knowledge-template/src/knowledge/config.py`,
`_dependencies`:

```python
    route_glob = _clean(table.get("route_glob"))
    if route_glob and "{segments}" not in route_glob:
        raise ConfigError(
            f"knowledge.toml: dependencies.route_glob is {route_glob!r};"
            " it must contain '{segments}' to mark where the route's path segments go"
        )
    endpoint_glob = _clean(table.get("endpoint_glob"))
    if endpoint_glob and "{path}" not in endpoint_glob:
        raise ConfigError(
            f"knowledge.toml: dependencies.endpoint_glob is {endpoint_glob!r};"
            " it must contain '{path}' to mark where the endpoint's path goes"
        )
```

`Dependencies(...)` now builds from the already-validated `route_glob`/`endpoint_glob`
locals instead of re-reading `table.get(...)` inline.

### Tests

`C:/Users/jesus/Documents/Proyectos/knowledge-template/tests/test_config.py`, added beside
the `dynamic_segment` tests:

- `test_route_glob_without_the_segments_token_is_rejected` — `route_glob = "app/page.tsx"`
  raises `ConfigError` naming `dependencies.route_glob` and quoting the bad value.
- `test_empty_route_glob_still_loads` — the `MINIMAL` fixture (no `[dependencies]` table at
  all) still loads, `config.dependencies.route_glob == ""`. Pins the ships-off-by-default
  behavior against an over-tight validation.
- `test_endpoint_glob_without_the_path_token_is_rejected` — parallel case for
  `endpoint_glob`/`{path}`.
- `test_empty_endpoint_glob_still_loads` — parallel empty-stays-legal case.

RED (before the fix):

```
tests/test_config.py::test_route_glob_without_the_segments_token_is_rejected FAILED
    Failed: DID NOT RAISE <class 'knowledge.config.ConfigError'>
tests/test_config.py::test_empty_route_glob_still_loads PASSED
tests/test_config.py::test_endpoint_glob_without_the_path_token_is_rejected FAILED
    Failed: DID NOT RAISE <class 'knowledge.config.ConfigError'>
tests/test_config.py::test_empty_endpoint_glob_still_loads PASSED
2 failed, 2 passed, 9 deselected in 0.13s
```

(The two "empty stays legal" tests were green from the start, as expected — they describe
behavior that was already correct and exist to guard against over-tightening.)

GREEN:

```
uv run pytest tests/test_config.py tests/test_deps.py -v
...
============================= 32 passed in 1.80s ==============================
```

Full suite:

```
uv run pytest -q
........................................................................ [ 40%]
........................................................................ [ 80%]
..................................                                       [100%]
178 passed in 7.14s
```

178 passed (174 baseline + 4 new), no warnings, no skips.

### Commit

`b3f8401` — "fix: reject a glob template that cannot substitute its segment"
(`src/knowledge/config.py`, `tests/test_config.py`; 2 files, 40 insertions, 2 deletions).

The Minor (dropped multi-segment endpoint case from the old `test_endpoint_to_glob`) was
explicitly deferred to final review — no action taken here.
