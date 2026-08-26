### Task 8: Finish the CLI's generic surface

Everything left in `cli.py` that names monicords, plus readable failures for the commands whose configuration is empty.

**Files:**

- Modify: `src/knowledge/cli.py`
- Modify: `src/knowledge/__init__.py`
- Modify: `src/knowledge/graph.py` (`broken_links` docstring)
- Test: `tests/test_cli_read.py`

**Interfaces:**

- Consumes: everything from Tasks 2–7.
- Produces: no new API; `cmd_stale` and `cmd_dep` exit 1 with a message when `config.code_repo is None`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli_read.py`:

```python
def test_stale_without_a_configured_code_repo_fails_clearly(repo, capsys, monkeypatch):
    from knowledge import cli
    (repo.root / "knowledge.toml").write_text(
        (repo.root / "knowledge.toml").read_text(encoding="utf-8").replace(
            'code_repo = "../code"', 'code_repo = ""'
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(repo.root)
    assert cli.main_argv(["stale"]) == 1
    assert "no code repository configured" in capsys.readouterr().err


def test_the_parser_description_names_no_project(capsys):
    from knowledge import cli
    text = cli.build_parser().format_help()
    assert "monicords" not in text.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_cli_read.py -v`
Expected: FAIL — `cli.main_argv` does not exist, and the description still says "monicords".

- [ ] **Step 3: Make the CLI testable and generic**

Split `main` so tests can drive it without `sys.argv`:

```python
def main_argv(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.handler is None:
        parser.print_help()
        return 1
    try:
        return args.handler(args)
    except (RuntimeError, ConfigError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def main() -> int:
    return main_argv()
```

Change the parser description to `"Author, track and publish a knowledge base."`. Change `src/knowledge/__init__.py`'s docstring to `"""Authoring, tracking and publishing for a knowledge base."""`.

In `cmd_stale` and `cmd_dep`, fail before doing work:

```python
    if config.code_repo is None and not getattr(args, "code_repo", None):
        print(
            "no code repository configured — set repo.code_repo in knowledge.toml,"
            " or pass --code-repo",
            file=sys.stderr,
        )
        return 1
```

- [ ] **Step 4: Sweep for anything left**

Run: `rg -i 'monicords|mon:|https://monicords' src/ tests/`
Expected: no hits. Fix any that appear.

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: remove the last project-specific strings from the CLI"
```

---

