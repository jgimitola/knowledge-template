"""`knowledge init` — bind the template to one project, once.

Placeholders split by who reads the file they live in (ruling C12):

- Prose the reader parses with their eyes — README, the agents, the skill, ontology/README.md
  — ships with `{{TOKEN}}` markers. `substitute` below sweeps those.
- Values a machine parses before `init` ever runs — knowledge.toml's `[vocabulary]`
  namespace/instances/prefix, and the ontology file's own `@prefix` line — ship as WORKING
  DEFAULTS instead. `load_config` treats an unsubstituted `{{TOKEN}}` as empty, and rdflib's
  Turtle parser rejects `@prefix {{PREFIX}}:` outright, so a token there would break the
  shipped template before `init` had a chance to run (`init.run` itself calls
  `load_config`). Those fields are rewritten in place — see `_rewrite_vocabulary_keys` and
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


def _rewrite_ontology_prefix(text: str, old_prefix: str, new_prefix: str, namespace: str) -> str:
    """Rewrite the ontology file's own vocabulary prefix — its `@prefix` declaration and
    every `old_prefix:Term` usage in the body.

    Two bounded passes, in this order:

    1. The declaration line itself, matched as a whole so the prefix name and its IRI are
       replaced together: `@prefix ex: <https://example.com/ontology#> .` becomes
       `@prefix acme: <https://acme.test/ontology#> .`. Matched first, while the line still
       reads `old_prefix:`, so pass 2 below cannot see it and mangle the IRI.
    2. Every remaining bare `old_prefix:` — e.g. `ex:Concept`, `rdfs:domain ex:Concept` —
       renamed to `new_prefix:`. `\\b` anchors the match so it cannot fire inside a longer
       word (`example:` never matches `\\bex:`, because "ex" there is not followed by a
       colon) or inside an IRI's host text (`https://example.com/...` has no `:` right after
       "ex" either). The file is small and hand-authored — three classes, three properties —
       so a bounded regex is a safe, auditable stand-in for a real Turtle-aware rewrite.

    The instance prefix (`app:` by default) is untouched: correction C12 scopes this rewrite
    to the vocabulary's own prefix, matching `_rewrite_vocabulary_keys` above, which likewise
    only rewrites `namespace`/`instances`/`prefix`, not `instance_prefix`.
    """
    declaration = re.compile(rf"@prefix\s+{re.escape(old_prefix)}:\s+<[^>]*>\s*\.")
    text = declaration.sub(f"@prefix {new_prefix}: <{namespace}> .", text, count=1)
    bare = re.compile(rf"\b{re.escape(old_prefix)}:")
    text = bare.sub(f"{new_prefix}:", text)
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
    values = _values(answers, ontology_file)
    namespace = values["BASE_IRI"] + "ontology#"
    instances = values["BASE_IRI"] + "id/"

    rewritten = substitute(
        root, values, MANIFEST + (f"ontology/{ontology_file}", "specs/example/spec.ttl")
    )

    ontology_path = root / "ontology" / ontology_file
    if ontology_path.is_file():
        text = ontology_path.read_text(encoding="utf-8")
        new_text = _rewrite_ontology_prefix(text, old_prefix, answers.prefix, namespace)
        if new_text != text:
            ontology_path.write_text(new_text, encoding="utf-8", newline="\n")
            if f"ontology/{ontology_file}" not in rewritten:
                rewritten.append(f"ontology/{ontology_file}")

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

    shutil.rmtree(root / "specs" / "example", ignore_errors=True)
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
