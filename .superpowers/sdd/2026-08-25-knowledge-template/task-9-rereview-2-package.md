# Task 9 fix rounds 2 and 3 scoped diff

FIX_BASE: d810790 (Task 10's commit; Task 9 fix rounds 2-3 land after it)
HEAD: 49b41f9

## Commits
```
49b41f9 fix: empty the tracked dump so a generated repository starts with no spec rows
4715e43 fix: rewrite the instance prefix declaration alongside the project prefix
```

## Stat
```
 src/knowledge/init.py | 111 ++++++++++++++++++++++++++++++++++++++++----------
 tests/test_init.py    |  92 +++++++++++++++++++++++++++++++++++++++++
 2 files changed, 181 insertions(+), 22 deletions(-)
```

## Controller's independent end-to-end verification of a generated repo
```
INSERT rows after init: 0
scan: added 0, moved 0, unchanged 0, missing 0, demoted 0
validate --strict: exit 0
init --check: no placeholders remain
@prefix acme: <https://acme.test/ontology#> / @prefix app: <https://acme.test/id/> — both agree with load_config
```

## Full diff (-U20)
```diff
diff --git a/src/knowledge/init.py b/src/knowledge/init.py
index c496349..ced9d0f 100644
--- a/src/knowledge/init.py
+++ b/src/knowledge/init.py
@@ -1,32 +1,33 @@
 """`knowledge init` — bind the template to one project, once.
 
 Placeholders split by who reads the file they live in (ruling C12):
 
 - Prose the reader parses with their eyes — README, the agents, the skill, ontology/README.md
   — ships with `{{TOKEN}}` markers. `substitute` below sweeps those.
 - Values a machine parses before `init` ever runs — knowledge.toml's `[vocabulary]`
-  namespace/instances/prefix, and the ontology file's own `@prefix` line — ship as WORKING
-  DEFAULTS instead. `load_config` treats an unsubstituted `{{TOKEN}}` as empty, and rdflib's
-  Turtle parser rejects `@prefix {{PREFIX}}:` outright, so a token there would break the
-  shipped template before `init` had a chance to run (`init.run` itself calls
-  `load_config`). Those fields are rewritten in place — see `_rewrite_vocabulary_keys` and
+  namespace/instances/prefix/instance_prefix, and the ontology file's own two `@prefix`
+  lines (the project vocabulary's, and the instance prefix's) — ship as WORKING DEFAULTS
+  instead. `load_config` treats an unsubstituted `{{TOKEN}}` as empty, and rdflib's Turtle
+  parser rejects `@prefix {{PREFIX}}:` outright, so a token there would break the shipped
+  template before `init` had a chance to run (`init.run` itself calls `load_config`). Those
+  fields are rewritten in place — see `_rewrite_vocabulary_keys` and
   `_rewrite_ontology_prefix` — not substituted.
 
 Either way, `[template] unconfigured = true` is what marks the repository as not yet
 configured, not the presence of any placeholder — that table survives even though the
 vocabulary defaults it sits beside are already "valid-looking" values.
 """
 
 from __future__ import annotations
 
 import re
 import shutil
 from dataclasses import dataclass
 from pathlib import Path
 
 from knowledge.config import load_config
 
 PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")
 
 # Files that carry {{TOKEN}} placeholders read by a person, not a parser. Everything else in
 # the template is already generic. The ontology and example-spec files are added in `run`,
@@ -104,52 +105,58 @@ def substitute(root: Path, values: dict[str, str], manifest=MANIFEST) -> list[st
 
 
 def remaining_placeholders(root: Path) -> list[str]:
     """"<path>: {{TOKEN}}" for every placeholder still in the tree."""
     found: list[str] = []
     for path in sorted(root.rglob("*")):
         if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
             continue
         if SKIPPED_DIRS & set(path.relative_to(root).parts):
             continue
         try:
             text = path.read_text(encoding="utf-8")
         except UnicodeDecodeError:
             continue
         for match in PLACEHOLDER.finditer(text):
             found.append(f"{path.relative_to(root).as_posix()}: {match.group(0)}")
     return found
 
 
 def _rewrite_vocabulary_keys(text: str, values: dict[str, str]) -> str:
-    """Rewrite `knowledge.toml`'s `[vocabulary]` namespace/instances/prefix in place.
+    """Rewrite `knowledge.toml`'s `[vocabulary]` namespace/instances/prefix/instance_prefix
+    in place.
 
-    These three ship as working defaults (`https://example.com/...`, `ex`), not `{{TOKEN}}`
-    placeholders — see the module docstring — so `substitute`'s token sweep never touches
-    them; they need their own rewrite.
+    These four ship as working defaults (`https://example.com/...`, `ex`, `app`), not
+    `{{TOKEN}}` placeholders — see the module docstring — so `substitute`'s token sweep
+    never touches them; they need their own rewrite. `instance_prefix` is included so
+    knowledge.toml stays consistent with the ontology file's own instance `@prefix` line
+    (see `_rewrite_ontology_prefix`) — both must name the same prefix, or SPARQL queries
+    built from `vocab.sparql_prefixes` would declare `app:` while specs actually use
+    whatever `answers.instance_prefix` renamed it to.
 
     Each key is matched anchored to the start of its own line (`(?m)^key\\s*=\\s*"..."$`)
     rather than replaced as a bare substring, so a value that happens to appear elsewhere in
     the file (or a same-named key, if one existed in another table) could not be hit by
-    accident. In the shipped `knowledge.toml`, `namespace` and `instances` each appear on
-    exactly one line, and `prefix` — anchored to line-start — matches only the bare `prefix`
-    key, never `instance_prefix` or `absorbed_prefixes` (both start with a different word).
+    accident. In the shipped `knowledge.toml`, `namespace`, `instances` and `instance_prefix`
+    each appear on exactly one line, and `prefix` — anchored to line-start — matches only
+    the bare `prefix` key, never `instance_prefix` or `absorbed_prefixes` (both start with a
+    different word).
     """
     for key, value in values.items():
         pattern = re.compile(rf'(?m)^({re.escape(key)}\s*=\s*)"[^"]*"$')
         text = pattern.sub(lambda m, v=value: f'{m.group(1)}"{v}"', text, count=1)
     return text
 
 
 # A Turtle span a comment-boundary search or the bare-prefix rewrite below must not look
 # inside: a "..." string literal, or a <...> IRI. Both can contain a literal '#' or the
 # prefix text without either meaning what it would in code — a namespace IRI conventionally
 # ends in '#' (<https://acme.test/ontology#>), and a hand-authored rdfs:comment/rdfs:label
 # routinely uses the prefix as English shorthand ("write ex: before every term"). Single
 # double-quoted strings and single-bracketed IRIs only: the seed ontology never uses
 # triple-quoted string literals, an escaped '"' inside one, or a nested '<'/'>' inside an
 # IRI, so this one-pass regex does not need to handle those.
 PROTECTED_SPAN = re.compile(r'"(?:\\.|[^"\\])*"|<[^<>]*>')
 
 
 def _comment_start(line: str) -> int:
     """Index of the first '#' in `line` that actually starts a Turtle comment — i.e. one
@@ -165,127 +172,187 @@ def _comment_start(line: str) -> int:
     idx = line.find("#", pos)
     return idx if idx != -1 else len(line)
 
 
 def _rewrite_bare_prefix_outside_protected_spans(
     code: str, pattern: re.Pattern[str], replacement: str
 ) -> str:
     """Apply `pattern.sub(replacement, ...)` to `code`, skipping every PROTECTED_SPAN (a
     string literal or an IRI) so a prefix quoted as English shorthand inside one is left
     untouched rather than corrupted."""
     out: list[str] = []
     pos = 0
     for span in PROTECTED_SPAN.finditer(code):
         out.append(pattern.sub(replacement, code[pos:span.start()]))
         out.append(span.group(0))
         pos = span.end()
     out.append(pattern.sub(replacement, code[pos:]))
     return "".join(out)
 
 
-def _rewrite_ontology_prefix(text: str, old_prefix: str, new_prefix: str, namespace: str) -> str:
-    """Rewrite the ontology file's own vocabulary prefix — its `@prefix` declaration and
-    every `old_prefix:Term` usage in the body.
+def _rewrite_prefix_pair(text: str, old_prefix: str, new_prefix: str, namespace: str) -> str:
+    """Rewrite one Turtle `@prefix` declaration — its name and IRI together — plus every
+    bare `old_prefix:Term` usage in the body. Shared by `_rewrite_ontology_prefix` below for
+    both prefixes the ontology file declares: the project vocabulary's own prefix (`ex:` by
+    default) and the instance prefix (`app:` by default) any spec's individuals use.
 
     Two bounded passes, in this order:
 
     1. The declaration line itself, matched as a whole so the prefix name and its IRI are
        replaced together: `@prefix ex: <https://example.com/ontology#> .` becomes
        `@prefix acme: <https://acme.test/ontology#> .`. Matched first, while the line still
        reads `old_prefix:`, so pass 2 below cannot see it and mangle the IRI.
     2. Every remaining bare `old_prefix:` — e.g. `ex:Concept`, `rdfs:domain ex:Concept` —
        renamed to `new_prefix:`, but only where it appears in Turtle *code*. Line by line:
        `_comment_start` finds where a trailing `# ...` comment begins (if any), and
        `_rewrite_bare_prefix_outside_protected_spans` skips every string literal and IRI in
        what remains. Without this, a plain `\\bold_prefix:\\b` sweep over the whole file would
        also rewrite the prefix everywhere it is used as English shorthand in hand-authored
        prose — a `#` comment explaining the file, or an `rdfs:comment` value — which the
        seed ontology (Task 10) does. `\\b` still anchors each code-position match so it
        cannot fire inside a longer word (`example:` never matches `\\bex:`, because "ex"
        there is not followed by a colon).
