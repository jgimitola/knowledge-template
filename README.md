# knowledge-template

A template for a knowledge base that documents a project as **prose plus an RDF graph**,
tracks which of its claims a human has verified, and publishes the result. The tooling
ships; the conventions do not — every project-specific decision is configuration or a
documented recipe, never a file imposed on you.

## The two-file model

Each spec is a directory under `specs/` with two files that say the same thing twice:

- `spec.md` — prose a person reads. What the project does, and _why_ wherever a rule exists.
- `spec.ttl` — the same claims as triples, in your project's vocabulary, so they can be
  queried.

Every spec's `spec.ttl` is parsed together with `ontology/ontology.ttl` into one RDF graph.
A question like "which views are scoped to the billing concept" is a SPARQL query over that
graph; "why is the amount required" is a sentence in the prose. The writer agent audits that
the two halves agree before a human verifies the spec is true.

## Getting started

1. Click **Use this template** on GitHub, then clone the repository it creates.
2. Install the tooling:
   ```bash
   uv sync --all-extras --dev
   ```
3. Bind the template to your project:
   ```bash
   uv run knowledge init
   ```
   It asks for a project name, a base IRI, a Turtle prefix and a few optional choices, then
   rewrites the placeholders, drops the example spec, and leaves you a repository configured
   for your own vocabulary.
4. Install the hooks (once):
   ```bash
   uv run pre-commit install --hook-type pre-commit --hook-type pre-push
   ```

Then read [docs/GUIDE.md](docs/GUIDE.md) and design your vocabulary with
[ontology/AUTHORING.md](ontology/AUTHORING.md).

## What you get

- **The `knowledge` CLI** — scaffold, scan, validate, query, publish, and track the
  draft → verified lifecycle of every spec.
- **Two agents** — an [interviewer](.claude/agents/interviewer.md) that captures what a
  project does one question at a time, and a [writer](.claude/agents/writer.md) that audits
  the graph against the prose before a human verifies it.
- **A reading skill** — [integrations/code-repo/.claude/skills/knowledge-base/SKILL.md](integrations/code-repo/.claude/skills/knowledge-base/SKILL.md),
  to drop into the code repository so an agent there can query the knowledge base without
  misreading it.
- **A lifecycle with teeth** — verification is a human act that refuses an unaudited graph,
  and staleness demotes a verified spec when the code it documents changes.

## What you configure

Everything project-specific lives in `knowledge.toml`:

| Section          | What it decides                                                       |
| ---------------- | -------------------------------------------------------------------- |
| `[project]`      | The project's name.                                                  |
| `[vocabulary]`   | Namespaces, prefixes, and which terms each mechanical check is about. |
| `[[ask]]`        | Named SPARQL surveys for the questions you ask often.                |
| `[repo]`         | Where the code repository lives, for staleness tracking.             |
| `[dependencies]` | How a route or endpoint becomes a file glob (optional).              |
| `[publish]`      | Where and how pages publish, and how the sidebar is ordered.         |

A check whose configuration is empty is reported as `skipped (not configured)` — never as a
pass it did not earn.

## Learn more

- [docs/GUIDE.md](docs/GUIDE.md) — the model, and how to adapt the template.
- [ontology/AUTHORING.md](ontology/AUTHORING.md) — how to design a vocabulary.
- [docs/recipes/](docs/recipes/) — GitHub Actions, wiki publishing, and Next.js dependency
  derivation.

MIT licensed. See [LICENSE](LICENSE).
