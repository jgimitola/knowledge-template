# Task 6 review package

BASE: 74b6741
HEAD: c4cc611

## Commits
```
c4cc611 fix: reject a dynamic_segment that cannot mark a segment
be63ff6 feat: derive dependency globs from configured patterns
```

## Stat
```
 presets/nextjs.toml     |  15 ++++++++
 src/knowledge/cli.py    |   4 +-
 src/knowledge/config.py |  34 ++++++++++------
 src/knowledge/deps.py   | 100 ++++++++++++++++++++++++++++++++----------------
 tests/test_config.py    |  15 ++++++++
 tests/test_deps.py      |  90 ++++++++++++++++++++++++++++---------------
 6 files changed, 181 insertions(+), 77 deletions(-)
```

## Confirmation: nothing in src/ reads presets/
```
src/knowledge/cli.py:276:    presets = graph.surveys(config)
src/knowledge/cli.py:277:    if not presets:
src/knowledge/cli.py:278:        print("no `ask` presets configured — add [[ask]] tables to knowledge.toml")
src/knowledge/cli.py:281:    for title, sparql in presets:
src/knowledge/deps.py:10:`[dependencies]` table — see `presets/nextjs.toml` for a worked example. Nothing here
src/knowledge/graph.py:71:    """The `ask` presets, in the order knowledge.toml declares them."""
Binary file src/knowledge/__pycache__/cli.cpython-313.pyc matches
Binary file src/knowledge/__pycache__/deps.cpython-313.pyc matches
Binary file src/knowledge/__pycache__/graph.cpython-313.pyc matches
```