-
-    The instance prefix (`app:` by default) is untouched: correction C12 scopes this rewrite
-    to the vocabulary's own prefix, matching `_rewrite_vocabulary_keys` above, which likewise
-    only rewrites `namespace`/`instances`/`prefix`, not `instance_prefix`.
     """
     declaration = re.compile(rf"@prefix\s+{re.escape(old_prefix)}:\s+<[^>]*>\s*\.")
     text = declaration.sub(f"@prefix {new_prefix}: <{namespace}> .", text, count=1)
 
     bare = re.compile(rf"\b{re.escape(old_prefix)}:")
     lines = []
     for line in text.split("\n"):
         cut = _comment_start(line)
         code, comment = line[:cut], line[cut:]
         rewritten_code = _rewrite_bare_prefix_outside_protected_spans(code, bare, f"{new_prefix}:")
         lines.append(rewritten_code + comment)
     return "\n".join(lines)
 
 
+def _rewrite_ontology_prefix(
+    text: str,
+    old_prefix: str,
+    new_prefix: str,
+    namespace: str,
+    old_instance_prefix: str,
+    new_instance_prefix: str,
+    instances: str,
+) -> str:
+    """Rewrite both prefixes the ontology file declares, via two independent
+    `_rewrite_prefix_pair` passes: the project vocabulary's own prefix (`ex:` by default,
+    rewritten first) and the instance prefix (`app:` by default, rewritten second).
+
+    The instance prefix is not optional to rewrite. `graph.turtle_source` concatenates
+    ontology.ttl (which declares both `@prefix` lines) with every spec's bare `.ttl` — a
+    spec never declares its own prefixes, so an individual like `app:Widget` in a spec
+    resolves against *this file's* `@prefix app:` declaration when the whole thing is parsed
+    as one Turtle document. Leaving that declaration pointed at the old instances IRI would
+    silently detach every individual any spec ever writes from `config.vocabulary.instances`
+    — `vocab.is_instance()` tests a literal IRI prefix, so it would return False for all of
+    them without erroring, which in turn switches off `graph.dangling_terms`'s instance half
+    and the underscore half of `lint.naming_violations` while both keep reporting clean.
+
+    The two passes are independent — each searches only for its own *old* prefix text, so
+    rewriting `ex:` first can't touch anything the `app:` pass is about, and vice versa —
+    order between them does not matter for correctness (project prefix is rewritten first
+    here only because that mirrors the order the two `@prefix` lines are declared).
+    """
+    text = _rewrite_prefix_pair(text, old_prefix, new_prefix, namespace)
+    text = _rewrite_prefix_pair(text, old_instance_prefix, new_instance_prefix, instances)
+    return text
+
+
 def _reset_metadata(root: Path) -> None:
     """An empty database dumped fresh, so the generated repository starts with no history
