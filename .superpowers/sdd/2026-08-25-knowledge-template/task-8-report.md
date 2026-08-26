# Task 8 report — Finish the CLI's generic surface

Work done in `C:/Users/jesus/Documents/Proyectos/knowledge-template`. Commit `d2d4c16`
("feat: remove the last project-specific strings from the CLI").

## What I implemented

1. **`main_argv(argv: Sequence[str] | None = None) -> int`** in `src/knowledge/cli.py`,
   split out of `main()` exactly as the brief specifies: builds the parser, parses `argv`,
   dispatches to the handler, and catches `(RuntimeError, ConfigError)` around the handler
   call, printing `error: <message>` to stderr and returning 1. `main()` is now
   `return main_argv()`. `ConfigError` is imported from `knowledge.config` (it already
   subclasses `RuntimeError`, so the extra name in the except tuple is redundant but matches
   the brief's snippet verbatim, and is harmless).
2. **Parser description** changed to `"Author, track and publish a knowledge base."`
   (dropped "a project's").
3. **`src/knowledge/__init__.py`** docstring changed to
   `"""Authoring, tracking and publishing for a knowledge base."""`.
4. **`cmd_stale` guard**: before calling `deps.check`, if `config.code_repo is None and not
   getattr(args, "code_repo", None)`, prints the brief's message to stderr and returns 1.
   Commented why this duplicates `deps.check`'s own `RuntimeError` (ruling C5 in the task
   context): that message is written for library callers, this one is `stale`'s own clean,
   dedicated output, not a message borrowed via exception propagation.
5. **`cmd_dep` guard**: added to the `add` branch only (see below), same condition, same
   message, same early return, placed before the spec-exists check and the DB insert so it
   fails before doing any work.

## Which `cmd_dep` subcommands I guarded, and why

Read `cmd_dep` before deciding. Only **`add`** consults the code repository — it calls
`deps.tracked_files(config.code_repo)` after inserting the dependency, to warn if the new
glob matches nothing. **`list`** only reads the RDF graph (`derived_globs`) and the database
(`manual_globs`) — no git call. **`remove`** only deletes a database row — no git call
either. So I guarded `add` and left `list`/`remove` untouched.

I verified this mattered, not just in theory: before the guard, running `dep add` against a
repo with `code_repo = ""` did **not** fail — it inserted the dependency, then
`deps.tracked_files(None)` ran `git -C None ls-files`, which git rejected (exit 128), and the
existing `except subprocess.CalledProcessError` in that branch swallowed it into a
misleading warning:
`warning: could not check the code repository (Command '['git', '-C', 'None', 'ls-files']' returned non-zero exit status 128.)`
— while still committing the (unchecked) dependency to the database. The new guard replaces
that with the clean early failure and leaves the database untouched (asserted in the test).

## TDD evidence

**RED** — `uv run pytest tests/test_cli_read.py -k "stale_without_a_configured or description_names_no_project" -v`:
```
tests/test_cli_read.py::test_stale_without_a_configured_code_repo_fails_clearly FAILED
    AttributeError: module 'knowledge.cli' has no attribute 'main_argv'
tests/test_cli_read.py::test_the_parser_description_names_no_project FAILED
    AssertionError: assert 'Author, track and publish a knowledge base.' in
    "...Author, track and publish a project's knowledge base...."
2 failed, 16 deselected
```

**RED** — `uv run pytest tests/test_cli_deps.py -k "without_a_configured_code_repo or list_works_without" -v`:
```
tests/test_cli_deps.py::test_dep_add_without_a_configured_code_repo_fails_clearly FAILED
    AssertionError: assert 0 == 1
    Captured stdout: assets now depends on app/**/assets/page.tsx
      warning: could not check the code repository (Command '['git', '-C', 'None', 'ls-files']' returned non-zero exit status 128.)
tests/test_cli_deps.py::test_dep_list_works_without_a_configured_code_repo PASSED
1 failed, 1 passed
```
(`dep list` already worked without a code repo — confirming it needed no guard, and giving
this test a real chance to fail if I over-guarded later.)

**GREEN** — after implementation, same two runs plus the full read/deps files:
`uv run pytest tests/test_cli_read.py tests/test_cli_deps.py -v` → **28 passed**.

**Full suite** — `uv run pytest`: **193 passed** (189 baseline + 4 new tests: the brief's
2 in `test_cli_read.py`, my 2 in `test_cli_deps.py`), no warnings, no skips.

