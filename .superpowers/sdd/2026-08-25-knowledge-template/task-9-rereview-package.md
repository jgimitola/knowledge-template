# Task 9 fix-round 1 scoped diff

FIX_BASE: 6bf11ac
HEAD: 22bb265

## Commits
```
22bb265 fix: confine the prefix rewrite to Turtle code positions, and stop swallowing rmtree errors
```

## Stat
```
 src/knowledge/cli.py  |  2 ++
 src/knowledge/init.py | 77 +++++++++++++++++++++++++++++++++++++++++++++------
 tests/test_init.py    | 38 +++++++++++++++++++++++--
 3 files changed, 107 insertions(+), 10 deletions(-)
```

## Controller's independent verification of the C20 fix
```
code rewritten: True | prefix line rewritten: True
rdfs:comment literal preserved: True | # comment preserved: True
```

## Full diff (-U20)
```diff
diff --git a/src/knowledge/cli.py b/src/knowledge/cli.py
index b8beef1..2cac82a 100644
--- a/src/knowledge/cli.py
+++ b/src/knowledge/cli.py
@@ -664,40 +664,42 @@ def cmd_init(args: argparse.Namespace) -> int:
         project_name=name,
         base_iri=base_iri,
         prefix=prefix,
         instance_prefix=args.instance_prefix or _prompt("Instance prefix", "app"),
         code_repo=args.code_repo if args.code_repo is not None
         else _prompt("Code repository path (blank to disable staleness)"),
         publish_target=args.publish_target or _prompt(
             "Publish target (none/directory/github-wiki)", "none"
         ),
         dependency_preset=args.dependency_preset or _prompt(
             "Dependency preset (none/nextjs)", "none"
         ),
     )
 
     rewritten = init.run(root, answers)
     print(f"configured {name}: rewrote {len(rewritten)} file(s)")
     for relative in rewritten:
         print("  -", relative)
 
     skill = root / "integrations" / "code-repo" / ".claude" / "skills" / "knowledge-base"
+    # Off by default: writing into a second, external repository (the code repo) must be an
+    # explicit request (--install-skill), never a side effect of running `init`.
     if args.install_skill and answers.code_repo:
         destination = (
             (root / answers.code_repo).resolve() / ".claude" / "skills" / "knowledge-base"
         )
         destination.parent.mkdir(parents=True, exist_ok=True)
         shutil.copytree(skill, destination, dirs_exist_ok=True)
         print(f"installed the reading skill into {destination}")
     elif skill.is_dir():
         print(f"\nthe reading skill is at {skill}")
         print(
             "copy it into your code repository's .claude/skills/,"
             " or re-run with --install-skill"
         )
 
     remaining = init.remaining_placeholders(root)
     if remaining:
         print(f"\nwarning: {len(remaining)} placeholder(s) remain; run `knowledge init --check`")
     return 0
 
 
diff --git a/src/knowledge/init.py b/src/knowledge/init.py
index ea6e540..c496349 100644
--- a/src/knowledge/init.py
+++ b/src/knowledge/init.py
@@ -123,66 +123,118 @@ def remaining_placeholders(root: Path) -> list[str]:
 def _rewrite_vocabulary_keys(text: str, values: dict[str, str]) -> str:
     """Rewrite `knowledge.toml`'s `[vocabulary]` namespace/instances/prefix in place.
 
     These three ship as working defaults (`https://example.com/...`, `ex`), not `{{TOKEN}}`
     placeholders — see the module docstring — so `substitute`'s token sweep never touches
     them; they need their own rewrite.
 
     Each key is matched anchored to the start of its own line (`(?m)^key\\s*=\\s*"..."$`)
     rather than replaced as a bare substring, so a value that happens to appear elsewhere in
     the file (or a same-named key, if one existed in another table) could not be hit by
     accident. In the shipped `knowledge.toml`, `namespace` and `instances` each appear on
     exactly one line, and `prefix` — anchored to line-start — matches only the bare `prefix`
     key, never `instance_prefix` or `absorbed_prefixes` (both start with a different word).
     """
     for key, value in values.items():
         pattern = re.compile(rf'(?m)^({re.escape(key)}\s*=\s*)"[^"]*"$')
         text = pattern.sub(lambda m, v=value: f'{m.group(1)}"{v}"', text, count=1)
     return text
 
 
+# A Turtle span a comment-boundary search or the bare-prefix rewrite below must not look
+# inside: a "..." string literal, or a <...> IRI. Both can contain a literal '#' or the
+# prefix text without either meaning what it would in code — a namespace IRI conventionally
+# ends in '#' (<https://acme.test/ontology#>), and a hand-authored rdfs:comment/rdfs:label
+# routinely uses the prefix as English shorthand ("write ex: before every term"). Single
+# double-quoted strings and single-bracketed IRIs only: the seed ontology never uses
+# triple-quoted string literals, an escaped '"' inside one, or a nested '<'/'>' inside an
+# IRI, so this one-pass regex does not need to handle those.
+PROTECTED_SPAN = re.compile(r'"(?:\\.|[^"\\])*"|<[^<>]*>')
+
+
+def _comment_start(line: str) -> int:
+    """Index of the first '#' in `line` that actually starts a Turtle comment — i.e. one
+    that is not inside a PROTECTED_SPAN. A '#' inside a string literal or an IRI (an
+    ontology namespace IRI ends in one) is not a comment marker, even though a naive
+    `line.find("#")` would treat it as one."""
+    pos = 0
+    for span in PROTECTED_SPAN.finditer(line):
+        idx = line.find("#", pos, span.start())
+        if idx != -1:
+            return idx
+        pos = span.end()
+    idx = line.find("#", pos)
+    return idx if idx != -1 else len(line)
+
+
+def _rewrite_bare_prefix_outside_protected_spans(
+    code: str, pattern: re.Pattern[str], replacement: str
+) -> str:
+    """Apply `pattern.sub(replacement, ...)` to `code`, skipping every PROTECTED_SPAN (a
+    string literal or an IRI) so a prefix quoted as English shorthand inside one is left
+    untouched rather than corrupted."""
+    out: list[str] = []
+    pos = 0
+    for span in PROTECTED_SPAN.finditer(code):
+        out.append(pattern.sub(replacement, code[pos:span.start()]))
+        out.append(span.group(0))
+        pos = span.end()
+    out.append(pattern.sub(replacement, code[pos:]))
+    return "".join(out)
+
+
 def _rewrite_ontology_prefix(text: str, old_prefix: str, new_prefix: str, namespace: str) -> str:
     """Rewrite the ontology file's own vocabulary prefix — its `@prefix` declaration and
     every `old_prefix:Term` usage in the body.
 
     Two bounded passes, in this order:
 
     1. The declaration line itself, matched as a whole so the prefix name and its IRI are
        replaced together: `@prefix ex: <https://example.com/ontology#> .` becomes
        `@prefix acme: <https://acme.test/ontology#> .`. Matched first, while the line still
        reads `old_prefix:`, so pass 2 below cannot see it and mangle the IRI.
     2. Every remaining bare `old_prefix:` — e.g. `ex:Concept`, `rdfs:domain ex:Concept` —
