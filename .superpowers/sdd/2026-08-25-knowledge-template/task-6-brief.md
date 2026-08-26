### Task 6: Configure the dependency globs

**Files:**

- Modify: `src/knowledge/deps.py`
- Modify: `src/knowledge/cli.py` (`cmd_stale`, `cmd_dep`)
- Create: `presets/nextjs.toml`
- Test: `tests/test_deps.py`

**Interfaces:**

- Consumes: `config.Dependencies` from Task 2; `graph.load_spec_graph` / `graph.run_query` from Task 3.
- Produces:
  - `deps.route_to_glob(route: str, settings: Dependencies) -> str`
  - `deps.endpoint_to_glob(endpoint: str, settings: Dependencies) -> str`
  - `deps.derived_globs(paths, config, spec_id) -> set[str]`
  - `deps.spec_globs(conn, paths, config, spec_id) -> set[str]`
  - `deps.check(conn, paths, config, demote, code_repo=None) -> list[tuple[str, list[str]]]`
  - `deps.uncheckable(conn, paths, config) -> list[str]`

- [ ] **Step 1: Write the failing tests**

Replace the glob tests in `tests/test_deps.py`:

```python
from knowledge import deps
from knowledge.config import Dependencies

NEXTJS = Dependencies(
    route_property="route",
    endpoint_property="endpoint",
    route_glob="app/**/{segments}/page.tsx",
    endpoint_glob="app/{path}/**/route.ts",
    absorbed_prefixes=("platform",),
)


def test_route_glob_absorbs_the_configured_prefix():
    assert deps.route_to_glob("/platform/assets", NEXTJS) == "app/**/assets/page.tsx"


def test_route_glob_replaces_dynamic_segments():
    assert (
        deps.route_to_glob("/platform/incomes/{incomeSourceId}", NEXTJS)
        == "app/**/incomes/*/page.tsx"
    )


def test_route_glob_leaves_unabsorbed_prefixes_alone():
    assert deps.route_to_glob("/settings/profile", NEXTJS) == "app/**/settings/profile/page.tsx"


def test_endpoint_glob_tolerates_a_leading_method():
    assert deps.endpoint_to_glob("GET /api/cron", NEXTJS) == "app/api/cron/**/route.ts"


def test_a_different_framework_needs_no_code_change():
    django = Dependencies(
        route_property="route",
        route_glob="apps/**/{segments}/views.py",
        dynamic_segment="<...>",
    )
    assert deps.route_to_glob("/reports/<year>", django) == "apps/**/reports/*/views.py"


def test_derived_globs_are_empty_when_nothing_is_configured(repo, config):
    from dataclasses import replace
    plain = replace(config, dependencies=Dependencies())
    assert deps.derived_globs(repo, plain, "assets") == set()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_deps.py -v`
Expected: FAIL — `route_to_glob()` takes 1 positional argument but 2 were given.

- [ ] **Step 3: Rewrite the derivation in `deps.py`**

Delete `DYNAMIC_SEGMENT` and `ROUTE_PREFIXES_ABSORBED_BY_GLOB`. Then:

```python
def _dynamic_delimiters(settings: Dependencies) -> tuple[str, str]:
    """`{...}` -> ("{", "}"), `<...>` -> ("<", ">"). The syntax a project writes dynamic
    route segments in is the project's, not this tool's."""
    opening, _, closing = settings.dynamic_segment.partition("...")
    return opening, closing


def route_to_glob(route: str, settings: Dependencies) -> str:
    """A route says nothing about directories a framework inserts and the URL omits, so an
    absorbed prefix is dropped and the glob's ** covers it. A dynamic segment becomes the
    configured replacement, matching whatever the real directory is called."""
    opening, closing = _dynamic_delimiters(settings)
    segments = [part for part in route.strip("/").split("/") if part]
    if segments and segments[0] in settings.absorbed_prefixes:
        segments = segments[1:]
    segments = [
        settings.dynamic_replacement
        if part.startswith(opening) and part.endswith(closing)
        else part
        for part in segments
    ]
    return settings.route_glob.replace("{segments}", "/".join(segments))


def endpoint_to_glob(endpoint: str, settings: Dependencies) -> str:
    path = endpoint.split()[-1]  # tolerate "GET /api/cron" as well as "/api/cron"
    return settings.endpoint_glob.replace("{path}", path.strip("/"))


def derived_globs(paths: Paths, config: Config, spec_id: str) -> set[str]:
    settings = config.dependencies
    if not settings.derives:
        return set()
    g = load_spec_graph(paths, config.vocabulary, spec_id)
    vocab = config.vocabulary
    globs: set[str] = set()
    if settings.route_property and settings.route_glob:
        rows = run_query(g, vocab, f"SELECT ?r WHERE {{ ?s {vocab.prefix}:{settings.route_property} ?r }}")
        globs |= {route_to_glob(row[0], settings) for row in rows}
    if settings.endpoint_property and settings.endpoint_glob:
        rows = run_query(g, vocab, f"SELECT ?e WHERE {{ ?s {vocab.prefix}:{settings.endpoint_property} ?e }}")
        globs |= {endpoint_to_glob(row[0], settings) for row in rows}
    return globs
```

Thread `config` in place of `paths, config` pairs through `spec_globs`, `check` and `uncheckable`, replacing their `Config`-typed `config` parameter usage: `check` already takes `config` and reads `config.code_repo`, which is now `Path | None`. Guard it:

```python
    root = code_repo if code_repo is not None else config.code_repo
    if root is None:
        raise RuntimeError(
            "no code repository configured — set repo.code_repo in knowledge.toml,"
            " or pass --code-repo"
        )
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_deps.py -v`
Expected: PASS.

- [ ] **Step 5: Write the Next.js preset**

Create `presets/nextjs.toml`:

```toml
# Copy this into your knowledge.toml to derive file globs from routes and endpoints in a
# Next.js App Router project. It is data, not something the tooling reads from here.
#
# `platform` is absorbed because /platform/assets lives at
# app/platform/(menuLayout)/assets/page.tsx: the route group sits between `platform` and the
# module, so the segment is dropped and the ** covers both it and the group.
# A dynamic segment like {incomeSourceId} becomes *, matching [incomeSourceId] on disk.
[dependencies]
route_property      = "route"
endpoint_property   = "endpoint"
route_glob          = "app/**/{segments}/page.tsx"
endpoint_glob       = "app/{path}/**/route.ts"
absorbed_prefixes   = ["platform"]
dynamic_segment     = "{...}"
dynamic_replacement = "*"
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: derive dependency globs from configured patterns"
```

---