## Step 4 sweep

`rg -i 'monicords|mon:|https://monicords' src/ tests/`:
```
tests/test_cli_read.py:    assert "monicords" not in text.lower()
tests/test_cli_read.py:    # A description that only avoids the string "monicords" would still pass for any other
```
Both hits are inside the test I just added (the brief's own `test_the_parser_description_names_no_project`
plus my strengthening comment) — the literal string being asserted *absent* from CLI output,
not a leftover project-naming string. No hits in any non-test source. Confirms the brief's
claim: Task 7 already closed this constraint; nothing to fix.

## `graph.py`'s `broken_links` docstring — no change made

The brief lists `src/knowledge/graph.py` (`broken_links` docstring) as a file to modify. I
read the function and its docstring:
```python
def broken_links(paths: Paths, ids: Sequence[str]) -> list[str]:
    """Links in prose point at wiki page names, which are derived from spec ids."""
```
This is already fully generic — no project name, no monicords-specific wording. I diffed it
against the read-only reference at
`C:/Users/jesus/Documents/Proyectos/monicords-knowledge/src/knowledge/graph.py`: the
docstring text is byte-identical in both; the only differences in the file are the
vocabulary-injection changes from earlier tasks (`vocab.prefix`/`vocab.namespace` instead of
hardcoded `MON`/`APP`, `run_query(g, vocab, sparql)`, etc.), all already done. I made no
change to this file — like Step 4, this line item appears to already be satisfied by prior
tasks. Flagging this explicitly per the instruction to say so rather than silently doing
nothing.

## Files changed

- `src/knowledge/cli.py` — `main_argv`/`main` split, `ConfigError` import and catch,
  generic parser description, `cmd_stale` and `cmd_dep`(`add`) guards with rationale
  comments.
