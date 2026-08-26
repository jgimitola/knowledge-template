# {{PROJECT_NAME}} knowledge

What {{PROJECT_NAME}} does, and why — recorded as prose plus an RDF graph, tracked from
draft to verified, and queryable with the `knowledge` CLI.

## Layout

```
knowledge.toml        the project's configuration
ontology/             the vocabulary every spec is written against
specs/<id>/spec.md    prose: what is true, and why
specs/<id>/spec.ttl   the same claims as triples
.metadata/            the tracked database dump
```

Each spec says the same thing twice: `spec.md` for a person to read, `spec.ttl` for the
graph to query. They are parsed together with the ontology into one graph.

## Reading the knowledge base

| You want                               | Command                            |
| -------------------------------------- | ---------------------------------- |
| The specs that exist, and their status | `knowledge list`                   |
| Everything one spec says               | `knowledge show <id>`              |
| Every triple touching one node         | `knowledge describe <prefix:Node>` |
| An answer across the whole graph       | `knowledge query "<SPARQL>"`       |
| A preset survey                        | `knowledge ask`                    |
| Contradictions in the graph            | `knowledge contradictions`         |

`query`, `ask`, `graph` and `contradictions` read verified specs only; `describe` reads
everything. Pass `--include-drafts` to widen the first group, and say that you did.

## Authoring

| Step                          | Command                                       |
| ----------------------------- | --------------------------------------------- |
| Scaffold a new spec           | `knowledge new <id> --title "<Title>"`        |
| Reconcile files ↔ database    | `knowledge scan`                              |
| Record the writer's audit     | `knowledge model <id> --by <name>`            |
| Open / answer a question      | `knowledge ask-question` / `knowledge answer` |
| Confirm a spec is true        | `knowledge verify <id> --by <name>`           |
| Find specs whose code changed | `knowledge stale`                             |
| Publish                       | `knowledge publish`                           |

## Setup

```bash
uv sync --all-extras --dev
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
```

See [docs/GUIDE.md](docs/GUIDE.md) for the full model and
[ontology/AUTHORING.md](ontology/AUTHORING.md) for the vocabulary.