-       renamed to `new_prefix:`. `\\b` anchors the match so it cannot fire inside a longer
-       word (`example:` never matches `\\bex:`, because "ex" there is not followed by a
-       colon) or inside an IRI's host text (`https://example.com/...` has no `:` right after
-       "ex" either). The file is small and hand-authored — three classes, three properties —
-       so a bounded regex is a safe, auditable stand-in for a real Turtle-aware rewrite.
+       renamed to `new_prefix:`, but only where it appears in Turtle *code*. Line by line:
+       `_comment_start` finds where a trailing `# ...` comment begins (if any), and
+       `_rewrite_bare_prefix_outside_protected_spans` skips every string literal and IRI in
+       what remains. Without this, a plain `\\bold_prefix:\\b` sweep over the whole file would
+       also rewrite the prefix everywhere it is used as English shorthand in hand-authored
+       prose — a `#` comment explaining the file, or an `rdfs:comment` value — which the
+       seed ontology (Task 10) does. `\\b` still anchors each code-position match so it
+       cannot fire inside a longer word (`example:` never matches `\\bex:`, because "ex"
+       there is not followed by a colon).
 
     The instance prefix (`app:` by default) is untouched: correction C12 scopes this rewrite
     to the vocabulary's own prefix, matching `_rewrite_vocabulary_keys` above, which likewise
     only rewrites `namespace`/`instances`/`prefix`, not `instance_prefix`.
     """
     declaration = re.compile(rf"@prefix\s+{re.escape(old_prefix)}:\s+<[^>]*>\s*\.")
     text = declaration.sub(f"@prefix {new_prefix}: <{namespace}> .", text, count=1)
+
     bare = re.compile(rf"\b{re.escape(old_prefix)}:")
-    text = bare.sub(f"{new_prefix}:", text)
-    return text
+    lines = []
+    for line in text.split("\n"):
+        cut = _comment_start(line)
+        code, comment = line[:cut], line[cut:]
+        rewritten_code = _rewrite_bare_prefix_outside_protected_spans(code, bare, f"{new_prefix}:")
+        lines.append(rewritten_code + comment)
+    return "\n".join(lines)
 
 
 def _reset_metadata(root: Path) -> None:
     """An empty database dumped fresh, so the generated repository starts with no history
     of specs that are no longer there."""
     from knowledge import db
     from knowledge.paths import get_paths
 
     paths = get_paths(root, load_config(root).vocabulary.ontology_file)
     paths.db.unlink(missing_ok=True)
     conn = db.connect(paths)
     db.save(conn, paths)
     conn.close()
     paths.db.unlink(missing_ok=True)
 
 
 def run(root: Path, answers: Answers) -> list[str]:
     """Bind the template to one project. Returns the files it actually rewrote — a path
     only lands in this list when its text changed, so the caller's count is one this
     function earned rather than one it merely attempted."""
@@ -214,35 +266,44 @@ def run(root: Path, answers: Answers) -> list[str]:
 
     toml_path = root / "knowledge.toml"
     original_toml = toml_path.read_text(encoding="utf-8")
     text = re.sub(r"\[template\]\nunconfigured = true\n\n?", "", original_toml, count=1)
     text = _rewrite_vocabulary_keys(
         text, {"namespace": namespace, "instances": instances, "prefix": answers.prefix}
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
 
-    shutil.rmtree(root / "specs" / "example", ignore_errors=True)
+    # Guarded on existence, not `ignore_errors=True`: the only case this must tolerate
+    # silently is the directory already being gone (Task 10 has not created it yet in the
+    # shipped template as of this task). `ignore_errors=True` would also swallow a real
+    # failure — a permission error or a locked file, plausible on Windows — and `run` would
+    # then report success with the stale example content still on disk and nothing
+    # downstream to catch it, since the example files carry no {{TOKEN}} for
+    # `remaining_placeholders` to flag.
+    example_dir = root / "specs" / "example"
+    if example_dir.exists():
+        shutil.rmtree(example_dir)
     _reset_metadata(root)
 
     template_readme = root / "docs" / "README.template.md"
     if template_readme.is_file():
         shutil.move(str(template_readme), str(root / "README.md"))
         # It moves rather than staying rewritten-in-place, so its manifest entry (added by
         # `substitute` above, if it carried a token) is swapped for the path it lives at
         # now — every entry the caller sees must point at a file that still exists there.
         relative = "docs/README.template.md"
         if relative in rewritten:
             rewritten.remove(relative)
         rewritten.append("README.md")
 
     return sorted(set(rewritten))
diff --git a/tests/test_init.py b/tests/test_init.py
index 3918b12..f427860 100644
--- a/tests/test_init.py
+++ b/tests/test_init.py
@@ -14,41 +14,44 @@ def build_template(tmp_path):
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
         "\n"
-        "ex:Concept a rdfs:Class ; rdfs:label \"Concept\"@en .\n",
+        "# Delete anything here that your domain has no use for; ex: is just a starting point.\n"
+        "ex:Concept a rdfs:Class ;\n"
+        "    rdfs:label   \"Concept\"@en ;\n"
+        "    rdfs:comment \"Write ex: before every term.\"@en .\n",
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
     example = tmp_path / "specs" / "example"
     example.mkdir(parents=True)
     (example / "spec.md").write_text("---\nid: example\n---\n\n# Example\n", encoding="utf-8")
     (example / "spec.ttl").write_text("# example\n", encoding="utf-8")
     (tmp_path / ".metadata").mkdir()
@@ -85,45 +88,76 @@ def test_run_substitutes_every_placeholder(tmp_path):
 
 def test_run_produces_a_loadable_config(tmp_path):
     root = build_template(tmp_path)
     init.run(root, ANSWERS)
     config = load_config(root)
     assert config.project_name == "Acme"
     assert config.vocabulary.namespace == "https://acme.test/ontology#"
     assert config.vocabulary.prefix == "acme"
     assert config.unconfigured is False
     assert config.code_repo is not None
 
 
 def test_run_rewrites_the_ontology_prefix_lines(tmp_path):
     root = build_template(tmp_path)
     init.run(root, ANSWERS)
     text = (root / "ontology" / "ontology.ttl").read_text(encoding="utf-8")
     assert "@prefix acme: <https://acme.test/ontology#> ." in text
 
 
 def test_run_rewrites_ontology_term_usages_too(tmp_path):
+    """The code positions still rewrite: `ex:Concept a rdfs:Class` becomes `acme:...`."""
     root = build_template(tmp_path)
     init.run(root, ANSWERS)
     text = (root / "ontology" / "ontology.ttl").read_text(encoding="utf-8")
     assert "acme:Concept a rdfs:Class" in text
-    assert "ex:" not in text
+    assert "ex:Concept" not in text
+
+
+def test_ontology_rewrite_leaves_a_hash_comment_alone(tmp_path):
+    """A `#` comment using the prefix as English shorthand ("ex: is just a starting point")
+    is prose a person reads, not code — it must survive untouched, not become `acme:`."""
+    root = build_template(tmp_path)
+    init.run(root, ANSWERS)
+    text = (root / "ontology" / "ontology.ttl").read_text(encoding="utf-8")
+    assert "ex: is just a starting point" in text
+
+
+def test_ontology_rewrite_leaves_a_string_literal_alone(tmp_path):
+    """An `rdfs:comment` string quoting the prefix as shorthand ("Write ex: before every
+    term.") is prose too — a blind \\bold_prefix:\\b sweep would corrupt it into "acme:"."""
+    root = build_template(tmp_path)
+    init.run(root, ANSWERS)
+    text = (root / "ontology" / "ontology.ttl").read_text(encoding="utf-8")
+    assert "Write ex: before every term." in text
+
+
+def test_ontology_rewrite_distinguishes_code_from_prose_in_one_pass(tmp_path):
+    """All three outcomes together, from a single `run`: the code position rewrites, the
+    `#` comment does not, and the `rdfs:comment` string does not — proving the fix tells
+    them apart rather than being coincidentally right about any one in isolation."""
+    root = build_template(tmp_path)
+    init.run(root, ANSWERS)
+    text = (root / "ontology" / "ontology.ttl").read_text(encoding="utf-8")
+    assert "acme:Concept a rdfs:Class" in text
+    assert "ex: is just a starting point" in text
+    assert "Write ex: before every term." in text
 
 
 def test_run_removes_the_example_spec_and_empties_the_dump(tmp_path):
     root = build_template(tmp_path)
     init.run(root, ANSWERS)
     assert not (root / "specs" / "example").exists()
     assert "seeded" not in (root / ".metadata" / "dump.sql").read_text(encoding="utf-8")
 
 
 def test_run_replaces_the_readme_with_the_template_one(tmp_path):
     root = build_template(tmp_path)
     init.run(root, ANSWERS)
     assert (root / "README.md").read_text(encoding="utf-8") == "# Acme\n"
 
 
 def test_run_refuses_a_configured_repository(tmp_path):
     root = build_template(tmp_path)
     init.run(root, ANSWERS)
     with pytest.raises(RuntimeError) as exc:
         init.run(root, ANSWERS)
```
