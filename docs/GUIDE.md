# Guide

How the knowledge base works, and how to adapt this template to your project.

## The model

A spec is **prose plus a graph**: `specs/<id>/spec.md` is what a person reads, and
`specs/<id>/spec.ttl` is the same claims as triples. Every spec's `.ttl` is parsed together
with `ontology/ontology.ttl` into one RDF graph, so a question that spans specs is a single
query.

A spec has exactly **two statuses: `draft` and `verified`**. There is no third. Two acts
move a spec between them, and they are deliberately separate:

- **`model`** is the _writer's audit_ — a record that the graph was checked against the prose
  in both directions. It certifies the two halves agree.
- **`verify`** is a _person's confirmation_ — a record that the prose is true. It takes a
  name, because someone is standing behind it.

`verify` refuses shortcuts. It will not verify a spec whose graph nobody has modelled
(confirming prose while the graph says something else is how the graph quietly goes wrong),
and it will not verify while a question is open against the spec (an unresolved uncertainty
is not something anyone should certify around).

**Staleness is a demotion, not a third status.** When the code a verified spec documents
changes, `stale` moves the spec back to `draft`. It does not invent a "stale" state; it
withdraws the verification the change called into question, and the spec re-enters the normal
draft → verified path.

## The drafts default

The reading commands that compute over the graph — `query`, `ask`, `graph` and
`contradictions` — read **verified specs only**, and they say nothing about what they left
out. A query that returns three rows when a draft holds the other two looks identical to a
query whose answer is genuinely three. This is deliberate: a verified-only default means a
number you read out of the graph is a number someone stood behind.

`describe` is the exception — it always reads everything, drafts included — so it is how you
check whether a thin result is hiding facts in a draft.

When you want drafts included in the computing commands, pass `--include-drafts`. When you
do, **say that you did**: an answer that quietly folded in unverified facts is worse than one
that left a verified fact out, because the reader cannot tell.

## Adapting the template

Work in this order — each step depends on the one before it:

1. **Design the vocabulary.** Start from the nouns and verbs the people who know your domain
   actually use. `ontology/AUTHORING.md` is the full guide; `ontology/examples/webapp.ttl` is
   a real vocabulary that grew this way. Delete every seed term your domain has no use for.
2. **Wire the checks into `[vocabulary]`.** Each mechanical check is about one of your terms —
   the rule class, the field class, the naming pattern, the functional properties. An empty
   value disables its check, and `validate` reports it as `skipped (not configured)` rather
   than passing. `ontology/AUTHORING.md`'s closing checklist maps each term to the key that
   makes a check see it.
3. **Decide on `[dependencies]`.** If you want `stale` to derive file globs from routes or
   endpoints in the graph, configure the properties and glob templates (see
   [docs/recipes/nextjs-dependencies.md](recipes/nextjs-dependencies.md)). Leaving them empty
   keeps manual dependencies as the only source, which is the shipped default.
4. **Decide on `[publish]`.** `none`, a local `directory`, or a `github-wiki` (see
   [docs/recipes/github-wiki-publishing.md](recipes/github-wiki-publishing.md)).
5. **Write the first spec.** `knowledge new <id> --title "..."`, then interview and audit it
   through to `verified`.

## The hooks

The hooks ship with the template but are inert until you install them, once:

```bash
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
```

Each exists to make the tool check itself where a check cannot be skipped:

- **`prettier --write`** (pre-commit) formats Markdown and YAML with `proseWrap: preserve`,
  because specs are hand-wrapped prose and rewrapping would turn a one-line edit into a
  whole-paragraph diff.
- **`prettier --check`** (pre-push) is the same formatting, enforced where it cannot be
  skipped.
- **`pytest`** (pre-push) guards the tooling, which you are invited to edit. A user who never
  touches `src/` is the one who can safely drop this hook.
- **`knowledge scan`** then **`knowledge validate --strict`** (pre-push) are the same check
  the writer agent is told to pass, run where it cannot be bypassed — no spec reaches the
  remote with an invented term, a broken reference or an ungrounded literal. They are two
  separate hooks (scan runs first) so no `bash` is required, which keeps the pre-push gate
  working on Windows.

`.gitattributes` normalises every file to LF because `.metadata/dump.sql` is a byte-compared
artifact a Windows author and a Linux runner would otherwise write differently on every run;
`.prettierrc.mjs`'s `endOfLine: 'lf'` exists for the same reason.

## What is deliberately not here

There is no `.github/workflows/` directory. A workflow encodes where the project lives, which
branch it verifies, which secrets it holds and how often it runs — decisions that belong to
your project, not to this tool. A file in the repository is a decision already made for you; a
recipe is a decision offered. The three workflows are documented in
[docs/recipes/github-actions.md](recipes/github-actions.md) instead.

## Command reference

### Reading

| Command                            | What it does                                     |
| ---------------------------------- | ------------------------------------------------ |
| `knowledge list`                   | The specs that exist, and their status.          |
| `knowledge show <id>`              | Everything one spec says (prose and graph).      |
| `knowledge describe <prefix:Node>` | Every triple touching one node, drafts included. |
| `knowledge query "<SPARQL>"`       | An answer computed across the verified graph.    |
| `knowledge ask`                    | The configured `[[ask]]` surveys.                |
| `knowledge graph <file>`           | Write the graph to a `.ttl` file.                |
| `knowledge contradictions`         | Mechanical contradictions in the graph.          |
| `knowledge questions`              | Open questions blocking verification.            |
| `knowledge stale`                  | Verified specs whose code has changed.           |
| `knowledge dep list <id>`          | A spec's manually recorded dependencies.         |

### Authoring

| Command                                     | What it does                                        |
| ------------------------------------------- | --------------------------------------------------- |
| `knowledge new <id> --title "<Title>"`      | Scaffold `specs/<id>/`.                             |
| `knowledge scan`                            | Reconcile spec files against the database.          |
| `knowledge model <id> --claim <prefix:IRI>` | Record the writer's audit of the graph.             |
| `knowledge ask-question <id> "<Q>"`         | Open a question against a spec.                     |
| `knowledge answer <id> ...`                 | Answer an open question.                            |
| `knowledge verify <id> --by <name>`         | Confirm a spec is true (a human act).               |
| `knowledge forget ...`                      | Prune a question or claim, logged in the event log. |
| `knowledge publish`                         | Render the specs and publish them.                  |
| `knowledge init`                            | Bind this template to one project (run once).       |
