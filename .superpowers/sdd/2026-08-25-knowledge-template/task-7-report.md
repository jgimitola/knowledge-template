# Task 7 report: Configure publishing

## Status: DONE

## What was implemented

Worked in `C:/Users/jesus/Documents/Proyectos/knowledge-template` (the read-only
`monicords-knowledge` repo was only read for reference, never written to — this report is
the one exception, written to the gitignored `.superpowers/` folder per the established
per-task reporting convention, confirmed via `git check-ignore`).

### `src/knowledge/publish.py`

- Deleted the seven module-level constants (`SIDEBAR_ORDER`, `SIDEBAR_REFERENCE`,
  `SIDEBAR_LABELS`, `SIDEBAR_HEADER_BEFORE`, `NESTED_UNDER`, `BOT_NAME`, `BOT_EMAIL`).
- `render_sidebar(conn, sidebar: Sidebar) -> str` — reads all the structure (title, order,
  reference, nested_under, header_before, labels) from the passed `Sidebar`, exactly as
  given in the brief.
- `write_pages(conn, paths, out_dir, sidebar: Sidebar) -> list[str]` — gained the `sidebar`
  parameter, passes it through to `render_sidebar`.
- `push(out_dir, remote, message, committer_name: str, committer_email: str) -> bool` —
  gained the two committer parameters in place of the deleted `BOT_NAME`/`BOT_EMAIL`
  constants; used for `git config user.name`/`user.email`.
- `strip_frontmatter`, `_spec_directory`, `render_page`, `_published` unchanged.
- Module docstring: replaced the `mon:Actor` / "product" wording (vestigial monicords
  vocabulary reference) with generic language about "whatever vocabulary declarations its
  own spec.ttl holds" — this file no longer names anything project-specific.

### `src/knowledge/cli.py` (`cmd_publish`)

Added a target dispatch at the top of `cmd_publish`, before the existing `--dry-run` check:

- `target == "none"` (the shipped default): prints an actionable stderr message —
  `"publishing is not configured — set publish.target in knowledge.toml to 'directory' or
  'github-wiki'"` — and returns 1. A comment directly above it states why "none" defaults:
  *"A freshly-templated repository has no wiki, no publish directory — nothing this tooling
  could safely guess — so it refuses to publish rather than picking a destination... that the
  project never asked for."* This follows the `restated_rule_comments`-style convention: the
  *reason*, not a restatement of the code.
