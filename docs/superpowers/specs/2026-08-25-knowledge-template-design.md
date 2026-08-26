# knowledge-template — design

## What this is

A public GitHub template repository that carries the authoring, tracking and publishing
tooling this repository proved out, with every monicords-specific decision removed. Someone
clicks "Use this template", clones the result, runs `knowledge init`, and has a working
knowledge base bound to their own project, their own vocabulary and their own conventions.

The tooling ships. The conventions do not. Everything monicords chose — a GitHub wiki as
the publishing target, a nightly staleness workflow, prettier through pre-commit, a
UI-shaped ontology, Next.js route globs — becomes either configuration or a documented
recipe. None of it is imposed on a new user by existing as a file in their repository.

This repository is not modified by the work, beyond this document. The template is a
scrubbed copy; monicords-knowledge keeps running as it does today and the two diverge.

## Why the design lands where it does

Three decisions shape everything else.

**The ontology ships near-empty.** monicords' vocabulary is a good vocabulary for a web
application: `Module`, `View`, `Section`, `Field`, `route`, `viewport`, `endpoint`. It is a
bad vocabulary for an API, a data pipeline, a policy manual or a game. A template that
ships it forces a shape onto every user, and the classes they never use still appear in
`validate` output, in the agents' instructions, and in the naming rules. So the template
ships three classes and three properties as a starting point, plus a guide on designing a
vocabulary, plus the full monicords vocabulary as a worked example that nothing loads.

**Which forces the vocabulary-aware checks into configuration.** Five mechanical checks and
one preset list currently name monicords terms in Python: `restated_rule_comments` looks for
`mon:Rule`, `naming_violations` looks for `mon:Field` and enforces `<Owner>_<field>`,
`ungrounded_empty_states` looks for `mon:emptyState`, `locally_redeclared_concepts` looks
for `mon:Concept` and the `concepts` spec, `contradictions.functional_conflicts` carries a
hardcoded five-property list, and `graph.SANITY_QUERIES` carries six monicords surveys. A
near-empty ontology would make all six either crash or silently pass. They become
configuration instead, read from `knowledge.toml`.

**A disabled check must say so.** This repository already draws the distinction, in
`deps.uncheckable`: "checked and clean" and "cannot be checked" are different states, and
conflating them is the same sin as guessing a missing exchange rate. A check whose
configuration is empty therefore reports `skipped (not configured)` in `validate` output.
It never prints a pass it did not earn.

## Repository layout

```
knowledge-template/
  README.md                       the template's own documentation
  LICENSE                         MIT
  knowledge.toml                  every project-specific value, as {{PLACEHOLDER}}
  pyproject.toml  uv.lock  .gitignore
  .pre-commit-config.yaml         the tool's own guard rails
  .prettierrc.mjs  .prettierignore  .gitattributes
  docs/
    GUIDE.md                      the model, and how to adapt the template
    README.template.md            becomes the generated repository's README
    recipes/
      github-actions.md
      github-wiki-publishing.md
      nextjs-dependencies.md
  ontology/
    ontology.ttl                  the seed vocabulary
    AUTHORING.md                  how to design a vocabulary
    README.md                     the generated repository's ontology page
    VERSION
    examples/webapp.ttl           monicords' full vocabulary. Not loaded.
    examples/webapp.toml          the knowledge.toml fragment that matches it
  presets/
    nextjs.toml                   the [dependencies] block monicords uses
  specs/
    example/spec.md               one round-trip demo spec
    example/spec.ttl
  src/knowledge/**                the tooling
  tests/**
  .claude/agents/interviewer.md
  .claude/agents/writer.md
  integrations/code-repo/.claude/skills/knowledge-base/SKILL.md
  .metadata/dump.sql              the example spec's row, and nothing else
```

What is deliberately absent is `.github/workflows/`. A workflow encodes where the project
lives, which branch it verifies, which secrets it holds and how often it runs — decisions
that belong to the user's project rather than to this tool. The three workflows are
documented as recipes instead. A file in the repository is a decision already made for the
user; a recipe is a decision offered.