-    of specs that are no longer there."""
+    of specs that are no longer there. (Ruling C23.)
+
+    Both `paths.db` and `paths.dump` must go before `db.connect` runs — deleting only the
+    `.db` achieves nothing on its own, because `dump.sql` is the tracked artifact and
+    `db.connect` rebuilds the database from it whenever the database file was just deleted
+    and a dump file is still present (see its own docstring: that reload exists so a pulled
+    dump.sql newer than the local db is picked up, which is exactly what an inherited,
+    checked-in dump.sql looks like here). Deleting only `paths.db` left a generated
+    repository's dump.sql carrying real INSERT rows for specs that no longer exist on disk
+    (Task 10's shipped `.metadata/dump.sql` has one for `example`) — `db.connect` reloaded
+    them into the "fresh" database and `db.save` wrote them right back out unchanged, so
+    `scan` in the generated repository reported `missing 1: example has a row but no
+    files` as the very first thing a new user saw.
+    """
     from knowledge import db
     from knowledge.paths import get_paths
 
     paths = get_paths(root, load_config(root).vocabulary.ontology_file)
     paths.db.unlink(missing_ok=True)
+    paths.dump.unlink(missing_ok=True)
     conn = db.connect(paths)
     db.save(conn, paths)
     conn.close()
     paths.db.unlink(missing_ok=True)
 
 
 def run(root: Path, answers: Answers) -> list[str]:
     """Bind the template to one project. Returns the files it actually rewrote — a path
     only lands in this list when its text changed, so the caller's count is one this
     function earned rather than one it merely attempted."""
     config = load_config(root)
     if not config.unconfigured:
         raise RuntimeError(
             f"{root} is already configured — remove the [template] table from"
             " knowledge.toml to re-run init"
         )
 
     ontology_file = config.vocabulary.ontology_file
     old_prefix = config.vocabulary.prefix
