### Task 7: Configure publishing

**Files:**

- Modify: `src/knowledge/publish.py`
- Modify: `src/knowledge/cli.py` (`cmd_publish`)
- Test: `tests/test_publish.py`, `tests/test_cli_publish.py`

**Interfaces:**

- Consumes: `config.Publish`, `config.Sidebar` from Task 2; `graph.page_name` from Task 3.
- Produces:
  - `publish.render_sidebar(conn, sidebar: Sidebar) -> str`
  - `publish.write_pages(conn, paths, out_dir, sidebar: Sidebar) -> list[str]`
  - `publish.push(out_dir, remote, message, committer_name, committer_email) -> bool`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_publish.py`:

```python
from knowledge import publish
from knowledge.config import Sidebar


def test_sidebar_uses_the_configured_title_and_order(seeded_conn):
    bar = Sidebar(title="Example", order=("concepts",), labels={"concepts": "Concepts"})
    text = publish.render_sidebar(seeded_conn, bar)
    assert text.startswith("### Example")
    assert "- [Concepts](Concepts)" in text


def test_unlisted_specs_are_appended_alphabetically(seeded_conn):
    text = publish.render_sidebar(seeded_conn, Sidebar(title="Example", order=("concepts",)))
    assert text.index("Concepts") < text.index("Assets")


def test_nesting_and_headers_come_from_the_config(seeded_conn):
    bar = Sidebar(
        title="Example",
        order=("concepts", "assets"),
        nested_under={"assets": "concepts"},
        header_before={"concepts": "Modules"},
    )
    text = publish.render_sidebar(seeded_conn, bar)
    assert "**Modules**" in text
    assert "  - [Assets](Assets)" in text


def test_an_empty_sidebar_config_renders_every_spec_flat_and_alphabetical(seeded_conn):
    text = publish.render_sidebar(seeded_conn, Sidebar(title="Example"))
    assert "  - [" not in text
    assert "**" not in text.split("**Reference**")[0].replace("### Example", "")
```

`seeded_conn` is a fixture that scans the `repo` fixture into a database. Add it to `tests/conftest.py`:

```python
@pytest.fixture
def seeded_conn(repo):
    from knowledge import db, scan
    conn = db.connect(repo)
    scan.scan(conn, repo)
    return conn
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_publish.py -v`
Expected: FAIL — `render_sidebar()` takes 1 positional argument but 2 were given.

- [ ] **Step 3: Rewrite `publish.py`'s constants as parameters**

Delete `SIDEBAR_ORDER`, `SIDEBAR_REFERENCE`, `SIDEBAR_LABELS`, `SIDEBAR_HEADER_BEFORE`, `NESTED_UNDER`, `BOT_NAME` and `BOT_EMAIL`. Keep `FRONTMATTER`, `strip_frontmatter`, `_spec_directory`, `render_page` and `_published` unchanged. Then:

```python
def render_sidebar(conn, sidebar: Sidebar) -> str:
    rows = {spec_id: (title, page) for spec_id, title, page in _published(conn)}
    reference = set(sidebar.reference)
    ordered = [s for s in sidebar.order if s in rows and s not in reference]
    ordered += sorted(s for s in rows if s not in sidebar.order and s not in reference)

    lines = [f"### {sidebar.title}", ""] if sidebar.title else []
    for spec_id in ordered:
        header = sidebar.header_before.get(spec_id)
        if header:
            lines += ["", f"**{header}**", ""]
        title, page = rows[spec_id]
        label = sidebar.labels.get(spec_id, title)
        indent = "  " if spec_id in sidebar.nested_under else ""
        lines.append(f"{indent}- [{label}]({page})")

    lines += ["", "**Reference**", "", "- [Ontology](Ontology)"]
    for spec_id in sidebar.reference:
        if spec_id not in rows:
            continue
        title, page = rows[spec_id]
        lines.append(f"- [{sidebar.labels.get(spec_id, title)}]({page})")
    lines.append("")
    return "\n".join(lines)
```

`write_pages` gains a `sidebar: Sidebar` parameter and passes it to `render_sidebar`. `push` gains `committer_name: str` and `committer_email: str` parameters in place of the deleted constants.

- [ ] **Step 4: Dispatch on the target in `cmd_publish`**

At the top of `cmd_publish`:

```python
    target = config.publish.target
    if target == "none":
        print(
            "publishing is not configured — set publish.target in knowledge.toml"
            " to 'directory' or 'github-wiki'",
            file=sys.stderr,
        )
        return 1
    if target == "directory":
        out_dir = Path(args.out_dir or config.publish.out_dir)
        if not str(out_dir):
            print("publish.out_dir is required when publish.target is 'directory'",
                  file=sys.stderr)
            return 1
        written = publish.write_pages(conn, paths, out_dir, config.publish.sidebar)
        print(f"{len(written)} page(s) written to {out_dir}")
        return 0
```

The existing `github-wiki` path continues below, reading `config.publish.remote`, and passing `config.publish.committer_name` / `.committer_email` into `publish.push`.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_publish.py tests/test_cli_publish.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: configure the sidebar and the publishing target"
```

---

