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
  `_rewrite_ontology_prefixes` — not substituted.

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
    (see `_rewrite_ontology_prefixes`) — both must name the same prefix, or SPARQL queries
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


def _rewrite_bare_prefixes_outside_protected_spans(
    code: str, pattern: re.Pattern[str], replacement
) -> str:
    """Apply `pattern.sub(replacement, ...)` to `code`, skipping every PROTECTED_SPAN (a
    string literal or an IRI) so a prefix quoted as English shorthand inside one is left
    untouched rather than corrupted. `replacement` may be a string or a match-to-string
    function, exactly as `re.sub` accepts."""
    out: list[str] = []
    pos = 0
    for span in PROTECTED_SPAN.finditer(code):
        out.append(pattern.sub(replacement, code[pos:span.start()]))
        out.append(span.group(0))
        pos = span.end()
    out.append(pattern.sub(replacement, code[pos:]))
    return "".join(out)


def _rewrite_ontology_prefixes(text: str, mapping: dict[str, tuple[str, str]]) -> str:
    """Rewrite every declared prefix the ontology file names, and every bare usage of it, in
    ONE simultaneous substitution (ruling C24).

    `mapping` sends each OLD prefix name to `(new_prefix_name, new_namespace_iri)`. For the
    ontology's two configurable prefixes that is
    `{old_prefix: (new_prefix, namespace), old_instance_prefix: (new_instance_prefix, instances)}`.

    A single pass is the only correct approach when the two prefixes may swap
    (`--prefix app --instance-prefix ex`) or one may shadow the other's shipped name
    (`--prefix app`, where `app` is the shipped instance prefix). Two sequential passes let
    the second observe the first's output: after pass 1 renames `ex:` to `app:`, a pass 2
    that searches for `app:` would match the line pass 1 just wrote and rewrite it again.
    Keying the substitution on OLD prefix names and applying it once removes that hazard —
    it is the classic in-place swap, and only a simultaneous rewrite gets it right.

    Declaration lines and body usages are handled on disjoint sets of lines (a line either
    is a `@prefix` declaration or it is not), so no rewritten declaration can be seen a
    second time by the body pass. A `@prefix` line whose prefix is not in `mapping`
    (`rdf:`, `rdfs:`, …) is left exactly as it stands.
    """
    if not mapping:
        return text

    # Longest name first so an alternation never matches a prefix that is itself a prefix of
    # another (e.g. `ex` before `example`); `\b` and the trailing `:` already prevent that,
    # but ordering keeps the intent explicit.
    alternation = "|".join(re.escape(name) for name in sorted(mapping, key=len, reverse=True))
    declaration = re.compile(rf"^(\s*@prefix\s+)({alternation})(:\s+)<[^>]*>(\s*\.\s*)$")
    bare = re.compile(rf"\b({alternation}):")

    def rename(match: re.Match[str]) -> str:
        return f"{mapping[match.group(1)][0]}:"

    lines: list[str] = []
    for line in text.split("\n"):
        if line.lstrip().startswith("@prefix"):
            match = declaration.match(line)
            if match:
                new_prefix, new_iri = mapping[match.group(2)]
                lines.append(f"{match.group(1)}{new_prefix}{match.group(3)}<{new_iri}>{match.group(4)}")
            else:
                lines.append(line)
            continue
        cut = _comment_start(line)
        code, comment = line[:cut], line[cut:]
        lines.append(_rewrite_bare_prefixes_outside_protected_spans(code, bare, rename) + comment)
    return "\n".join(lines)


def _reset_metadata(root: Path) -> None:
    """An empty database dumped fresh, so the generated repository starts with no history
    of specs that are no longer there. (Ruling C23.)

    Both `paths.db` and `paths.dump` must go before `db.connect` runs — deleting only the
    `.db` achieves nothing on its own, because `dump.sql` is the tracked artifact and
    `db.connect` rebuilds the database from it whenever the database file was just deleted
    and a dump file is still present (see its own docstring: that reload exists so a pulled
    dump.sql newer than the local db is picked up, which is exactly what an inherited,
    checked-in dump.sql looks like here). Deleting only `paths.db` left a generated
    repository's dump.sql carrying real INSERT rows for specs that no longer exist on disk
    (Task 10's shipped `.metadata/dump.sql` has one for `example`) — `db.connect` reloaded
    them into the "fresh" database and `db.save` wrote them right back out unchanged, so
    `scan` in the generated repository reported `missing 1: example has a row but no
    files` as the very first thing a new user saw.
    """
    from knowledge import db
    from knowledge.paths import get_paths

    paths = get_paths(root, load_config(root).vocabulary.ontology_file)
    paths.db.unlink(missing_ok=True)
    paths.dump.unlink(missing_ok=True)
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

    # Refuse equal prefixes before touching a single file (ruling C24). A vocabulary prefix
    # and an instance prefix that are the same string cannot tell terms from individuals —
    # `vocab.is_term` and `vocab.is_instance` discriminate by prefix, so both would match
    # everything — and no rewrite of the ontology's two `@prefix` lines could repair that.
    # There is no correct output for this input, so `run` stops rather than produce a
    # plausible-looking wrong one, and stops before writing so the template is left intact.
    if answers.prefix == answers.instance_prefix:
        raise RuntimeError(
            "prefix and instance_prefix must differ — one names vocabulary terms and the"
            " other individuals, and is_term/is_instance tell them apart by prefix"
        )
    # The rewrite mapping is keyed on the OLD prefix names, so two identical old prefixes
    # would collapse into a single entry and silently drop one declaration. That shipped
    # config is already incoherent; fail loudly rather than half-rewrite the ontology.
    if old_prefix == old_instance_prefix:
        raise RuntimeError(
            "knowledge.toml's vocabulary.prefix and vocabulary.instance_prefix must differ"
            " — the prefix rewrite is keyed on the old prefix, and two equal old prefixes"
            " cannot both be mapped"
        )

    values = _values(answers, ontology_file)
    namespace = values["BASE_IRI"] + "ontology#"
    instances = values["BASE_IRI"] + "id/"

    rewritten = substitute(
        root, values, MANIFEST + (f"ontology/{ontology_file}", "specs/example/spec.ttl")
    )

    ontology_path = root / "ontology" / ontology_file
    if ontology_path.is_file():
        text = ontology_path.read_text(encoding="utf-8")
        new_text = _rewrite_ontology_prefixes(
            text,
            {
                old_prefix: (answers.prefix, namespace),
                old_instance_prefix: (answers.instance_prefix, instances),
            },
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