+    old_instance_prefix = config.vocabulary.instance_prefix
     values = _values(answers, ontology_file)
     namespace = values["BASE_IRI"] + "ontology#"
     instances = values["BASE_IRI"] + "id/"
 
     rewritten = substitute(
         root, values, MANIFEST + (f"ontology/{ontology_file}", "specs/example/spec.ttl")
     )
 
     ontology_path = root / "ontology" / ontology_file
     if ontology_path.is_file():
         text = ontology_path.read_text(encoding="utf-8")
-        new_text = _rewrite_ontology_prefix(text, old_prefix, answers.prefix, namespace)
+        new_text = _rewrite_ontology_prefix(
+            text, old_prefix, answers.prefix, namespace,
+            old_instance_prefix, answers.instance_prefix, instances,
+        )
         if new_text != text:
             ontology_path.write_text(new_text, encoding="utf-8", newline="\n")
             if f"ontology/{ontology_file}" not in rewritten:
                 rewritten.append(f"ontology/{ontology_file}")
 
     toml_path = root / "knowledge.toml"
     original_toml = toml_path.read_text(encoding="utf-8")
     text = re.sub(r"\[template\]\nunconfigured = true\n\n?", "", original_toml, count=1)
+    # instance_prefix is rewritten alongside namespace/instances/prefix — not just those
+    # three — so knowledge.toml stays consistent with the ontology file's own instance
+    # `@prefix` line above: if they disagreed, `vocab.sparql_prefixes` and `cmd_describe`'s
+    # default term prefix would still say `app:` while specs actually use whatever
+    # `answers.instance_prefix` renamed it to.
     text = _rewrite_vocabulary_keys(
-        text, {"namespace": namespace, "instances": instances, "prefix": answers.prefix}
+        text,
+        {
+            "namespace": namespace,
+            "instances": instances,
+            "prefix": answers.prefix,
+            "instance_prefix": answers.instance_prefix,
+        },
     )
     if answers.publish_target != "none":
         text = text.replace('target  = "none"', f'target  = "{answers.publish_target}"')
     if answers.dependency_preset != "none":
         preset = (root / "presets" / f"{answers.dependency_preset}.toml").read_text(
             encoding="utf-8"
         )
         block = preset.split("[dependencies]", 1)[1]
         text = re.sub(r"\[dependencies\].*?(?=\n\[)", "[dependencies]" + block, text, flags=re.S)
     if text != original_toml:
         toml_path.write_text(text, encoding="utf-8", newline="\n")
         if "knowledge.toml" not in rewritten:
             rewritten.append("knowledge.toml")
 
     # Guarded on existence, not `ignore_errors=True`: the only case this must tolerate
     # silently is the directory already being gone (Task 10 has not created it yet in the
     # shipped template as of this task). `ignore_errors=True` would also swallow a real
     # failure — a permission error or a locked file, plausible on Windows — and `run` would
     # then report success with the stale example content still on disk and nothing
     # downstream to catch it, since the example files carry no {{TOKEN}} for