The hooks are the exception, and they ship. `.pre-commit-config.yaml` is not a house style
imported from elsewhere: two of its four hooks are the tool checking itself, and the other
two exist because of how the tool stores content. `knowledge scan && validate --strict` on
pre-push is the same check the writer agent is told to pass, run where it cannot be
skipped. `pytest` on pre-push guards the tooling a user is invited to edit. Prettier's
`proseWrap: preserve` exists because specs are hand-wrapped prose and rewrapping would turn
a one-line edit into a whole-paragraph diff. Its `endOfLine: 'lf'` exists because
`.gitattributes` normalises to LF, and `.gitattributes` exists because `.metadata/dump.sql`
is a byte-compared artifact that a Windows author and a Linux runner would otherwise write
differently on every run.

Those four files are therefore one unit: each of the last three exists to make the one
before it true. `.pre-commit-config.yaml`, `.prettierrc.mjs`, `.prettierignore` and
`.gitattributes` all ship, and `pre-commit` stays in the dev dependency group alongside
`pytest`.

Hooks are inert until installed, so `docs/GUIDE.md` carries the one-time
`pre-commit install --hook-type pre-commit --hook-type pre-push`, what each of the four
hooks does, and which to drop — `pytest`, for a user who never touches `src/`.

## Configuration

`knowledge.toml` grows from two keys to the full surface below. Values shown are the
template's shipped defaults; `{{...}}` marks what `init` substitutes.

```toml
# Written by `knowledge init`. Remove the [template] table to unlock a re-run.
[template]
unconfigured = true

[project]
name = "{{PROJECT_NAME}}"

[vocabulary]
ontology_file   = "ontology.ttl"
namespace       = "{{BASE_IRI}}ontology#"
instances       = "{{BASE_IRI}}id/"
prefix          = "{{PREFIX}}"
instance_prefix = "app"

# Terms the mechanical checks need to know about. An empty value disables its check,
# and `validate` reports it as skipped rather than passed.
rule_class                 = "Rule"
concept_class              = ""
concept_spec               = "concepts"
field_class                = ""
field_name_pattern         = ""
underscore_reserved        = false
functional_properties      = []
verbatim_string_properties = []

# The `ask` presets. Each becomes one named survey.
[[ask]]
name  = "everything with a label"
query = "SELECT ?s ?l WHERE { ?s rdfs:label ?l } ORDER BY ?l"

[repo]
code_repo = "{{CODE_REPO}}"     # empty disables `stale` and `dep`

[dependencies]
route_property      = ""
endpoint_property   = ""
route_glob          = ""
endpoint_glob       = ""
absorbed_prefixes   = []
dynamic_segment     = "{...}"
dynamic_replacement = "*"

[publish]
target  = "none"                # "none" | "directory" | "github-wiki"
remote  = ""
out_dir = ""
committer_name  = "github-actions[bot]"
committer_email = "41898282+github-actions[bot]@users.noreply.github.com"

[publish.sidebar]
title         = "{{PROJECT_NAME}}"
order         = []              # anything unlisted is appended alphabetically
reference     = []
nested_under  = {}
header_before = {}
labels        = {}
```

Two files carry monicords' real values for anyone who wants them: `presets/nextjs.toml`
holds the `[dependencies]` block, including the `platform` absorbed prefix and the
`app/**/…/page.tsx` glob; `ontology/examples/webapp.toml` holds the matching `[vocabulary]`
keys and the six `[[ask]]` surveys. Both are copy-paste. Nothing in `src/` reads them.

## Changes to the tooling