- `target == "directory"`: resolves `out_dir` from `args.out_dir or config.publish.out_dir`,
  fails cleanly (stderr, exit 1) if both are empty, otherwise calls
  `publish.write_pages(conn, paths, out_dir, config.publish.sidebar)` and reports
  `"{n} page(s) written to {out_dir}"` — an honest count, never a phrase like "current" or
  "up to date" that a reader could mistake for confirmation the destination is in sync (per
  decision #3 in the task instructions).
- `target == "github-wiki"` (or any other already-validated value): falls through unchanged
  into the existing `--dry-run` / clone-and-push flow, now passing
  `config.publish.sidebar` into both `write_pages` calls and
  `config.publish.committer_name` / `.committer_email` into `push`.
- Added a new `--out-dir` CLI flag to the `publish` subparser (distinct from the pre-existing
  `-o/--output`, which is `--dry-run`'s own output flag) so a directory-target publish can be
  redirected from the command line without touching `knowledge.toml`.

### The `if not str(out_dir):` bug (flagged in the task instructions)

The brief's snippet checked emptiness *after* wrapping the value in `Path(...)`. That can
never fire: `Path("")` normalises to `Path(".")`, and `str(Path("."))` is `"."` — truthy.
I fixed this by checking the **raw string** before constructing the `Path`:

```python
raw_out_dir = args.out_dir or config.publish.out_dir
if not raw_out_dir:
    print("publish.out_dir is required when publish.target is 'directory'", file=sys.stderr)
    return 1
out_dir = Path(raw_out_dir)
```

Added a regression test for this specific trap:
`test_publish_directory_target_without_an_out_dir_fails_cleanly` — its docstring explains the
`Path("")` → `"."` normalisation directly, so a future reader doesn't reintroduce the bug by
"simplifying" the check back to `if not str(out_dir):`.

### Tests

`tests/conftest.py`:
- Added the `seeded_conn` fixture exactly as given in the brief.
- `KNOWLEDGE_TOML` / `write_knowledge_toml` gained `target` (default `"github-wiki"`, to
  preserve every existing caller's behaviour) and `out_dir` (default `""`) parameters, needed
  so `test_cli_publish.py` could construct `none` and `directory`-target configs without a
  duplicate template. Existing callers (`test_cli_deps.py`, `test_cli_write.py`) don't pass
  these, so their behaviour is unchanged.

`tests/test_publish.py`:
- Added the four brief-specified tests exercising `render_sidebar` directly via `seeded_conn`
  (configured title/order, alphabetical fallback, nesting/headers, and the empty-config
  flat-alphabetical pin).
- Updated every pre-existing `write_pages(conn, repo, tmp_path)` call to pass an explicit
  `Sidebar(...)` fourth argument (now required, no default — matching the brief's signature).
- `test_the_sidebar_labels_home_as_home_not_its_page_title` (containing the flagged
  `# Monicords` / `[Monicords](Home)` strings) was renamed to
  `test_the_sidebar_labels_home_using_the_configured_override`: the spec's H1 is now `#
  Example` (this fixture tree's project name, matching `CONFIG_TOML`'s `[project] name =
  "Example"`) and the label override is passed explicitly as
  `Sidebar(labels={"home": "Home"})` instead of coming from a hardcoded module constant. Same
  behaviour under test — a configured label wins over the spec's own title — with no
  project-specific string.
- `test_the_reference_section_files_architecture_after_ontology` now passes
  `Sidebar(reference=("architecture",))` explicitly instead of relying on the deleted
  `SIDEBAR_REFERENCE` constant.

`tests/test_cli_publish.py` — the brief didn't supply CLI test code (only the `cmd_publish`
implementation pseudocode), so I wrote four new tests following the existing file's pattern,
covering the behaviour the brief's pseudocode specifies:
- `test_publish_target_none_fails_with_a_readable_message_instead_of_a_traceback`
- `test_publish_directory_target_writes_pages_without_pushing`
- `test_publish_directory_target_out_dir_flag_overrides_the_config`
- `test_publish_directory_target_without_an_out_dir_fails_cleanly` (the `Path("")` regression
  guard described above)

## TDD evidence

**RED** — `uv run pytest tests/test_publish.py -v` before any implementation change:

```
FAILED tests/test_publish.py::test_write_pages_names_files_by_wiki_page - TypeError: write_pages() takes 3 positional arguments but 4 were given
...
FAILED tests/test_publish.py::test_sidebar_uses_the_configured_title_and_order - TypeError: render_sidebar() takes 1 positional argument but 2 were given
...
11 failed, 2 passed in 0.42s
```

Matches the brief's predicted failure exactly ("`render_sidebar()` takes 1 positional
argument but 2 were given").

**RED** — `uv run pytest tests/test_cli_publish.py -v` before `cmd_publish` was touched:

```
FAILED tests/test_cli_publish.py::test_publish_target_none_fails_with_a_readable_message_instead_of_a_traceback
  AssertionError: assert 'publish.target' in ''
FAILED tests/test_cli_publish.py::test_publish_directory_target_writes_pages_without_pushing
  assert 1 == 0   (fell through to the old clone-and-push path, which failed against a nonexistent remote)
FAILED tests/test_cli_publish.py::test_publish_directory_target_out_dir_flag_overrides_the_config
  SystemExit: 2   (argparse: unrecognized arguments: --out-dir ...)
FAILED tests/test_cli_publish.py::test_publish_directory_target_without_an_out_dir_fails_cleanly
  AssertionError: assert 'publish.out_dir is required' in ''
4 failed, 5 passed in 1.62s
```

Each failure is for the right reason: no target dispatch existed yet, and `--out-dir` wasn't
a registered flag.

**GREEN** — after implementing `publish.py` and `cli.py`:

```
uv run pytest tests/test_publish.py tests/test_cli_publish.py -v
...
22 passed in 0.76s
```

**GREEN — full suite:**

```
uv run pytest -q
........................................................................ [ 38%]
........................................................................ [ 77%]
..........................................                               [100%]
186 passed in 7.53s
```

(178 baseline + 4 new `render_sidebar`/`write_pages` behaviour tests in test_publish.py +
4 new CLI dispatch tests = 186; no warnings, no skips.)

## monicords grep (the constraint this task closes)

```
$ grep -rni "monicords" src/ tests/ --include=*.py
$ echo $?
1
```

(Also ran without `--include` and piped through `grep -v __pycache__`: same empty result,
exit 1 — no matches.)

## Files changed

- `C:/Users/jesus/Documents/Proyectos/knowledge-template/src/knowledge/publish.py`
- `C:/Users/jesus/Documents/Proyectos/knowledge-template/src/knowledge/cli.py`
- `C:/Users/jesus/Documents/Proyectos/knowledge-template/tests/conftest.py`
- `C:/Users/jesus/Documents/Proyectos/knowledge-template/tests/test_publish.py`
- `C:/Users/jesus/Documents/Proyectos/knowledge-template/tests/test_cli_publish.py`

Commit: `9118e93` — "feat: configure the sidebar and the publishing target"

## Self-review findings

- Verified LF-only line endings and no trailing whitespace on every edited file (manual
  `grep -n ' $'` and a byte-level `b'\r' in data` check — no pre-commit hook enforces this
  for Python files here, only prettier for markdown/yaml).
- Confirmed `write_pages`/`render_sidebar`/`push` signatures match the brief's Interfaces
  section verbatim.
- Confirmed no circular import: `knowledge.config` doesn't import `knowledge.publish`, so
  `from knowledge.config import Sidebar` in `publish.py` is safe.
- Confirmed the "none" gate sits *before* the `--dry-run` check (per the brief's "at the top
  of cmd_publish" placement) — meaning `--dry-run` also requires a configured target now.
  This is a real behavioural narrowing versus the old code (where `--dry-run` needed no
  config at all), but it's consistent with the brief's literal ordering and with decision #2:
  dry-run's purpose is previewing a real publish, and there's no real publish to preview when
  nothing is configured. Flagging this as a judgment call rather than hiding it.
- Confirmed the shipped-default empty-sidebar test
  (`test_an_empty_sidebar_config_renders_every_spec_flat_and_alphabetical`) passes against
  the real implementation, not just a hand-verified assertion.
- No overbuilding: did not add `_clear_markdown`-style stale-file removal to the `directory`
  target — the brief's given code doesn't call it, and repeated `directory` publishes
  accumulating old pages is a real but separate concern I didn't invent a fix for.
- Did not touch `config.py` — it already had everything this task consumes (`Publish`,
  `Sidebar`, `TARGETS` validation), as the brief's Interfaces section stated.

## Concerns

- The `directory` target does not clear stale pages between runs (see self-review above) —
  unlike the `--dry-run` and `github-wiki` paths, which both call `_clear_markdown` first. If
  a later task wants directory-target parity with those two, that's a small, separate follow-up.
- I made a judgment call giving `--dry-run` a hard dependency on `publish.target` being
  configured, per the brief's literal code placement. If this repo's intent was for
  `--dry-run` to remain usable with zero `knowledge.toml` publish configuration (a "preview
  before you even decide where to publish" use case), that would require moving the `none`
  check below the `--dry-run` branch — flagging this in case that's not the intended behaviour.

---

## Fix round 1

The coordinator's review confirmed both concerns above were real, and found a third I had
missed: with the dispatch order `none` → `directory` → `dry_run` → `github-wiki`, a
`--dry-run` publish under `target = "directory"` fell into the `directory` branch (which
returns before the `dry_run` check is ever reached) and silently performed a **real** write
to `out_dir` — no stale-clearing, no per-page listing, and no indication the flag had been
ignored. Same family of problem as (a) `--dry-run` erroring under `target = "none"` and (c)
the `directory` branch never clearing stale pages: output/behaviour not living up to what a
reader or a flag promised.

**Ruling applied:** separate rendering from publishing. `--dry-run` is not a mode of
publishing, it is the thing done *instead* of publishing, so it has to run before any target
dispatch at all — unconditionally, including under `target = "none"`.

### New ordering in `cmd_publish` (`src/knowledge/cli.py`)

1. `if args.dry_run:` — moved to the very top of the dispatch, right after `open_repo`/the
   `publish` import. Runs unconditionally, regardless of `publish.target`. Behaviour
   unchanged from before: default `paths.root / "build" / "wiki"` when `-o` isn't given,
   `_clear_markdown` first, `write_pages`, the `{n} page(s) written to {out}` line, the
   per-page listing (`for name in sorted(written): print("   ", name)` — 4 leading spaces
   after `print`'s default separator, verified empirically), then the stale-removal report.
2. `target = config.publish.target; if target == "none":` — now runs only once `--dry-run`
   has had first refusal, so it guards a real publish only. Adjusted the comment: *"'none' is
   the shipped default, and it guards only a real publish — --dry-run above already handles
   the 'just show me' case regardless of this."* The rest of the original reasoning (a fresh
   template can't safely guess a destination) is unchanged and still accurate.
3. `if target == "directory":` — now also clears stale pages, mirroring the dry-run and
   github-wiki paths: `out_dir.mkdir(...)` then `existing = set(_clear_markdown(out_dir))`
   *before* `write_pages`, then the same `stale = sorted(existing - set(written))` /
   `"{n} stale page(s) removed: ..."` report dry-run uses — same wording, so the two reports
   read consistently. (I did not add the per-page listing dry-run does; the ruling asked only
   for stale-clearing and a consistent removal report, and the per-page listing wasn't part
   of the original brief's directory pseudocode either — kept the diff to what was asked.)
4. The `github-wiki` clone-and-push flow is unchanged, now simply reached after `none` and
   `directory` have been ruled out.

### Three new pinning tests (`tests/test_cli_publish.py`)

- `test_dry_run_succeeds_when_publish_target_is_none` — `target = "none"`, `--dry-run -o
  <path>`: exit 0, `Assets.md` written. Pins fix (a).
- `test_dry_run_takes_the_dry_run_path_even_under_a_directory_target` — `target =
  "directory"` with its own configured `out_dir`, then `--dry-run -o <preview>`: asserts the
  preview path got the pages, the *configured* `out_dir` was never created
  (`assert not configured.exists()`), and — the distinguishing signal — the dry-run path's
  per-page listing line (`"    Assets.md"`, 4 leading spaces) is present in stdout. The
  directory branch never prints that listing, so its presence is direct proof `--dry-run`
  took the dry-run branch rather than being silently swallowed by the directory branch. Pins
  fix (b).
- `test_publish_directory_target_removes_a_page_whose_spec_is_gone` — pre-seeds `out_dir`
  with a stale `Old-Name.md`, runs a real (non-dry-run) `directory` publish, asserts the stale
  file is gone and `"stale page(s) removed: Old-Name.md"` is printed — same wording
  `test_dry_run_removes_a_stale_page_before_writing` already pins for the dry-run path. Pins
  fix (c).

### Commands and output

```
$ uv run pytest tests/test_cli_publish.py tests/test_publish.py -v
...
25 passed in 0.88s
```

```
$ uv run pytest -q
........................................................................ [ 38%]
........................................................................ [ 76%]
.............................................                            [100%]
189 passed in 7.49s
```

No warnings, no skips (checked via `pytest -q 2>&1 | grep -i "warn\|skip"` → no matches).
189 = 186 (post-round-0) + 3 new tests above, as the coordinator's "expect 189+, pristine"
predicted.

Re-verified LF-only / no trailing whitespace on both changed files, and re-ran the
`monicords` grep constraint — still clean:

```
$ grep -rni "monicords" src/ tests/ 2>&1 | grep -v "__pycache__"
$ echo $?
1
```

### Files changed (this round)

- `C:/Users/jesus/Documents/Proyectos/knowledge-template/src/knowledge/cli.py`
- `C:/Users/jesus/Documents/Proyectos/knowledge-template/tests/test_cli_publish.py`

Commit: `7169aed` — "fix: render with --dry-run regardless of target, and clear stale pages
in a directory publish"

## Status after fix round 1: DONE

---

## Fix round 2

**Important finding from task review:** the `dry_run` and `directory` branches in
`cmd_publish` had drifted into two near-verbatim copies of the same six-step sequence
(`mkdir` → `_clear_markdown` → `write_pages` → print written count → compute stale →
print stale removals), differing only in the destination variable and dry-run's per-page
listing. Fix round 1 existed specifically because these two blocks had already diverged once
(the directory branch was missing the clear-and-report half). Left as two copies, the next
change to the stale-removal wording or the clear/write sequence has to be made twice, with
nothing enforcing that it's made in both places.

Two Minors were flagged and explicitly deferred by the coordinator to final review (not
touched here):
- `--dry-run` combined with `--out-dir` silently ignores `--out-dir` (dry-run reads
  `args.output` only).
- The directory branch has no per-page listing (dry-run does). The new `list_pages`
  parameter makes this a one-line change later if the two are ever meant to be symmetric.

Also noted for the record: the coordinator independently verified `Sidebar()`'s defaults
(`''`, `()`, `()`, `{}`, `{}`, `{}`) are all empty collections, never `None`, so
`render_sidebar`'s `.get()`/`in` calls on them are safe — no action needed on my end.

### The helper (`src/knowledge/cli.py`)

Added a module-level `_render_to`, placed directly after `_clear_markdown` (its sibling in
spirit — both exist so two callers can't diverge on a step that must not diverge):

```python
def _render_to(conn, paths: Paths, out_dir: Path, sidebar: Sidebar, *, list_pages: bool) -> int:
    """Render every published spec into out_dir, clearing pages that no longer have a spec.

    Shared by --dry-run and the directory target: both render locally and push nothing, so
    a difference between them could only ever be a bug — round 1 of this task's review found
    exactly that, when the directory target was missing the clear-and-report half dry-run
    already had. One implementation means there is nothing left to keep in sync by hand.
    """
    from knowledge import publish

    out_dir.mkdir(parents=True, exist_ok=True)
    existing = set(_clear_markdown(out_dir))
    written = publish.write_pages(conn, paths, out_dir, sidebar)
    print(f"{len(written)} page(s) written to {out_dir}")
    if list_pages:
        for name in sorted(written):
            print("   ", name)
    stale = sorted(existing - set(written))
    if stale:
        print(f"{len(stale)} stale page(s) removed: {', '.join(stale)}")
    return 0
```

`from knowledge import publish` is a local import inside `_render_to`, matching the existing
lazy-import convention `cmd_publish` already used for the same module (kept rather than
promoted to a top-level import, since that convention predates this task and wasn't part of
the ask). Added `Sidebar` to the existing `from knowledge.config import Config, load_config`
line at the top of the file so the parameter could be properly typed.

### The two call sites

Dry-run (`list_pages=True`, preserving its per-page listing):

```python
    if args.dry_run:
        out = Path(args.output) if args.output else paths.root / "build" / "wiki"
        return _render_to(conn, paths, out, config.publish.sidebar, list_pages=True)
```

Directory target (`list_pages=False`, the Minor the coordinator deferred):

```python
    if target == "directory":
        raw_out_dir = args.out_dir or config.publish.out_dir
        if not raw_out_dir:
            print(
                "publish.out_dir is required when publish.target is 'directory'",
                file=sys.stderr,
            )
            return 1
        return _render_to(
            conn, paths, Path(raw_out_dir), config.publish.sidebar, list_pages=False
        )
```

The `none` gate and the `github-wiki` clone-and-push flow are untouched — `_render_to` only
replaces the two branches that render-without-pushing.

### Tests: confirmed unchanged

Per instruction, I did not touch any test to make it pass — `git diff --stat` for this round
shows only `src/knowledge/cli.py` changed:

```
$ git diff --stat
 src/knowledge/cli.py | 51 ++++++++++++++++++++++++++++-----------------------
 1 file changed, 28 insertions(+), 23 deletions(-)
```

All the round-1 pinning tests, including
`test_dry_run_takes_the_dry_run_path_even_under_a_directory_target` (the one most sensitive
to this refactor, since it distinguishes the two branches by the presence/absence of the
per-page listing) and `test_publish_directory_target_removes_a_page_whose_spec_is_gone`,
pass unmodified against the refactored code — confirming the refactor is behaviour-preserving.

### Commands and output

```
$ uv run pytest tests/test_cli_publish.py tests/test_publish.py -v
...
25 passed in 0.86s
```

```
$ uv run pytest -q
........................................................................ [ 38%]
........................................................................ [ 76%]
.............................................                            [100%]
189 passed in 7.51s
```

189 — unchanged from fix round 1, as expected for a pure refactor. No warnings, no skips
(`pytest -q 2>&1 | grep -i "warn\|skip"` → no matches). Re-checked LF-only / no trailing
whitespace on `cli.py`.

### Files changed (this round)

- `C:/Users/jesus/Documents/Proyectos/knowledge-template/src/knowledge/cli.py`

Commit: `7ab0b21` — "refactor: share one render-to-directory path between dry-run and the
directory target"

## Status after fix round 2: DONE