- `src/knowledge/__init__.py` — generic package docstring.
- `tests/test_cli_read.py` — the brief's two Step-1 tests, appended verbatim, plus the
  strengthened assertion on the exact description text (with a comment explaining why the
  brief's bare `"monicords" not in text` was a weak assertion).
- `tests/test_cli_deps.py` — two new tests: `dep add` fails clearly without a configured
  code repo (and leaves the database untouched), `dep list` keeps working without one.
- `src/knowledge/graph.py` — not modified (see above).

## Self-review

- Diff is scoped to exactly what the brief and the decision notes asked for; no unrelated
  cleanup, no speculative refactors.
- Both new guards carry a comment explaining *why* the duplication with `deps.check` (for
  `stale`) and the pre-`deps.tracked_files` failure (for `dep add`) exist, per the
  `restated_rule_comments` house style — not just restating what the code does.
- `test_the_parser_description_names_no_project` now pins the exact generic string, so it
  cannot pass merely because some other project's name happens not to be "monicords" — it
  was demonstrably able to fail (RED evidence above) before the description text was fixed.
- `test_dep_list_works_without_a_configured_code_repo` gave the `add`-only guard placement
  a genuine chance to fail if I had guarded the whole `cmd_dep` function instead of just the
  `add` branch — it passed both before and after my change, confirming `list` was never at
  risk and stays that way.
- Checked for trailing whitespace (none) and CRLF (none — all four changed files are
  LF-only) in the changed files.
- `except (RuntimeError, ConfigError)` in `main_argv` is redundant given `ConfigError(RuntimeError)`,
  but I kept it as the brief specifies verbatim rather than "improving" it to
  `except RuntimeError` — not my call to make silently in a task about following a brief
  exactly.
- No `--code-repo` CLI flag exists for `dep`, so `getattr(args, "code_repo", None)` in that
  guard is always `None` there; kept it anyway since it's the same reusable guard shape the
  brief shows for `stale` (which does have the flag), and it costs nothing.

## Concerns

- None blocking. The one thing worth the controller's attention: the `graph.py` file-list
  entry appears to be a no-op like Step 4 was flagged as being — I verified this by diffing
  against the read-only reference rather than assuming, but wanted it visible rather than
  silently skipped.

---

## Fix round 1 — dropped `cmd_stale`'s guard (commit `e7f8443`)

The coordinator's review found `test_stale_without_a_configured_code_repo_fails_clearly`
could not fail for the reason it was named after: `deps.check` already raises `RuntimeError`
with the byte-identical message, `main_argv` already catches and prints it, so deleting
`cmd_stale`'s guard left the test passing unchanged. Ruling C5 (keep both guards) was wrong
for `cmd_stale` — there is no distinguishing behavior it adds, unlike `cmd_dep add`'s guard,
which is load-bearing because it prevents a database row being inserted before the git
validation fails (an observable side effect the existing test already asserts).

### What I removed

Deleted the guard block and its comment from `cmd_stale` in `src/knowledge/cli.py` — the
`if config.code_repo is None and not getattr(...)` check, its print, and its `return 1`.
`cmd_stale` now goes straight from `from knowledge import deps` to
`override = Path(args.code_repo).resolve() if args.code_repo else None`, i.e. back to
relying entirely on `deps.check`'s own `RuntimeError`, caught by `main_argv`.

`cmd_dep add`'s guard is untouched — it stays exactly as committed in the first round.

### Rewritten test

`test_stale_without_a_configured_code_repo_fails_clearly` →
`test_stale_surfaces_deps_checks_missing_code_repo_error` in `tests/test_cli_read.py`:

```python
def test_stale_surfaces_deps_checks_missing_code_repo_error(repo, capsys, monkeypatch):
    """cmd_stale has no guard of its own for this — deps.check raises RuntimeError when
    neither config.code_repo nor --code-repo is set, and main_argv's except clause turns
    that into the "error: ..." line asserted below. Delete deps.check's own
    `if root is None: raise` and this fails (exit 0, "nothing has gone stale" instead),
    which is what makes this test genuinely test that guard rather than duplicate one in
    the CLI layer that would pass identically either way."""
    from knowledge import cli
    (repo.root / "knowledge.toml").write_text(
        (repo.root / "knowledge.toml").read_text(encoding="utf-8").replace(
            'code_repo = "../code"', 'code_repo = ""'
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(repo.root)
    assert cli.main_argv(["stale"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    assert "no code repository configured" in err
```

Renamed for what it actually tests (surfacing `deps.check`'s error through `main_argv`, not
a CLI-layer guard that no longer exists), and now asserts the `error: ` prefix that proves
the message arrives via `main_argv`'s exception handler rather than a direct `print`.

### Discrimination evidence

Temporarily replaced `deps.check`'s guard in `src/knowledge/deps.py` (lines 138-142):

```python
    if root is None:
        raise RuntimeError(
            "no code repository configured — set repo.code_repo in knowledge.toml,"
            " or pass --code-repo"
        )
```

with a disabled no-op (`if False: raise RuntimeError('unreachable')`), then ran the test:

```
$ uv run pytest tests/test_cli_read.py -k "test_stale_surfaces_deps_checks_missing_code_repo_error" -v
...
tests/test_cli_read.py::test_stale_surfaces_deps_checks_missing_code_repo_error FAILED

>       assert cli.main_argv(["stale"]) == 1
E       AssertionError: assert 0 == 1
E        +  where 0 = <function main_argv at 0x...>(['stale'])

Captured stdout call
nothing has gone stale
1 failed, 17 deselected in 0.11s
```

Exit code flips to 0 and the output becomes the false-confidence "nothing has gone stale"
(exactly the failure mode `deps.check`'s own docstring warns against), instead of the
error — confirming the test genuinely exercises that guard. Restored `deps.py` verbatim
(`git diff src/knowledge/deps.py` showed no diff after restoring) and reran:

```
$ uv run pytest tests/test_cli_read.py -k "test_stale_surfaces_deps_checks_missing_code_repo_error" -v
...
tests/test_cli_read.py::test_stale_surfaces_deps_checks_missing_code_repo_error PASSED
1 passed, 17 deselected in 0.05s
```

### Full verification

```
$ uv run pytest tests/test_cli_read.py tests/test_cli_deps.py -v
... 28 passed in 2.57s

$ uv run pytest
... 193 passed in 7.61s
```

193 passed, unchanged count from before the fix (one test renamed/rewritten, none
added/removed), no warnings, no skips.

### Commit

`e7f8443` — "fix: drop the stale guard that duplicated deps.check's message verbatim"
(`src/knowledge/cli.py`: -14/+0 net removal of the guard; `tests/test_cli_read.py`:
rewritten test). `src/knowledge/deps.py` is untouched in the final diff — confirmed via
`git status`/`git diff` after restoring the temporary edit.

### Remaining concern

None new. The reviewer's Minor about `except (RuntimeError, ConfigError)` in `main_argv`
being redundant (`ConfigError` already subclasses `RuntimeError`) is left as-is per the
coordinator's explicit instruction to defer it to final review.