diff --git a/tests/test_init.py b/tests/test_init.py
index f427860..f6383ea 100644
--- a/tests/test_init.py
+++ b/tests/test_init.py
@@ -13,40 +13,44 @@ def build_template(tmp_path):
     break the template itself (see ruling C12). Only prose-read files carry `{{TOKEN}}`
     placeholders.
     """
     (tmp_path / "knowledge.toml").write_text(
         "[template]\nunconfigured = true\n\n"
         '[project]\nname = "{{PROJECT_NAME}}"\n\n'
         "[vocabulary]\n"
         'ontology_file = "ontology.ttl"\n'
         'namespace = "https://example.com/ontology#"\n'
         'instances = "https://example.com/id/"\n'
         'prefix = "ex"\n'
         'instance_prefix = "app"\n\n'
         '[repo]\ncode_repo = "{{CODE_REPO}}"\n',
         encoding="utf-8",
     )
     ontology = tmp_path / "ontology"
     ontology.mkdir()
     (ontology / "ontology.ttl").write_text(
         "@prefix ex: <https://example.com/ontology#> .\n"
         "@prefix app: <https://example.com/id/> .\n"
+        # Real prefixes, not tokens or placeholders: a real rdflib parse (as
+        # graph.load_graph does) needs rdfs: actually bound, not just present as text.
+        "@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
+        "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
         "\n"
         "# Delete anything here that your domain has no use for; ex: is just a starting point.\n"
         "ex:Concept a rdfs:Class ;\n"
         "    rdfs:label   \"Concept\"@en ;\n"
         "    rdfs:comment \"Write ex: before every term.\"@en .\n",
         encoding="utf-8",
     )
     (ontology / "README.md").write_text("# {{PROJECT_NAME}} ontology\n", encoding="utf-8")
     (ontology / "VERSION").write_text("1.0.0\n", encoding="utf-8")
     docs = tmp_path / "docs"
     docs.mkdir()
     (docs / "README.template.md").write_text("# {{PROJECT_NAME}}\n", encoding="utf-8")
     (tmp_path / "README.md").write_text("# knowledge-template\n", encoding="utf-8")
     agents = tmp_path / ".claude" / "agents"
     agents.mkdir(parents=True)
     (agents / "writer.md").write_text("Audit against {{ONTOLOGY_FILE}}.\n", encoding="utf-8")
     (agents / "interviewer.md").write_text("Interview about {{PROJECT_NAME}}.\n", encoding="utf-8")
     skill = tmp_path / "integrations" / "code-repo" / ".claude" / "skills" / "knowledge-base"
     skill.mkdir(parents=True)
     (skill / "SKILL.md").write_text("Read {{PROJECT_NAME}}'s knowledge base.\n", encoding="utf-8")
@@ -133,40 +137,65 @@ def test_ontology_rewrite_leaves_a_string_literal_alone(tmp_path):
 
 def test_ontology_rewrite_distinguishes_code_from_prose_in_one_pass(tmp_path):
     """All three outcomes together, from a single `run`: the code position rewrites, the
     `#` comment does not, and the `rdfs:comment` string does not — proving the fix tells
     them apart rather than being coincidentally right about any one in isolation."""
     root = build_template(tmp_path)
     init.run(root, ANSWERS)
     text = (root / "ontology" / "ontology.ttl").read_text(encoding="utf-8")
     assert "acme:Concept a rdfs:Class" in text
     assert "ex: is just a starting point" in text
     assert "Write ex: before every term." in text
 
 
 def test_run_removes_the_example_spec_and_empties_the_dump(tmp_path):
     root = build_template(tmp_path)
     init.run(root, ANSWERS)
     assert not (root / "specs" / "example").exists()
     assert "seeded" not in (root / ".metadata" / "dump.sql").read_text(encoding="utf-8")
 
 
+GENUINE_DUMP_SQL = """\
+-- Generated by `knowledge`. Do not edit by hand.
+PRAGMA foreign_keys=OFF;
+BEGIN TRANSACTION;
+INSERT INTO spec (id, title, path, status, confidence, ontology_version, md_hash, ttl_hash, modeled_md_hash, modeled_ttl_hash, modeled_at, modeled_by, verified_at, verified_by, verified_against_commit, demoted_at, demoted_reason, publishes_to_wiki, wiki_page, created_at, updated_at) VALUES ('ghost', 'Ghost', 'specs/ghost', 'draft', NULL, NULL, 'a', 'b', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 1, 'Ghost', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z');
+COMMIT;
+PRAGMA foreign_keys=ON;
+"""
+
+
+def test_run_empties_a_dump_that_has_real_insert_rows(tmp_path):
+    """Ruling C23. Round 1's own dump.sql fixture ("-- seeded\\n", a bare SQL comment) had
+    nothing for db.connect's reload-from-dump to actually reload — exactly why this slipped
+    through every test until now. A generated repository's real dump.sql (Task 10's shipped
+    one carries a genuine `INSERT INTO spec ...` row for `example`) must end up with no
+    INSERT rows at all, not just a changed comment: deleting only the `.db` file achieves
+    nothing, because `db.connect` rebuilds the database from `dump.sql` whenever the `.db`
+    was just deleted and a dump file is still present."""
+    root = build_template(tmp_path)
+    (root / ".metadata" / "dump.sql").write_text(GENUINE_DUMP_SQL, encoding="utf-8")
+    init.run(root, ANSWERS)
+    dump_text = (root / ".metadata" / "dump.sql").read_text(encoding="utf-8")
+    assert "INSERT" not in dump_text
+
+
 def test_run_replaces_the_readme_with_the_template_one(tmp_path):
     root = build_template(tmp_path)
     init.run(root, ANSWERS)
     assert (root / "README.md").read_text(encoding="utf-8") == "# Acme\n"
 
 
 def test_run_refuses_a_configured_repository(tmp_path):
     root = build_template(tmp_path)
     init.run(root, ANSWERS)
     with pytest.raises(RuntimeError) as exc:
         init.run(root, ANSWERS)
     assert "already configured" in str(exc.value)
 
 
 def test_remaining_placeholders_reports_what_is_left(tmp_path):
     root = build_template(tmp_path)
     (root / "stray.md").write_text("# {{PROJECT_NAME}}\n", encoding="utf-8")
     init.run(root, ANSWERS)
     assert any("stray.md" in entry for entry in init.remaining_placeholders(root))
 
@@ -186,20 +215,83 @@ def test_remaining_placeholders_ignores_a_token_shaped_docstring_in_python_sourc
     own source alongside the generated project, exactly what the shipped template does."""
     root = build_template(tmp_path)
     src = root / "src" / "knowledge"
     src.mkdir(parents=True)
     (src / "config.py").write_text(
         'def f():\n    """An unsubstituted {{PLACEHOLDER}} reads as empty."""\n',
         encoding="utf-8",
     )
     init.run(root, ANSWERS)
     assert init.remaining_placeholders(root) == []
 
 
 def test_run_reports_only_files_it_actually_changed(tmp_path):
     """`run` must not claim it rewrote a file whose text it left untouched."""
     root = build_template(tmp_path)
     rewritten = init.run(root, ANSWERS)
     for relative in rewritten:
         assert (root / relative).is_file(), f"{relative} was reported rewritten but is gone"
     # VERSION carries no placeholder and nothing touches it — it must not be claimed.
     assert "ontology/VERSION" not in rewritten
