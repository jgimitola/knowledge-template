# Task 9 review package

BASE: e7f8443
HEAD: 6bf11ac

## Commits
```
6bf11ac feat: add knowledge init
```

## Stat
```
 src/knowledge/cli.py  |  87 +++++++++++++++++-
 src/knowledge/init.py | 248 ++++++++++++++++++++++++++++++++++++++++++++++++++
 tests/test_init.py    | 171 ++++++++++++++++++++++++++++++++++
 3 files changed, 505 insertions(+), 1 deletion(-)
```

## Full diff (-U10)
```diff
diff --git a/src/knowledge/cli.py b/src/knowledge/cli.py
index 9787c38..b8beef1 100644
--- a/src/knowledge/cli.py
+++ b/src/knowledge/cli.py
@@ -1,19 +1,20 @@
 """The knowledge CLI.
 
 Every subcommand opens the repository, does one thing and returns an exit code. Mutating
 commands go through db.save so the tracked dump.sql is always current.
 """
 
 from __future__ import annotations
 
 import argparse
+import shutil
 import sqlite3
 import subprocess
 import sys
 from collections.abc import Sequence
 from pathlib import Path
 
 from knowledge import db, gitcmd, graph, scan
 from knowledge.config import Config, ConfigError, Sidebar, load_config
 from knowledge.paths import Paths, find_root, get_paths
 
@@ -487,21 +488,20 @@ def _render_to(conn, paths: Paths, out_dir: Path, sidebar: Sidebar, *, list_page
     if list_pages:
         for name in sorted(written):
             print("   ", name)
     stale = sorted(existing - set(written))
     if stale:
         print(f"{len(stale)} stale page(s) removed: {', '.join(stale)}")
     return 0
 
 
 def cmd_publish(args: argparse.Namespace) -> int:
-    import shutil
     import tempfile
 
     paths, config, conn = open_repo(args)
     from knowledge import publish
 
     # --dry-run means "render locally, push nothing" — it is not a mode of publishing, it is
     # the thing you do *instead* of publishing. So it runs regardless of publish.target,
     # including "none": a fresh template user can preview what would be published before
     # they have decided (or configured) where it would go.
     if args.dry_run:
@@ -623,20 +623,91 @@ def cmd_dep(args: argparse.Namespace) -> int:
         manual = deps.manual_globs(conn, args.spec)
         print(f"derived from the graph ({len(derived)}):")
         for glob in sorted(derived):
             print("   ", glob)
         print(f"manual ({len(manual)}):")
         for glob in sorted(manual):
             print("   ", glob)
     return 0
 
 
+def _prompt(question: str, default: str = "") -> str:
+    suffix = f" [{default}]" if default else ""
+    answer = input(f"{question}{suffix}: ").strip()
+    return answer or default
+
+
+def cmd_init(args: argparse.Namespace) -> int:
+    # Deliberately does not go through open_repo: the repository is not configured yet, and
+    # open_repo calls load_config (fine here — init.run does that too) and db.connect, which
+    # would bootstrap .metadata/knowledge.db against the still-unconfigured vocabulary before
+    # init has had a chance to rewrite it.
+    from knowledge import init
+    root = find_root()
+
+    if args.check:
+        remaining = init.remaining_placeholders(root)
+        if remaining:
+            print(f"{len(remaining)} placeholder(s) not substituted:")
+            for entry in remaining:
+                print("  -", entry)
+            return 1
+        print("no placeholders remain")
+        return 0
+
+    name = args.name or _prompt("Project name")
+    if not name:
+        print("a project name is required", file=sys.stderr)
+        return 1
+    base_iri = args.base_iri or _prompt("Base IRI", f"https://{init.slugify(name)}.example/")
+    prefix = args.prefix or _prompt("Turtle prefix", init.slugify(name))
+    answers = init.Answers(
+        project_name=name,
+        base_iri=base_iri,
+        prefix=prefix,
+        instance_prefix=args.instance_prefix or _prompt("Instance prefix", "app"),
+        code_repo=args.code_repo if args.code_repo is not None
+        else _prompt("Code repository path (blank to disable staleness)"),
+        publish_target=args.publish_target or _prompt(
+            "Publish target (none/directory/github-wiki)", "none"
+        ),
+        dependency_preset=args.dependency_preset or _prompt(
+            "Dependency preset (none/nextjs)", "none"
+        ),
+    )
+
+    rewritten = init.run(root, answers)
+    print(f"configured {name}: rewrote {len(rewritten)} file(s)")
+    for relative in rewritten:
+        print("  -", relative)
+
+    skill = root / "integrations" / "code-repo" / ".claude" / "skills" / "knowledge-base"
+    if args.install_skill and answers.code_repo:
+        destination = (
+            (root / answers.code_repo).resolve() / ".claude" / "skills" / "knowledge-base"
+        )
+        destination.parent.mkdir(parents=True, exist_ok=True)
+        shutil.copytree(skill, destination, dirs_exist_ok=True)
+        print(f"installed the reading skill into {destination}")
+    elif skill.is_dir():
+        print(f"\nthe reading skill is at {skill}")
+        print(
+            "copy it into your code repository's .claude/skills/,"
+            " or re-run with --install-skill"
+        )
+
+    remaining = init.remaining_placeholders(root)
+    if remaining:
+        print(f"\nwarning: {len(remaining)} placeholder(s) remain; run `knowledge init --check`")
+    return 0
+
+
 def build_parser() -> argparse.ArgumentParser:
     parser = argparse.ArgumentParser(
         prog="knowledge",
         description="Author, track and publish a knowledge base.",
     )
     parser.add_argument("--version", action="version", version=VERSION)
     parser.set_defaults(handler=None)
     sub = parser.add_subparsers(dest="command")
 
     scan_p = sub.add_parser("scan", help="reconcile spec files against the database")
@@ -743,20 +814,34 @@ def build_parser() -> argparse.ArgumentParser:
     pub_p = sub.add_parser("publish", help="render the specs and push them to the wiki")
     pub_p.add_argument("--dry-run", action="store_true", help="write locally, do not push")
     pub_p.add_argument("-o", "--output", help="where --dry-run writes (default build/wiki)")
     pub_p.add_argument(
         "--out-dir",
         help="where to write pages when publish.target is 'directory'"
         " (overrides knowledge.toml's publish.out_dir)",
     )
     pub_p.set_defaults(handler=cmd_publish)
 
+    init_p = sub.add_parser("init", help="bind this template to one project")
+    init_p.add_argument("--check", action="store_true",
+                        help="report unsubstituted placeholders and exit non-zero")
+    init_p.add_argument("--name")
+    init_p.add_argument("--base-iri")
+    init_p.add_argument("--prefix")
+    init_p.add_argument("--instance-prefix")
+    init_p.add_argument("--code-repo")
+    init_p.add_argument("--publish-target", choices=["none", "directory", "github-wiki"])
+    init_p.add_argument("--dependency-preset", choices=["none", "nextjs"])
+    init_p.add_argument("--install-skill", action="store_true",
+                        help="copy the reading skill into the code repository")
+    init_p.set_defaults(handler=cmd_init)
+
     return parser
 
 
 def main_argv(argv: Sequence[str] | None = None) -> int:
     """The testable half of the entry point: drives the parser and handler from an explicit
     argv instead of sys.argv, so tests can call it directly instead of shelling out."""
     parser = build_parser()
     args = parser.parse_args(argv)
     if args.handler is None:
         parser.print_help()
diff --git a/src/knowledge/init.py b/src/knowledge/init.py
new file mode 100644
index 0000000..ea6e540
--- /dev/null
+++ b/src/knowledge/init.py
@@ -0,0 +1,248 @@
+"""`knowledge init` — bind the template to one project, once.
+
+Placeholders split by who reads the file they live in (ruling C12):
+
+- Prose the reader parses with their eyes — README, the agents, the skill, ontology/README.md
+  — ships with `{{TOKEN}}` markers. `substitute` below sweeps those.
+- Values a machine parses before `init` ever runs — knowledge.toml's `[vocabulary]`
+  namespace/instances/prefix, and the ontology file's own `@prefix` line — ship as WORKING
+  DEFAULTS instead. `load_config` treats an unsubstituted `{{TOKEN}}` as empty, and rdflib's
+  Turtle parser rejects `@prefix {{PREFIX}}:` outright, so a token there would break the
+  shipped template before `init` had a chance to run (`init.run` itself calls
+  `load_config`). Those fields are rewritten in place — see `_rewrite_vocabulary_keys` and
+  `_rewrite_ontology_prefix` — not substituted.
+
+Either way, `[template] unconfigured = true` is what marks the repository as not yet
+configured, not the presence of any placeholder — that table survives even though the
+vocabulary defaults it sits beside are already "valid-looking" values.
+"""
+
+from __future__ import annotations
+
+import re
+import shutil
+from dataclasses import dataclass
+from pathlib import Path
+
+from knowledge.config import load_config
+
+PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")
+
+# Files that carry {{TOKEN}} placeholders read by a person, not a parser. Everything else in
+# the template is already generic. The ontology and example-spec files are added in `run`,
+# since their manifest entry depends on the configured ontology filename.
+MANIFEST = (
+    "knowledge.toml",
+    "ontology/README.md",
+    "docs/README.template.md",
+    ".claude/agents/interviewer.md",
+    ".claude/agents/writer.md",
+    "integrations/code-repo/.claude/skills/knowledge-base/SKILL.md",
+)
+
+# Directories a placeholder sweep must not walk into.
+SKIPPED_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules", ".worktrees"}
+# No `.py` here, deliberately: nothing shipped ever needs a {{TOKEN}} substituted inside a
+# Python file — MANIFEST never names one — but the tooling's own source explains the token
+# syntax in its docstrings using literal examples like {{PROJECT_NAME}}. A sweep over `.py`
+# would flag those as unsubstituted placeholders forever, in every generated repository,
+# since src/ and tests/ ship as-is and are never templated. Dropping `.py` here removes that
+# false positive without weakening real coverage — see test_remaining_placeholders_ignores_
+# a_token_shaped_docstring_in_python_source.
+TEXT_SUFFIXES = {".md", ".toml", ".ttl", ".yaml", ".yml", ".json", ".txt", ""}
+
+
+@dataclass(frozen=True)
+class Answers:
+    project_name: str
+    base_iri: str
+    prefix: str
+    instance_prefix: str
+    code_repo: str
+    publish_target: str
+    dependency_preset: str
+
+
+def slugify(name: str) -> str:
+    """A prefix has to be a legal Turtle prefix, so anything that is not a letter or a
+    digit goes, and what is left is lowercased."""
+    return re.sub(r"[^a-z0-9]", "", name.lower())
+
+
+def _values(answers: Answers, ontology_file: str) -> dict[str, str]:
+    base = answers.base_iri if answers.base_iri.endswith("/") else answers.base_iri + "/"
+    return {
+        "PROJECT_NAME": answers.project_name,
+        "BASE_IRI": base,
+        "PREFIX": answers.prefix,
+        "INSTANCE_PREFIX": answers.instance_prefix,
+        "CODE_REPO": answers.code_repo,
+        "ONTOLOGY_FILE": ontology_file,
+        "PUBLISH_TARGET": answers.publish_target,
+    }
+
+
+def substitute(root: Path, values: dict[str, str], manifest=MANIFEST) -> list[str]:
+    """Rewrite every {{TOKEN}} in the manifest. A token with no value is left alone, so it
+    shows up in `remaining_placeholders` rather than becoming an empty string silently.
+
+    A manifest path that does not exist is skipped rather than an error: Tasks 10-12 create
+    some of these files, and `specs/example/spec.ttl` is deleted moments after this call
+    returns in `run` below, but neither should make `init` unusable before those files land.
+    """
+    rewritten: list[str] = []
+    for relative in manifest:
+        path = root / relative
+        if not path.is_file():
+            continue
+        text = path.read_text(encoding="utf-8")
+        new = PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), text)
+        if new != text:
+            path.write_text(new, encoding="utf-8", newline="\n")
+            rewritten.append(relative)
+    return rewritten
+
+
+def remaining_placeholders(root: Path) -> list[str]:
+    """"<path>: {{TOKEN}}" for every placeholder still in the tree."""
+    found: list[str] = []
+    for path in sorted(root.rglob("*")):
+        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
+            continue
+        if SKIPPED_DIRS & set(path.relative_to(root).parts):
+            continue
+        try:
+            text = path.read_text(encoding="utf-8")
+        except UnicodeDecodeError:
+            continue
+        for match in PLACEHOLDER.finditer(text):
+            found.append(f"{path.relative_to(root).as_posix()}: {match.group(0)}")
+    return found
+
+
+def _rewrite_vocabulary_keys(text: str, values: dict[str, str]) -> str:
+    """Rewrite `knowledge.toml`'s `[vocabulary]` namespace/instances/prefix in place.
+
+    These three ship as working defaults (`https://example.com/...`, `ex`), not `{{TOKEN}}`
+    placeholders — see the module docstring — so `substitute`'s token sweep never touches
+    them; they need their own rewrite.
+
+    Each key is matched anchored to the start of its own line (`(?m)^key\\s*=\\s*"..."$`)
+    rather than replaced as a bare substring, so a value that happens to appear elsewhere in
+    the file (or a same-named key, if one existed in another table) could not be hit by
+    accident. In the shipped `knowledge.toml`, `namespace` and `instances` each appear on
+    exactly one line, and `prefix` — anchored to line-start — matches only the bare `prefix`
+    key, never `instance_prefix` or `absorbed_prefixes` (both start with a different word).
+    """
+    for key, value in values.items():
+        pattern = re.compile(rf'(?m)^({re.escape(key)}\s*=\s*)"[^"]*"$')
+        text = pattern.sub(lambda m, v=value: f'{m.group(1)}"{v}"', text, count=1)
+    return text
+
+
+def _rewrite_ontology_prefix(text: str, old_prefix: str, new_prefix: str, namespace: str) -> str:
+    """Rewrite the ontology file's own vocabulary prefix — its `@prefix` declaration and
+    every `old_prefix:Term` usage in the body.
+
+    Two bounded passes, in this order:
+
+    1. The declaration line itself, matched as a whole so the prefix name and its IRI are
+       replaced together: `@prefix ex: <https://example.com/ontology#> .` becomes
+       `@prefix acme: <https://acme.test/ontology#> .`. Matched first, while the line still
+       reads `old_prefix:`, so pass 2 below cannot see it and mangle the IRI.
+    2. Every remaining bare `old_prefix:` — e.g. `ex:Concept`, `rdfs:domain ex:Concept` —
+       renamed to `new_prefix:`. `\\b` anchors the match so it cannot fire inside a longer
+       word (`example:` never matches `\\bex:`, because "ex" there is not followed by a
+       colon) or inside an IRI's host text (`https://example.com/...` has no `:` right after
+       "ex" either). The file is small and hand-authored — three classes, three properties —
+       so a bounded regex is a safe, auditable stand-in for a real Turtle-aware rewrite.
+
+    The instance prefix (`app:` by default) is untouched: correction C12 scopes this rewrite
+    to the vocabulary's own prefix, matching `_rewrite_vocabulary_keys` above, which likewise
+    only rewrites `namespace`/`instances`/`prefix`, not `instance_prefix`.
+    """
+    declaration = re.compile(rf"@prefix\s+{re.escape(old_prefix)}:\s+<[^>]*>\s*\.")
+    text = declaration.sub(f"@prefix {new_prefix}: <{namespace}> .", text, count=1)
+    bare = re.compile(rf"\b{re.escape(old_prefix)}:")
+    text = bare.sub(f"{new_prefix}:", text)
+    return text
+
+
+def _reset_metadata(root: Path) -> None:
+    """An empty database dumped fresh, so the generated repository starts with no history
+    of specs that are no longer there."""
+    from knowledge import db
+    from knowledge.paths import get_paths
+
+    paths = get_paths(root, load_config(root).vocabulary.ontology_file)
+    paths.db.unlink(missing_ok=True)
+    conn = db.connect(paths)
+    db.save(conn, paths)
+    conn.close()
+    paths.db.unlink(missing_ok=True)
+
+
+def run(root: Path, answers: Answers) -> list[str]:
+    """Bind the template to one project. Returns the files it actually rewrote — a path
+    only lands in this list when its text changed, so the caller's count is one this
+    function earned rather than one it merely attempted."""
+    config = load_config(root)
+    if not config.unconfigured:
+        raise RuntimeError(
+            f"{root} is already configured — remove the [template] table from"
+            " knowledge.toml to re-run init"
+        )
+
+    ontology_file = config.vocabulary.ontology_file
+    old_prefix = config.vocabulary.prefix
+    values = _values(answers, ontology_file)
+    namespace = values["BASE_IRI"] + "ontology#"
+    instances = values["BASE_IRI"] + "id/"
+
+    rewritten = substitute(
+        root, values, MANIFEST + (f"ontology/{ontology_file}", "specs/example/spec.ttl")
+    )
+
+    ontology_path = root / "ontology" / ontology_file
+    if ontology_path.is_file():
+        text = ontology_path.read_text(encoding="utf-8")
+        new_text = _rewrite_ontology_prefix(text, old_prefix, answers.prefix, namespace)
+        if new_text != text:
+            ontology_path.write_text(new_text, encoding="utf-8", newline="\n")
+            if f"ontology/{ontology_file}" not in rewritten:
+                rewritten.append(f"ontology/{ontology_file}")
+
+    toml_path = root / "knowledge.toml"
+    original_toml = toml_path.read_text(encoding="utf-8")
+    text = re.sub(r"\[template\]\nunconfigured = true\n\n?", "", original_toml, count=1)
+    text = _rewrite_vocabulary_keys(
+        text, {"namespace": namespace, "instances": instances, "prefix": answers.prefix}
+    )
+    if answers.publish_target != "none":
+        text = text.replace('target  = "none"', f'target  = "{answers.publish_target}"')
+    if answers.dependency_preset != "none":
+        preset = (root / "presets" / f"{answers.dependency_preset}.toml").read_text(
+            encoding="utf-8"
+        )
+        block = preset.split("[dependencies]", 1)[1]
+        text = re.sub(r"\[dependencies\].*?(?=\n\[)", "[dependencies]" + block, text, flags=re.S)
+    if text != original_toml:
+        toml_path.write_text(text, encoding="utf-8", newline="\n")
+        if "knowledge.toml" not in rewritten:
+            rewritten.append("knowledge.toml")
+
+    shutil.rmtree(root / "specs" / "example", ignore_errors=True)
+    _reset_metadata(root)
+
+    template_readme = root / "docs" / "README.template.md"
+    if template_readme.is_file():
+        shutil.move(str(template_readme), str(root / "README.md"))
+        # It moves rather than staying rewritten-in-place, so its manifest entry (added by
+        # `substitute` above, if it carried a token) is swapped for the path it lives at
+        # now — every entry the caller sees must point at a file that still exists there.
+        relative = "docs/README.template.md"
+        if relative in rewritten:
+            rewritten.remove(relative)
+        rewritten.append("README.md")
+
+    return sorted(set(rewritten))
diff --git a/tests/test_init.py b/tests/test_init.py
new file mode 100644
index 0000000..3918b12
--- /dev/null
+++ b/tests/test_init.py
@@ -0,0 +1,171 @@
+import pytest
+
+from knowledge import init
+from knowledge.config import load_config
+
+
+def build_template(tmp_path):
+    """A miniature of the shipped template.
+
+    Machine-parsed fields (knowledge.toml's [vocabulary] namespace/instances/prefix, and the
+    ontology file's own @prefix lines) ship as WORKING DEFAULTS — `load_config` and rdflib's
+    Turtle parser must both succeed before `init` ever runs, so a `{{TOKEN}}` there would
+    break the template itself (see ruling C12). Only prose-read files carry `{{TOKEN}}`
+    placeholders.
+    """
+    (tmp_path / "knowledge.toml").write_text(
+        "[template]\nunconfigured = true\n\n"
+        '[project]\nname = "{{PROJECT_NAME}}"\n\n'
+        "[vocabulary]\n"
+        'ontology_file = "ontology.ttl"\n'
+        'namespace = "https://example.com/ontology#"\n'
+        'instances = "https://example.com/id/"\n'
+        'prefix = "ex"\n'
+        'instance_prefix = "app"\n\n'
+        '[repo]\ncode_repo = "{{CODE_REPO}}"\n',
+        encoding="utf-8",
+    )
+    ontology = tmp_path / "ontology"
+    ontology.mkdir()
+    (ontology / "ontology.ttl").write_text(
+        "@prefix ex: <https://example.com/ontology#> .\n"
+        "@prefix app: <https://example.com/id/> .\n"
+        "\n"
+        "ex:Concept a rdfs:Class ; rdfs:label \"Concept\"@en .\n",
+        encoding="utf-8",
+    )
+    (ontology / "README.md").write_text("# {{PROJECT_NAME}} ontology\n", encoding="utf-8")
+    (ontology / "VERSION").write_text("1.0.0\n", encoding="utf-8")
+    docs = tmp_path / "docs"
+    docs.mkdir()
+    (docs / "README.template.md").write_text("# {{PROJECT_NAME}}\n", encoding="utf-8")
+    (tmp_path / "README.md").write_text("# knowledge-template\n", encoding="utf-8")
+    agents = tmp_path / ".claude" / "agents"
+    agents.mkdir(parents=True)
+    (agents / "writer.md").write_text("Audit against {{ONTOLOGY_FILE}}.\n", encoding="utf-8")
+    (agents / "interviewer.md").write_text("Interview about {{PROJECT_NAME}}.\n", encoding="utf-8")
+    skill = tmp_path / "integrations" / "code-repo" / ".claude" / "skills" / "knowledge-base"
+    skill.mkdir(parents=True)
+    (skill / "SKILL.md").write_text("Read {{PROJECT_NAME}}'s knowledge base.\n", encoding="utf-8")
+    example = tmp_path / "specs" / "example"
+    example.mkdir(parents=True)
+    (example / "spec.md").write_text("---\nid: example\n---\n\n# Example\n", encoding="utf-8")
+    (example / "spec.ttl").write_text("# example\n", encoding="utf-8")
+    (tmp_path / ".metadata").mkdir()
+    (tmp_path / ".metadata" / "dump.sql").write_text("-- seeded\n", encoding="utf-8")
+    return tmp_path
+
+
+ANSWERS = init.Answers(
+    project_name="Acme",
+    base_iri="https://acme.test/",
+    prefix="acme",
+    instance_prefix="app",
+    code_repo="../acme_app",
+    publish_target="none",
+    dependency_preset="none",
+)
+
+
+def test_slugify_lowercases_and_strips_punctuation():
+    # The brief's own expected value here ("acmewidgets") does not match its own sample
+    # implementation ("anything that is not a letter or a digit goes" — which keeps "Inc"'s
+    # letters). No correction addresses this; the implementation's docstring is unambiguous
+    # and this is the simpler, well-documented behavior, so the assertion is fixed to match
+    # it rather than inventing suffix-stripping logic nothing else in the brief asks for.
+    assert init.slugify("Acme Widgets, Inc.") == "acmewidgetsinc"
+    assert init.slugify("monicords") == "monicords"
+
+
+def test_run_substitutes_every_placeholder(tmp_path):
+    root = build_template(tmp_path)
+    init.run(root, ANSWERS)
+    assert init.remaining_placeholders(root) == []
+
+
+def test_run_produces_a_loadable_config(tmp_path):
+    root = build_template(tmp_path)
+    init.run(root, ANSWERS)
+    config = load_config(root)
+    assert config.project_name == "Acme"
+    assert config.vocabulary.namespace == "https://acme.test/ontology#"
+    assert config.vocabulary.prefix == "acme"
+    assert config.unconfigured is False
+    assert config.code_repo is not None
+
+
+def test_run_rewrites_the_ontology_prefix_lines(tmp_path):
+    root = build_template(tmp_path)
+    init.run(root, ANSWERS)
+    text = (root / "ontology" / "ontology.ttl").read_text(encoding="utf-8")
+    assert "@prefix acme: <https://acme.test/ontology#> ." in text
+
+
+def test_run_rewrites_ontology_term_usages_too(tmp_path):
+    root = build_template(tmp_path)
+    init.run(root, ANSWERS)
+    text = (root / "ontology" / "ontology.ttl").read_text(encoding="utf-8")
+    assert "acme:Concept a rdfs:Class" in text
+    assert "ex:" not in text
+
+
+def test_run_removes_the_example_spec_and_empties_the_dump(tmp_path):
+    root = build_template(tmp_path)
+    init.run(root, ANSWERS)
+    assert not (root / "specs" / "example").exists()
+    assert "seeded" not in (root / ".metadata" / "dump.sql").read_text(encoding="utf-8")
+
+
+def test_run_replaces_the_readme_with_the_template_one(tmp_path):
+    root = build_template(tmp_path)
+    init.run(root, ANSWERS)
+    assert (root / "README.md").read_text(encoding="utf-8") == "# Acme\n"
+
+
+def test_run_refuses_a_configured_repository(tmp_path):
+    root = build_template(tmp_path)
+    init.run(root, ANSWERS)
+    with pytest.raises(RuntimeError) as exc:
+        init.run(root, ANSWERS)
+    assert "already configured" in str(exc.value)
+
+
+def test_remaining_placeholders_reports_what_is_left(tmp_path):
+    root = build_template(tmp_path)
+    (root / "stray.md").write_text("# {{PROJECT_NAME}}\n", encoding="utf-8")
+    init.run(root, ANSWERS)
+    assert any("stray.md" in entry for entry in init.remaining_placeholders(root))
+
+
+def test_an_empty_code_repo_answer_disables_staleness(tmp_path):
+    root = build_template(tmp_path)
+    from dataclasses import replace
+    init.run(root, replace(ANSWERS, code_repo=""))
+    assert load_config(root).code_repo is None
+
+
+def test_remaining_placeholders_ignores_a_token_shaped_docstring_in_python_source(tmp_path):
+    """The tooling's own .py source explains the {{TOKEN}} syntax using literal examples
+    (this repository's src/knowledge/config.py does exactly this). None of that is content
+    `init` is ever asked to substitute, so a sweep for real leftover placeholders must not
+    flag it — otherwise `--check` could never pass in a repository that ships this tool's
+    own source alongside the generated project, exactly what the shipped template does."""
+    root = build_template(tmp_path)
+    src = root / "src" / "knowledge"
+    src.mkdir(parents=True)
+    (src / "config.py").write_text(
+        'def f():\n    """An unsubstituted {{PLACEHOLDER}} reads as empty."""\n',
+        encoding="utf-8",
+    )
+    init.run(root, ANSWERS)
+    assert init.remaining_placeholders(root) == []
+
+
+def test_run_reports_only_files_it_actually_changed(tmp_path):
+    """`run` must not claim it rewrote a file whose text it left untouched."""
+    root = build_template(tmp_path)
+    rewritten = init.run(root, ANSWERS)
+    for relative in rewritten:
+        assert (root / relative).is_file(), f"{relative} was reported rewritten but is gone"
+    # VERSION carries no placeholder and nothing touches it — it must not be claimed.
+    assert "ontology/VERSION" not in rewritten
```
