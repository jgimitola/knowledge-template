"""`knowledge init` — bind the template to one project, once.

Placeholders split by who reads the file they live in (ruling C12):

- Prose the reader parses with their eyes — README, the agents, the skill, ontology/README.md
  — ships with `{{TOKEN}}` markers. `substitute` below sweeps those.
- Values a machine parses before `init` ever runs — knowledge.toml's `[vocabulary]`
  namespace/instances/prefix/instance_prefix, and the ontology file's own two `@prefix`
  lines (the project vocabulary's, and the instance prefix's) — ship as WORKING DEFAULTS
  instead. `load_config` treats an unsubstituted `{{TOKEN}}` as empty, and rdflib's Turtle
  parser rejects `@prefix {{PREFIX}}:` outright, so a token there would break the shipped
  template before `init` had a chance to run (`init.run` itself calls `load_config`). Those
  fields are rewritten in place — see `_rewrite_vocabulary_keys` and
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
# since their manifest entry depends on the configured ontology filename.
MANIFEST = (
    "knowledge.toml",
    "ontology/README.md",
    "docs/README.template.md",
    ".claude/agents/interviewer.md",
    ".claude/agents/writer.md",
    "integrations/code-repo/.claude/skills/knowledge-base/SKILL.md",
)

# Directories a placeholder sweep must not walk into.
SKIPPED_DIRS = {".git", ".venv", "__pycache__", ".pytest_cache", "node_modules", ".worktrees"}
# No `.py` here, deliberately: nothing shipped ever needs a {{TOKEN}} substituted inside a
# Python file — MANIFEST never names one — but the tooling's own source explains the token
# syntax in its docstrings using literal examples like {{PROJECT_NAME}}. A sweep over `.py`
# would flag those as unsubstituted placeholders forever, in every generated repository,
# since src/ and tests/ ship as-is and are never templated. Dropping `.py` here removes that
# false positive without weakening real coverage — see test_remaining_placeholders_ignores_
# a_token_shaped_docstring_in_python_source.
TEXT_SUFFIXES = {".md", ".toml", ".ttl", ".yaml", ".yml", ".json", ".txt", ""}


@dataclass(frozen=True)
class Answers:
    project_name: str
    base_iri: str
    prefix: str
    instance_prefix: str
    code_repo: str
    publish_target: str
    dependency_preset: str


def slugify(name: str) -> str:
    """A prefix has to be a legal Turtle prefix, so anything that is not a letter or a
    digit goes, and what is left is lowercased."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _values(answers: Answers, ontology_file: str) -> dict[str, str]:
    base = answers.base_iri if answers.base_iri.endswith("/") else answers.base_iri + "/"
    return {
        "PROJECT_NAME": answers.project_name,
        "BASE_IRI": base,
        "PREFIX": answers.prefix,
        "INSTANCE_PREFIX": answers.instance_prefix,
        "CODE_REPO": answers.code_repo,
        "ONTOLOGY_FILE": ontology_file,
        "PUBLISH_TARGET": answers.publish_target,
    }


def substitute(root: Path, values: dict[str, str], manifest=MANIFEST) -> list[str]:
    """Rewrite every {{TOKEN}} in the manifest. A token with no value is left alone, so it
    shows up in `remaining_placeholders` rather than becoming an empty string silently.

    A manifest path that does not exist is skipped rather than an error: Tasks 10-12 create
    some of these files, and `specs/example/spec.ttl` is deleted moments after this call
    returns in `run` below, but neither should make `init` unusable before those files land.
    """
    rewritten: list[str] = []
    for relative in manifest:
        path = root / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        new = PLACEHOLDER.sub(lambda m: values.get(m.group(1), m.group(0)), text)
        if new != text:
            path.write_text(new, encoding="utf-8", newline="\n")
            rewritten.append(relative)
    return rewritten


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
    """Rewrite `knowledge.toml`'s `[vocabulary]` namespace/instances/prefix/instance_prefix
    in place.

    These four ship as working defaults (`https://example.com/...`, `ex`, `app`), not
    `{{TOKEN}}` placeholders — see the module docstring — so `substitute`'s token sweep
    never touches them; they need their own rewrite. `instance_prefix` is included so
    knowledge.toml stays consistent with the ontology file's own instance `@prefix` line
    (see `_rewrite_ontology_prefix`) — both must name the same prefix, or SPARQL queries
    built from `vocab.sparql_prefixes` would declare `app:` while specs actually use
    whatever `answers.instance_prefix` renamed it to.

    Each key is matched anchored to the start of its own line (`(?m)^key\\s*=\\s*"..."$`)
    rather than replaced as a bare substring, so a value that happens to appear elsewhere in
    the file (or a same-named key, if one existed in another table) could not be hit by
    accident. In the shipped `knowledge.toml`, `namespace`, `instances` and `instance_prefix`
    each appear on exactly one line, and `prefix` — anchored to line-start — matches only
    the bare `prefix` key, never `instance_prefix` or `absorbed_prefixes` (both start with a
    different word).
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
    that is not inside a PROTECTED_SPAN. A '#' inside a string literal or an IRI (an
    ontology namespace IRI ends in one) is not a comment marker, even though a naive
    `line.find("#")` would treat it as one."""
    pos = 0
    for span in PROTECTED_SPAN.finditer(line):
        idx = line.find("#", pos, span.start())
        if idx != -1:
            return idx
        pos = span.end()
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