+
+
+def test_ontology_instance_prefix_line_matches_the_configured_instances_iri(tmp_path):
+    """The ontology file's `@prefix app: <...>` line must end up pointing at the same IRI
+    `config.vocabulary.instances` does after init — otherwise every individual any spec
+    writes (`app:Something`) parses under the *old* namespace instead. A spec never
+    declares its own prefixes (see graph.turtle_source), so it resolves against whatever
+    the ontology file's own `@prefix app:` line says."""
+    root = build_template(tmp_path)
+    init.run(root, ANSWERS)
+    text = (root / "ontology" / "ontology.ttl").read_text(encoding="utf-8")
+    config = load_config(root)
+    assert f"@prefix app: <{config.vocabulary.instances}> ." in text
+
+
+def test_bare_instance_prefix_usage_is_rewritten_when_the_instance_prefix_changes(tmp_path):
+    """A code-position `app:Term` usage in the ontology file must follow `instance_prefix`
+    to its new name too, not just the IRI on the declaration line."""
+    root = build_template(tmp_path)
+    ontology_path = root / "ontology" / "ontology.ttl"
+    ontology_path.write_text(
+        ontology_path.read_text(encoding="utf-8") + "app:Seed a ex:Concept .\n",
+        encoding="utf-8",
+    )
+    from dataclasses import replace
+    init.run(root, replace(ANSWERS, instance_prefix="ind"))
+    text = ontology_path.read_text(encoding="utf-8")
+    assert "ind:Seed a acme:Concept ." in text
+    assert "app:Seed" not in text
+
+
+def test_a_rewritten_specs_instance_iri_satisfies_is_instance(tmp_path):
+    """Pins the actual consequence, through the real graph-loading pipeline rather than a
+    hand-built URIRef: `graph.turtle_source` concatenates ontology.ttl's `@prefix`
+    declarations with each spec's bare `.ttl` (a spec never declares its own prefixes), so
+    an individual like `app:Widget` in a spec resolves against whichever IRI the ontology
+    file's `@prefix app:` line names. If that line were left pointed at the old namespace,
+    `is_instance()` would return False for every individual any spec ever writes — which is
+    exactly what silently switches off `graph.dangling_terms`' instance half and the
+    underscore half of `lint.naming_violations`, both of which then report clean without
+    having checked. Uses a spec directory other than "example" because `init` deletes that
+    one — the bug would otherwise go unexercised by every other test in this file too."""
+    root = build_template(tmp_path)
+    demo = root / "specs" / "demo"
+    demo.mkdir(parents=True)
+    (demo / "spec.md").write_text("---\nid: demo\n---\n\n# Demo\n", encoding="utf-8")
+    # Written as a person would author it *after* init — using the project's real prefix
+    # (acme:, matching ANSWERS.prefix below), not the shipped default (ex:) the ontology no
+    # longer declares once init has renamed it.
+    (demo / "spec.ttl").write_text(
+        'app:Widget a acme:Concept ;\n    rdfs:label "Widget"@en .\n', encoding="utf-8"
+    )
+    init.run(root, ANSWERS)
+
+    from knowledge import graph
+    from knowledge.paths import get_paths
+
+    config = load_config(root)
+    paths = get_paths(root, config.vocabulary.ontology_file)
+    g = graph.load_graph(paths, config.vocabulary, ["demo"])
+    widget = config.vocabulary.instance("Widget")
+    assert (widget, None, None) in g, "the individual did not parse under the expected IRI at all"
+    assert config.vocabulary.is_instance(widget)
```