| Module                                          | Change                                                                                                                                                                                                                                                                                                                                                                                             |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `config.py`                                     | Grows from two fields to the schema above. Typed dataclasses, validated on load, with a clear error naming the missing or malformed key.                                                                                                                                                                                                                                                           |
| `paths.py`                                      | `ontology_ttl` resolves from `vocabulary.ontology_file` rather than the literal `monicords.ttl`.                                                                                                                                                                                                                                                                                                   |
| `graph.py`                                      | `MON` and `APP` stop being module constants and become values carried alongside the graph. `SPARQL_PREFIXES` is built from the configured prefixes. `SANITY_QUERIES` reads the `[[ask]]` tables. `broken_links` checks against publish-target page names when a target is configured, and against spec ids when it is not.                                                                         |
| `lint.py`                                       | `restated_rule_comments`, `naming_violations`, `ungrounded_empty_states` and `locally_redeclared_concepts` take their terms from config and return a "not configured" sentinel when their key is empty. `invented_predicates`, `invented_types` and `domain_range_violations` need no change beyond the namespace becoming a parameter — they already work against whatever the ontology declares. |
| `contradictions.py`                             | `FUNCTIONAL_PROPERTIES` reads `vocabulary.functional_properties`.                                                                                                                                                                                                                                                                                                                                  |
| `deps.py`                                       | `route_to_glob` and `endpoint_to_glob` build from the configured templates and absorbed prefixes. Both derivations are off by default, leaving manual globs as the only dependency source until a user opts in.                                                                                                                                                                                    |
| `publish.py`                                    | `SIDEBAR_ORDER`, `SIDEBAR_REFERENCE`, `SIDEBAR_LABELS`, `SIDEBAR_HEADER_BEFORE` and `NESTED_UNDER` move to `[publish.sidebar]`. `BOT_NAME` and `BOT_EMAIL` move to `[publish]`. The `github-wiki` push path becomes one target among three.                                                                                                                                                        |
| `cli.py`                                        | Gains `init`. `stale`, `dep` and `publish` fail with a readable message when their configuration is empty, rather than with a traceback. `validate` prints skipped checks distinctly from passed ones.                                                                                                                                                                                             |
| `db.py`, `lifecycle.py`, `scan.py`, `gitcmd.py` | Unchanged. Already generic.                                                                                                                                                                                                                                                                                                                                                                        |
| `tests/conftest.py`                             | The fixture vocabulary is rewritten off monicords terms.                                                                                                                                                                                                                                                                                                                                           |
| `scripts/`                                      | Dropped. `extract_wiki.py` and `seed_statuses.py` are one-off monicords migration scripts.                                                                                                                                                                                                                                                                                                         |

## `knowledge init`

Interactive by default, with a flag for every prompt so it can run unattended.

It asks for: the project name; the base IRI; the prefix, defaulting to a slug of the
project name; the code repository path, where blank disables staleness checking; the
publish target; and the dependency preset, where `nextjs` copies `presets/nextjs.toml` into
the `[dependencies]` table and `none` leaves it empty.

It then rewrites `knowledge.toml`, renames the ontology file if the project name implies a
better name and rewrites its `@prefix` lines, substitutes placeholders across a manifest of
files, removes `specs/example/`, resets `.metadata/dump.sql` to an empty dump, replaces
`README.md` with `docs/README.template.md`, and removes the `[template]` table.

The manifest is small, now that no workflows ship: `knowledge.toml`, the ontology file,
`ontology/README.md`, both agents, the code-repo skill, and `docs/README.template.md`.

Two guards. `init` refuses to run when `[template]` is absent, so a configured repository
cannot be re-initialised by accident. `knowledge init --check` exits non-zero if any
`{{...}}` placeholder survives anywhere in the tree — the template's own test suite asserts
placeholders are present, and a generated repository can assert none remain.

Installing the reading skill into the code repository is opt-in, via `--install-skill`.
Writing into a second repository is not something a scaffolding command should do by
default; without the flag, `init` prints the source path and the suggested destination.

## The ontology seed

`ontology/ontology.ttl` declares three classes and three properties, each with a comment
saying it is a starting point rather than a fixture:

- `Concept` — a thing the domain is about, independent of any presentation.
- `Rule` — a constraint or invariant the domain enforces.
- `Actor` — who performs something.
- `relatesTo`, `constrains`, `performedBy`.