def _rewrite_prefix_pair(text: str, old_prefix: str, new_prefix: str, namespace: str) -> str:
    """Rewrite one Turtle `@prefix` declaration — its name and IRI together — plus every
    bare `old_prefix:Term` usage in the body. Shared by `_rewrite_ontology_prefix` below for
    both prefixes the ontology file declares: the project vocabulary's own prefix (`ex:` by
    default) and the instance prefix (`app:` by default) any spec's individuals use.

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


def _rewrite_ontology_prefix(
    text: str,
    old_prefix: str,
    new_prefix: str,
    namespace: str,
    old_instance_prefix: str,
    new_instance_prefix: str,
    instances: str,
) -> str:
    """Rewrite both prefixes the ontology file declares, via two independent
    `_rewrite_prefix_pair` passes: the project vocabulary's own prefix (`ex:` by default,
    rewritten first) and the instance prefix (`app:` by default, rewritten second).

    The instance prefix is not optional to rewrite. `graph.turtle_source` concatenates
    ontology.ttl (which declares both `@prefix` lines) with every spec's bare `.ttl` — a
    spec never declares its own prefixes, so an individual like `app:Widget` in a spec
    resolves against *this file's* `@prefix app:` declaration when the whole thing is parsed
    as one Turtle document. Leaving that declaration pointed at the old instances IRI would
    silently detach every individual any spec ever writes from `config.vocabulary.instances`
    — `vocab.is_instance()` tests a literal IRI prefix, so it would return False for all of
    them without erroring, which in turn switches off `graph.dangling_terms`'s instance half
    and the underscore half of `lint.naming_violations` while both keep reporting clean.

    The two passes are independent — each searches only for its own *old* prefix text, so
    rewriting `ex:` first can't touch anything the `app:` pass is about, and vice versa —
    order between them does not matter for correctness (project prefix is rewritten first
    here only because that mirrors the order the two `@prefix` lines are declared).
    """
    text = _rewrite_prefix_pair(text, old_prefix, new_prefix, namespace)
    text = _rewrite_prefix_pair(text, old_instance_prefix, new_instance_prefix, instances)
    return text


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
    config = load_config(root)
    if not config.unconfigured:
        raise RuntimeError(
            f"{root} is already configured — remove the [template] table from"
            " knowledge.toml to re-run init"
        )

    ontology_file = config.vocabulary.ontology_file
    old_prefix = config.vocabulary.prefix
    old_instance_prefix = config.vocabulary.instance_prefix
    values = _values(answers, ontology_file)
    namespace = values["BASE_IRI"] + "ontology#"
    instances = values["BASE_IRI"] + "id/"

    rewritten = substitute(
        root, values, MANIFEST + (f"ontology/{ontology_file}", "specs/example/spec.ttl")
    )

    ontology_path = root / "ontology" / ontology_file
    if ontology_path.is_file():
        text = ontology_path.read_text(encoding="utf-8")
        new_text = _rewrite_ontology_prefix(
            text, old_prefix, answers.prefix, namespace,
            old_instance_prefix, answers.instance_prefix, instances,
        )
        if new_text != text:
            ontology_path.write_text(new_text, encoding="utf-8", newline="\n")
            if f"ontology/{ontology_file}" not in rewritten:
                rewritten.append(f"ontology/{ontology_file}")

    toml_path = root / "knowledge.toml"
    original_toml = toml_path.read_text(encoding="utf-8")
    text = re.sub(r"\[template\]\nunconfigured = true\n\n?", "", original_toml, count=1)
    # instance_prefix is rewritten alongside namespace/instances/prefix — not just those
    # three — so knowledge.toml stays consistent with the ontology file's own instance
    # `@prefix` line above: if they disagreed, `vocab.sparql_prefixes` and `cmd_describe`'s
    # default term prefix would still say `app:` while specs actually use whatever
    # `answers.instance_prefix` renamed it to.
    text = _rewrite_vocabulary_keys(
        text,
        {
            "namespace": namespace,
            "instances": instances,
            "prefix": answers.prefix,
            "instance_prefix": answers.instance_prefix,
        },
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
    # `remaining_placeholders` to flag.
    example_dir = root / "specs" / "example"
    if example_dir.exists():
        shutil.rmtree(example_dir)
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