## Full diff (-U10)
```diff
diff --git a/presets/nextjs.toml b/presets/nextjs.toml
new file mode 100644
index 0000000..8036450
--- /dev/null
+++ b/presets/nextjs.toml
@@ -0,0 +1,15 @@
+# Copy this into your knowledge.toml to derive file globs from routes and endpoints in a
+# Next.js App Router project. It is data, not something the tooling reads from here.
+#
+# `platform` is absorbed because /platform/assets lives at
+# app/platform/(menuLayout)/assets/page.tsx: the route group sits between `platform` and the
+# module, so the segment is dropped and the ** covers both it and the group.
+# A dynamic segment like {incomeSourceId} becomes *, matching [incomeSourceId] on disk.
+[dependencies]
+route_property      = "route"
+endpoint_property   = "endpoint"
+route_glob          = "app/**/{segments}/page.tsx"
+endpoint_glob       = "app/{path}/**/route.ts"
+absorbed_prefixes   = ["platform"]
+dynamic_segment     = "{...}"
+dynamic_replacement = "*"
diff --git a/src/knowledge/cli.py b/src/knowledge/cli.py
index bbde317..90ac87d 100644
--- a/src/knowledge/cli.py
+++ b/src/knowledge/cli.py
@@ -441,21 +441,21 @@ def cmd_stale(args: argparse.Namespace) -> int:
         for spec_id, hits in findings:
             print(f"{spec_id}: {len(hits)} dependency change(s)")
             for path in hits:
                 print("   ", path)
         if args.demote:
             db.save(conn, paths)
             print(f"\n{len(findings)} spec(s) demoted to draft")
         else:
             print(f"\n{len(findings)} spec(s) would be demoted (pass --demote to apply)")
 
-    gaps = deps.uncheckable(conn, paths, config.vocabulary)
+    gaps = deps.uncheckable(conn, paths, config)
     if gaps:
         print(f"\n{len(gaps)} verified spec(s) have no dependencies and cannot be checked:")
         print("   ", ", ".join(gaps))
         print('  Add one with: knowledge dep add <spec> "<glob>"')
     return 0
 
 
 def _clear_markdown(out_dir: Path) -> list[str]:
     """Unlink every top-level *.md in out_dir, returning what was removed.
 
@@ -549,21 +549,21 @@ def cmd_dep(args: argparse.Namespace) -> int:
             if not deps.matches({args.glob}, tracked):
                 print("  warning: this glob matches no file in the code repository today")
     elif args.action == "remove":
         conn.execute(
             "DELETE FROM spec_dependency WHERE spec_id = ? AND glob = ?", (args.spec, args.glob)
         )
         db.record_event(conn, args.spec, "dependency_removed", "cli", args.glob)
         db.save(conn, paths)
         print(f"{args.spec} no longer depends on {args.glob}")
     else:
-        derived = deps.derived_globs(paths, config.vocabulary, args.spec)
+        derived = deps.derived_globs(paths, config, args.spec)
         manual = deps.manual_globs(conn, args.spec)
         print(f"derived from the graph ({len(derived)}):")
         for glob in sorted(derived):
             print("   ", glob)
         print(f"manual ({len(manual)}):")
         for glob in sorted(manual):
             print("   ", glob)
     return 0
 
 
diff --git a/src/knowledge/config.py b/src/knowledge/config.py
index 7fd07d3..09c9b60 100644
--- a/src/knowledge/config.py
+++ b/src/knowledge/config.py
@@ -34,21 +34,23 @@ class Dependencies:
     endpoint_property: str = ""
     route_glob: str = ""
     endpoint_glob: str = ""
     absorbed_prefixes: tuple[str, ...] = ()
     dynamic_segment: str = "{...}"
     dynamic_replacement: str = "*"
 
     @property
     def derives(self) -> bool:
         """Whether any glob can be derived from the graph at all. False leaves manual
-        globs as the only dependency source, which is the shipped default."""
+        globs as the only dependency source — the shipped default, because a project that
+        has not told this tool how its routes map to files should get no globs rather
+        than a guessed pattern that silently matches the wrong thing, or nothing."""
         return bool(self.route_property and self.route_glob) or bool(
             self.endpoint_property and self.endpoint_glob
         )
 
 
 @dataclass(frozen=True)
 class Sidebar:
     title: str = ""
     order: tuple[str, ...] = ()
     reference: tuple[str, ...] = ()
@@ -131,37 +133,47 @@ def _publish(data: dict) -> Publish:
             title=_clean(bar.get("title")),
             order=tuple(bar.get("order", ())),
             reference=tuple(bar.get("reference", ())),
             nested_under=dict(bar.get("nested_under", {})),
             header_before=dict(bar.get("header_before", {})),
             labels=dict(bar.get("labels", {})),
         ),
     )
 
 
+def _dependencies(data: dict) -> Dependencies:
+    table = data.get("dependencies", {})
+    dynamic_segment = _clean(table.get("dynamic_segment")) or "{...}"
+    if "..." not in dynamic_segment:
+        raise ConfigError(
+            f"knowledge.toml: dependencies.dynamic_segment is {dynamic_segment!r};"
+            " it must contain '...' to mark where the segment name goes (e.g. '{...}', '<...>')"
+        )
+    return Dependencies(
+        route_property=_clean(table.get("route_property")),
+        endpoint_property=_clean(table.get("endpoint_property")),
+        route_glob=_clean(table.get("route_glob")),
+        endpoint_glob=_clean(table.get("endpoint_glob")),
+        absorbed_prefixes=tuple(table.get("absorbed_prefixes", ())),
+        dynamic_segment=dynamic_segment,
+        dynamic_replacement=_clean(table.get("dynamic_replacement")) or "*",
+    )
+
+
 def load_config(root: Path) -> Config:
     with (root / "knowledge.toml").open("rb") as handle:
         data = tomllib.load(handle)
 
     code_repo = _clean(data.get("repo", {}).get("code_repo"))
-    deps = data.get("dependencies", {})
 
     return Config(
         project_name=_clean(data.get("project", {}).get("name")),
         vocabulary=_vocabulary(data),
         surveys=tuple(
             Survey(name=_clean(row.get("name")), query=_clean(row.get("query")))
             for row in data.get("ask", ())
         ),
         code_repo=(root / code_repo).resolve() if code_repo else None,
-        dependencies=Dependencies(
-            route_property=_clean(deps.get("route_property")),
-            endpoint_property=_clean(deps.get("endpoint_property")),
-            route_glob=_clean(deps.get("route_glob")),
-            endpoint_glob=_clean(deps.get("endpoint_glob")),
-            absorbed_prefixes=tuple(deps.get("absorbed_prefixes", ())),
-            dynamic_segment=_clean(deps.get("dynamic_segment")) or "{...}",
-            dynamic_replacement=_clean(deps.get("dynamic_replacement")) or "*",
-        ),
+        dependencies=_dependencies(data),
         publish=_publish(data),
         unconfigured=bool(data.get("template", {}).get("unconfigured", False)),
     )
diff --git a/src/knowledge/deps.py b/src/knowledge/deps.py
index 34edf41..84c23e7 100644
--- a/src/knowledge/deps.py
+++ b/src/knowledge/deps.py
@@ -1,78 +1,99 @@
 """What code does a spec depend on, and has any of it changed since verification?
 
 Two sources. Derived globs come from the spec's own triples — a route or an endpoint
 resolves mechanically to a file pattern — and are recomputed on every run, so they cannot
 themselves go stale. Manual globs in spec_dependency cover what the ontology does not
 model: services, Prisma models, shared utilities.
 
+The route/endpoint -> glob shape is framework-specific (a route group absorbed by **, a
+dynamic segment's on-disk spelling) and lives entirely in `knowledge.toml`'s
+`[dependencies]` table — see `presets/nextjs.toml` for a worked example. Nothing here
+hardcodes one framework, and by default `[dependencies]` is empty: a project that has not
+configured it gets manual globs only, not a guess.
+
 This never blocks a build. A code change failing on documentation is a check people learn
 to bypass; staleness is data, surfaced as work.
 """
 
 from __future__ import annotations
 
-import re
 from pathlib import Path, PurePosixPath
 
 from knowledge import gitcmd, lifecycle
-from knowledge.config import Config
+from knowledge.config import Config, Dependencies
 from knowledge.graph import load_spec_graph, run_query
 from knowledge.paths import Paths
-from knowledge.vocab import Vocabulary
 
-DYNAMIC_SEGMENT = re.compile(r"^\{.+\}$")
 
-# Routes whose files sit under a Next.js route group. /platform/assets lives at
-# app/platform/(menuLayout)/assets/page.tsx: the group sits between `platform` and the
-# module, so `platform` is dropped and the ** absorbs it along with the group.
-ROUTE_PREFIXES_ABSORBED_BY_GLOB = ("platform",)
+def _dynamic_delimiters(settings: Dependencies) -> tuple[str, str]:
+    """`{...}` -> ("{", "}"), `<...>` -> ("<", ">"). The syntax a project writes dynamic
+    route segments in is the project's, not this tool's."""
+    opening, _, closing = settings.dynamic_segment.partition("...")
+    return opening, closing
 
 
-def route_to_glob(route: str) -> str:
-    """A route says nothing about Next.js route groups — (menuLayout) is in the path but
-    not the URL — so the glob absorbs them with **. A dynamic segment like
-    {incomeSourceId} becomes *, matching the real directory name [incomeSourceId]."""
+def route_to_glob(route: str, settings: Dependencies) -> str:
+    """A route says nothing about directories a framework inserts and the URL omits, so an
+    absorbed prefix is dropped and the glob's ** covers it. A dynamic segment becomes the
+    configured replacement, matching whatever the real directory is called."""
+    opening, closing = _dynamic_delimiters(settings)
     segments = [part for part in route.strip("/").split("/") if part]
-    if segments and segments[0] in ROUTE_PREFIXES_ABSORBED_BY_GLOB:
+    if segments and segments[0] in settings.absorbed_prefixes:
         segments = segments[1:]
-    segments = ["*" if DYNAMIC_SEGMENT.match(part) else part for part in segments]
-    return "app/**/" + "/".join(segments) + "/page.tsx"
+    segments = [
+        settings.dynamic_replacement
+        if part.startswith(opening) and part.endswith(closing)
+        else part
+        for part in segments
+    ]
+    return settings.route_glob.replace("{segments}", "/".join(segments))
 
 
-def endpoint_to_glob(endpoint: str) -> str:
+def endpoint_to_glob(endpoint: str, settings: Dependencies) -> str:
     path = endpoint.split()[-1]  # tolerate "GET /api/cron" as well as "/api/cron"
-    return "app/" + path.strip("/") + "/**/route.ts"
-
-
-def derived_globs(paths: Paths, vocab: Vocabulary, spec_id: str) -> set[str]:
+    return settings.endpoint_glob.replace("{path}", path.strip("/"))
+
+
+def derived_globs(paths: Paths, config: Config, spec_id: str) -> set[str]:
+    """Empty when `config.dependencies.derives` is False — the shipped default, since a
+    project that has not configured `[dependencies]` has told this tool nothing about how
+    its routes map to files, and guessing would risk a glob that matches the wrong thing
+    (or nothing) silently."""
+    settings = config.dependencies
+    if not settings.derives:
+        return set()
+    vocab = config.vocabulary
     g = load_spec_graph(paths, vocab, spec_id)
-    globs = {
-        route_to_glob(row[0])
-        for row in run_query(g, vocab, f"SELECT ?r WHERE {{ ?s {vocab.prefix}:route ?r }}")
-    }
-    globs |= {
-        endpoint_to_glob(row[0])
-        for row in run_query(g, vocab, f"SELECT ?e WHERE {{ ?s {vocab.prefix}:endpoint ?e }}")
-    }
+    globs: set[str] = set()
+    if settings.route_property and settings.route_glob:
+        rows = run_query(
+            g, vocab, f"SELECT ?r WHERE {{ ?s {vocab.prefix}:{settings.route_property} ?r }}"
+        )
+        globs |= {route_to_glob(row[0], settings) for row in rows}
+    if settings.endpoint_property and settings.endpoint_glob:
+        rows = run_query(
+            g, vocab, f"SELECT ?e WHERE {{ ?s {vocab.prefix}:{settings.endpoint_property} ?e }}"
+        )
+        globs |= {endpoint_to_glob(row[0], settings) for row in rows}
     return globs
 
 
 def manual_globs(conn, spec_id: str) -> set[str]:
     return {
         row[0]
         for row in conn.execute("SELECT glob FROM spec_dependency WHERE spec_id = ?", (spec_id,))
     }
 
 
-def spec_globs(conn, paths: Paths, vocab: Vocabulary, spec_id: str) -> set[str]:
-    return derived_globs(paths, vocab, spec_id) | manual_globs(conn, spec_id)
+def spec_globs(conn, paths: Paths, config: Config, spec_id: str) -> set[str]:
+    return derived_globs(paths, config, spec_id) | manual_globs(conn, spec_id)
 
 
 def changed_files(code_repo: Path, since: str) -> list[str]:
     """Both sides of a rename count. git reports only the destination path by default, so
     a renamed dependency directory would match no glob and the spec would never be flagged
     — a silent failure, and the one kind staleness cannot report on itself."""
     result = gitcmd.run(
         ["-C", str(code_repo), "diff", "--name-status", "-M", f"{since}..HEAD"],
         capture_output=True, text=True, check=True,
     )
@@ -99,40 +120,51 @@ def tracked_files(code_repo: Path) -> list[str]:
 def matches(globs: set[str], changed: list[str]) -> list[str]:
     return sorted(
         path for path in changed
         if any(PurePosixPath(path).full_match(pattern) for pattern in globs)
     )
 
 
 def check(conn, paths: Paths, config: Config, demote: bool,
           code_repo: Path | None = None) -> list[tuple[str, list[str]]]:
     """code_repo overrides the configured path. CI checks the code repository out inside
-    its own workspace, which is not where knowledge.toml points."""
+    its own workspace, which is not where knowledge.toml points.
+
+    Raises RuntimeError when neither is set. Silently reporting no findings would be
+    indistinguishable from a spec that was actually compared against code and found
+    unchanged — the same false confidence as guessing a missing value instead of saying
+    it is missing.
+    """
     root = code_repo if code_repo is not None else config.code_repo
+    if root is None:
+        raise RuntimeError(
+            "no code repository configured — set repo.code_repo in knowledge.toml,"
+            " or pass --code-repo"
+        )
     findings: list[tuple[str, list[str]]] = []
     rows = list(conn.execute(
         "SELECT id, verified_against_commit FROM spec"
         " WHERE status = 'verified' AND verified_against_commit IS NOT NULL ORDER BY id"
     ))
     for spec_id, since in rows:
         hits = matches(
-            spec_globs(conn, paths, config.vocabulary, spec_id), changed_files(root, since)
+            spec_globs(conn, paths, config, spec_id), changed_files(root, since)
         )
         if not hits:
             continue
         findings.append((spec_id, hits))
         if demote:
             lifecycle.demote(
                 conn, spec_id, "changed since verification: " + ", ".join(hits), "stale-check"
             )
     return findings
 
 
-def uncheckable(conn, paths: Paths, vocab: Vocabulary) -> list[str]:
+def uncheckable(conn, paths: Paths, config: Config) -> list[str]:
     """Verified specs with zero dependencies — no derived route/endpoint and no manual
     glob. `check` reports these as clean, which is misleading: "checked and clean" and
     "cannot be checked" are different states, and conflating them is the same sin as
     guessing a missing exchange rate."""
     ids = [
         row[0] for row in conn.execute("SELECT id FROM spec WHERE status = 'verified' ORDER BY id")
     ]
-    return [spec_id for spec_id in ids if not spec_globs(conn, paths, vocab, spec_id)]
+    return [spec_id for spec_id in ids if not spec_globs(conn, paths, config, spec_id)]
diff --git a/tests/test_config.py b/tests/test_config.py
index aa72865..ab2e6ba 100644
--- a/tests/test_config.py
+++ b/tests/test_config.py
@@ -101,10 +101,25 @@ def test_missing_required_key_names_it(tmp_path):
     with pytest.raises(ConfigError) as exc:
         load_config(write(tmp_path, text))
     assert "vocabulary.namespace" in str(exc.value)
 
 
 def test_unknown_publish_target_is_rejected(tmp_path):
     text = MINIMAL + '\n[publish]\ntarget = "carrier-pigeon"\n'
     with pytest.raises(ConfigError) as exc:
         load_config(write(tmp_path, text))
     assert "carrier-pigeon" in str(exc.value)
+
+
+def test_dynamic_segment_without_an_ellipsis_is_rejected(tmp_path):
+    text = MINIMAL + '\n[dependencies]\ndynamic_segment = "{}"\n'
+    with pytest.raises(ConfigError) as exc:
+        load_config(write(tmp_path, text))
+    assert "dependencies.dynamic_segment" in str(exc.value)
+    assert "{}" in str(exc.value)
+
+
+@pytest.mark.parametrize("segment", ["<...>", "[...]"])
+def test_dynamic_segment_alternative_delimiters_are_accepted(tmp_path, segment):
+    text = MINIMAL + f'\n[dependencies]\ndynamic_segment = "{segment}"\n'
+    config = load_config(write(tmp_path, text))
+    assert config.dependencies.dynamic_segment == segment
diff --git a/tests/test_deps.py b/tests/test_deps.py
index da0b6a6..9d2f15b 100644
--- a/tests/test_deps.py
+++ b/tests/test_deps.py
@@ -1,66 +1,85 @@
 import subprocess
+from dataclasses import replace
 
 import pytest
 
 from knowledge import db, deps, lifecycle, scan
+from knowledge.config import Dependencies
 from tests.conftest import make_config
 
+NEXTJS = Dependencies(
+    route_property="route",
+    endpoint_property="endpoint",
+    route_glob="app/**/{segments}/page.tsx",
+    endpoint_glob="app/{path}/**/route.ts",
+    absorbed_prefixes=("platform",),
+)
 
-def test_route_to_glob_ignores_route_groups():
-    # /platform/assets lives at app/platform/(menuLayout)/assets/page.tsx
-    assert deps.route_to_glob("/platform/assets") == "app/**/assets/page.tsx"
-    assert deps.route_to_glob("/landing") == "app/**/landing/page.tsx"
-    assert deps.route_to_glob("/platform/expenses/calendar") == (
-        "app/**/expenses/calendar/page.tsx"
+
+def test_route_glob_absorbs_the_configured_prefix():
+    assert deps.route_to_glob("/platform/assets", NEXTJS) == "app/**/assets/page.tsx"
+
+
+def test_route_glob_replaces_dynamic_segments():
+    assert (
+        deps.route_to_glob("/platform/incomes/{incomeSourceId}", NEXTJS)
+        == "app/**/incomes/*/page.tsx"
     )
 
 
-def test_route_to_glob_handles_a_dynamic_segment():
-    # A dynamic segment becomes *, not [*] — [*] is a character class matching one literal
-    # asterisk, while the real directory is named [incomeSourceId].
-    assert deps.route_to_glob("/platform/incomes/{incomeSourceId}") == (
-        "app/**/incomes/*/page.tsx"
+def test_route_glob_leaves_unabsorbed_prefixes_alone():
+    assert deps.route_to_glob("/settings/profile", NEXTJS) == "app/**/settings/profile/page.tsx"
+
+
+def test_endpoint_glob_tolerates_a_leading_method():
+    assert deps.endpoint_to_glob("GET /api/cron", NEXTJS) == "app/api/cron/**/route.ts"
+
+
+def test_a_different_framework_needs_no_code_change():
+    django = Dependencies(
+        route_property="route",
+        route_glob="apps/**/{segments}/views.py",
+        dynamic_segment="<...>",
     )
+    assert deps.route_to_glob("/reports/<year>", django) == "apps/**/reports/*/views.py"
+
+
+def test_derived_globs_are_empty_when_nothing_is_configured(repo, config):
+    plain = replace(config, dependencies=Dependencies())
+    assert deps.derived_globs(repo, plain, "assets") == set()
 
 
 def test_a_dynamic_glob_matches_a_real_nextjs_directory():
-    globs = {deps.route_to_glob("/platform/incomes/{incomeSourceId}")}
+    globs = {deps.route_to_glob("/platform/incomes/{incomeSourceId}", NEXTJS)}
     changed = ["app/platform/(menuLayout)/incomes/[incomeSourceId]/page.tsx"]
     assert deps.matches(globs, changed) == changed
 
 
-def test_endpoint_to_glob():
-    assert deps.endpoint_to_glob("/api/cron") == "app/api/cron/**/route.ts"
-    assert deps.endpoint_to_glob("/api/loans-out/summary") == (
-        "app/api/loans-out/summary/**/route.ts"
-    )
-
-
 def test_an_endpoint_glob_matches_a_route_handler_directly_beneath_it():
-    globs = {deps.endpoint_to_glob("/api/cron")}
+    globs = {deps.endpoint_to_glob("/api/cron", NEXTJS)}
     assert deps.matches(globs, ["app/api/cron/route.ts"]) == ["app/api/cron/route.ts"]
 
 
 def test_derived_globs_come_from_the_specs_own_triples(repo, config):
-    assert deps.derived_globs(repo, config.vocabulary, "assets") == {"app/**/assets/page.tsx"}
-    assert deps.derived_globs(repo, config.vocabulary, "concepts") == set()
+    assert deps.derived_globs(repo, config, "assets") == {"app/**/assets/page.tsx"}
+    assert deps.derived_globs(repo, config, "concepts") == set()
 
 
 def test_manual_globs_are_added_to_derived_ones(repo, config):
     conn = db.connect(repo)
     scan.scan(conn, repo)
     conn.execute(
         "INSERT INTO spec_dependency (spec_id, glob, note)"
         " VALUES ('assets','modules/server/submodules/assets/**','the service layer')"
     )
-    assert deps.spec_globs(conn, repo, config.vocabulary, "assets") == {
+    assert deps.spec_globs(conn, repo, config, "assets") == {
         "app/**/assets/page.tsx",
         "modules/server/submodules/assets/**",
     }
 
 
 def test_matches_uses_full_glob_semantics():
     globs = {"app/**/assets/page.tsx", "modules/server/submodules/assets/**"}
     changed = [
         "app/platform/(menuLayout)/assets/page.tsx",
         "modules/server/submodules/assets/services/create/index.ts",
@@ -83,68 +102,68 @@ def code_repo(tmp_path):
     subprocess.run(["git", "-C", str(root), "config", "user.name", "T"], check=True)
     subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, capture_output=True)
     subprocess.run(["git", "-C", str(root), "commit", "-m", "init"], check=True,
                    capture_output=True)
     return root
 
 
 def test_check_demotes_a_spec_whose_dependency_changed(repo, code_repo):
     conn = db.connect(repo)
     scan.scan(conn, repo)
-    config = make_config(code_repo, remote="x")
+    config = replace(make_config(code_repo, remote="x"), dependencies=NEXTJS)
     base = lifecycle.head_commit(code_repo)
 
     lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
     lifecycle.verify(conn, repo, config, "assets", by="jesus", prune=[], commit=base)
 
     page = code_repo / "app" / "platform" / "(menuLayout)" / "assets" / "page.tsx"
     page.write_text("changed\n")
     subprocess.run(["git", "-C", str(code_repo), "commit", "-am", "change"], check=True,
                    capture_output=True)
 
     findings = deps.check(conn, repo, config, demote=True)
     assert findings == [("assets", ["app/platform/(menuLayout)/assets/page.tsx"])]
     assert list(conn.execute("SELECT status FROM spec WHERE id='assets'")) == [("draft",)]
 
 
 def test_check_ignores_an_unrelated_change(repo, code_repo):
     conn = db.connect(repo)
     scan.scan(conn, repo)
-    config = make_config(code_repo, remote="x")
+    config = replace(make_config(code_repo, remote="x"), dependencies=NEXTJS)
     base = lifecycle.head_commit(code_repo)
 
     lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
     lifecycle.verify(conn, repo, config, "assets", by="jesus", prune=[], commit=base)
 
     (code_repo / "README.md").write_text("goodbye\n")
     subprocess.run(["git", "-C", str(code_repo), "commit", "-am", "readme"], check=True,
                    capture_output=True)
 
     assert deps.check(conn, repo, config, demote=True) == []
     assert list(conn.execute("SELECT status FROM spec WHERE id='assets'")) == [("verified",)]
 
 
 def test_check_only_looks_at_verified_specs(repo, code_repo):
     conn = db.connect(repo)
     scan.scan(conn, repo)
-    config = make_config(code_repo, remote="x")
+    config = replace(make_config(code_repo, remote="x"), dependencies=NEXTJS)
     # assets is left as a draft; nothing to demote regardless of what changed.
     assert deps.check(conn, repo, config, demote=True) == []
 
 
 def test_check_demotes_a_spec_whose_dependency_was_renamed(repo, code_repo):
     """git reports only the destination of a rename by default. If changed_files did not
     also report the source path, this manual glob (which names the old directory) would
     match nothing and the spec would never be flagged."""
     conn = db.connect(repo)
     scan.scan(conn, repo)
-    config = make_config(code_repo, remote="x")
+    config = replace(make_config(code_repo, remote="x"), dependencies=NEXTJS)
 
     conn.execute(
         "INSERT INTO spec_dependency (spec_id, glob, note)"
         " VALUES ('assets','modules/server/submodules/assets/**','the service layer')"
     )
     service_dir = code_repo / "modules" / "server" / "submodules" / "assets"
     service_dir.mkdir(parents=True)
     (service_dir / "index.ts").write_text("export {}\n")
     subprocess.run(["git", "-C", str(code_repo), "add", "-A"], check=True, capture_output=True)
     subprocess.run(["git", "-C", str(code_repo), "commit", "-m", "add service"], check=True,
@@ -165,43 +184,54 @@ def test_check_demotes_a_spec_whose_dependency_was_renamed(repo, code_repo):
     findings = deps.check(conn, repo, config, demote=True)
     assert findings == [("assets", ["modules/server/submodules/assets/index.ts"])]
     assert list(conn.execute("SELECT status FROM spec WHERE id='assets'")) == [("draft",)]
 
 
 def test_check_accepts_a_code_repo_override(repo, code_repo, tmp_path):
     """CI checks the code repo out inside the workspace, not where knowledge.toml points."""
     conn = db.connect(repo)
     scan.scan(conn, repo)
     # A config pointing somewhere that does not exist, to prove the override is what is used.
-    config = make_config(tmp_path / "nonexistent", remote="x")
+    config = replace(make_config(tmp_path / "nonexistent", remote="x"), dependencies=NEXTJS)
     base = lifecycle.head_commit(code_repo)
 
     lifecycle.mark_modeled(conn, repo, "assets", by="writer", ontology_version="1.0.0")
     lifecycle.verify(conn, repo, config, "assets", by="jesus", prune=[], commit=base)
 
     page = code_repo / "app" / "platform" / "(menuLayout)" / "assets" / "page.tsx"
     page.write_text("changed\n")
     subprocess.run(["git", "-C", str(code_repo), "commit", "-am", "change"], check=True,
                    capture_output=True)
 
     findings = deps.check(conn, repo, config, demote=True, code_repo=code_repo)
     assert findings == [("assets", ["app/platform/(menuLayout)/assets/page.tsx"])]
 
 
+def test_check_refuses_when_no_code_repository_is_configured(repo, config):
+    """config.code_repo is Optional; without this guard a spec that was never compared
+    against any code repository would silently report zero findings, indistinguishable
+    from a spec that was actually checked and found clean."""
+    conn = db.connect(repo)
+    scan.scan(conn, repo)
+    no_repo = replace(config, code_repo=None)
+    with pytest.raises(RuntimeError, match="no code repository configured"):
+        deps.check(conn, repo, no_repo, demote=False)
+
+
 def test_uncheckable_lists_a_verified_spec_with_no_dependencies(repo, config):
     conn = db.connect(repo)
     scan.scan(conn, repo)
     conn.execute("UPDATE spec SET status='verified' WHERE id IN ('assets','concepts')")
     # assets has a derived glob from its route; concepts has neither a route/endpoint nor a
     # manual dependency, so only concepts is uncheckable.
-    assert deps.uncheckable(conn, repo, config.vocabulary) == ["concepts"]
+    assert deps.uncheckable(conn, repo, config) == ["concepts"]
 
 
 def test_uncheckable_excludes_a_spec_once_it_has_a_manual_glob(repo, config):
     conn = db.connect(repo)
     scan.scan(conn, repo)
     conn.execute("UPDATE spec SET status='verified' WHERE id IN ('assets','concepts')")
     conn.execute(
         "INSERT INTO spec_dependency (spec_id, glob, note)"
         " VALUES ('concepts','prisma/schema.prisma','the data model')"
     )
-    assert deps.uncheckable(conn, repo, config.vocabulary) == []
+    assert deps.uncheckable(conn, repo, config) == []
```