`ontology/AUTHORING.md` is the guide. It covers designing a vocabulary from the domain
rather than from the tooling; the naming-convention table pattern and how to encode one in
`field_name_pattern` and `underscore_reserved`; why `partOf` is not transitive and what
that costs at query time; why inverse pairs are convention rather than inference; why a
predicate whose values span two types is better left with no `rdfs:range` than with two;
when a property is functional and how to declare it so `contradictions` catches conflicts;
and how each new term is wired into `[vocabulary]` so the linters see it.

`ontology/examples/webapp.ttl` is monicords' vocabulary, verbatim, as the guide's worked
example. Nothing loads it. Its presence costs nothing, and it is the only way the guide can
show a vocabulary that has actually survived twenty-one specs.

## Agents and the reading skill

The interviewer and the writer keep their method intact — the one-question-per-turn
interview loop, the four contradiction shapes and which of them are mechanical, both
directions of the writer's audit, the `model`-before-`scan` finishing sequence, and every
boundary (never write the database directly, never `verify`, the writer may demote nothing,
neither edits the code repository).

What changes is only what is monicords. `ontology/monicords.ttl` becomes the configured
ontology file. `app:Workspace` and the `viewport` example become vocabulary-neutral
phrasing, with the concrete versions living in the webapp example's prose. References to
`ontology/README.md`'s naming table point at `ontology/AUTHORING.md`.

The reading skill — currently in the code repository, not here — ships at
`integrations/code-repo/.claude/skills/knowledge-base/SKILL.md`, templated the same way. It
keeps the parts that are about the tool rather than about monicords: which subcommand
answers which question, that `show` takes a spec id while `describe` takes a node name,
that `query`, `ask`, `graph` and `contradictions` exclude drafts silently while `describe`
does not, and that prefixes are prepended. The monicords-specific traps — which specs are
currently drafts, which predicates point where — become a section the user fills in.

## Recipes

Each recipe is prose explaining what the thing buys and when it is worth it, followed by a
fenced block to copy.

- `github-actions.md` — the three workflows: parse-and-validate on pull request, publish on
  push to the default branch, and nightly staleness demotion. Each carries the commentary
  the current workflows carry, including why staleness runs in the knowledge repository
  rather than the code repository, and why cross-repository access needs a PAT rather than
  `GITHUB_TOKEN`.
- `github-wiki-publishing.md` — how the wiki target works, the page-naming rule, the
  sidebar configuration, and the fact that GitHub only creates the wiki remote once a page
  exists.
- `nextjs-dependencies.md` — what `[dependencies]` does, why a route needs a glob rather
  than a path, and how route groups and dynamic segments are absorbed.

## Phases

1. **Configuration and genericisation.** The `config.py` schema, then each module in the
   table above, with the existing test suite kept green and extended per module.
2. **`knowledge init`.** The command, the placeholder manifest, `--check`, both guards, and
   tests covering re-run refusal and placeholder residue.
3. **Ontology.** The seed, `AUTHORING.md`, and the webapp example with its config fragment.
4. **Documentation and agents.** Both agents, the code-repo skill, `README.md`,
   `docs/GUIDE.md` including the hooks section, the three recipes,
   `docs/README.template.md`, `LICENSE`.
5. **End-to-end verification and publication.** Run `init` into a scratch directory, author
   a spec through the round trip, `validate --strict`, `publish --dry-run` against a
   directory target; then push public and mark the repository as a template.

## Decisions taken, with their reasons

- **MIT, public.** A template that is not public cannot be used as one. Branch protection
  is unavailable on the current plan for private repositories; public sidesteps that.
- **The example spec is invented, not borrowed.** No monicords prose leaves this
  repository.
- **The design document stays here.** GitHub copies a template's files into every generated
  repository but not its history, so a `docs/superpowers/` tree in the template would ride
  along into every user's repository. This document lives in monicords-knowledge, where the
  precedent already exists.
