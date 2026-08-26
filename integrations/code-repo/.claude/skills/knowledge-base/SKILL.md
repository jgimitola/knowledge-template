---
name: knowledge-base
description: Use when answering questions about what {{PROJECT_NAME}} does, why a rule exists, or what a module is for — and whenever running the `knowledge` CLI. Covers which subcommand answers which question, the draft-exclusion trap, and SPARQL against the project vocabulary.
---

# Reading {{PROJECT_NAME}}'s knowledge base

The knowledge base answers "what does this do and why" from prose plus an RDF graph. This
skill is how you query it without misreading it. The commands run from the knowledge
repository (see [Your knowledge base](#your-knowledge-base) below for where that is).

## Which command answers which question

| You want                                   | Command                                   |
| ------------------------------------------ | ----------------------------------------- |
| The specs that exist, and their status     | `knowledge list`                          |
| Everything one spec says                   | `knowledge show <spec-id>`                |
| Every triple touching one node             | `knowledge describe <{{INSTANCE_PREFIX}}:Node>` |
| An answer computed across the whole graph  | `knowledge query "<SPARQL>"`              |
| A preset survey (the questions asked often) | `knowledge ask`                          |
| Contradictions in the graph                | `knowledge contradictions`                |
| Open questions blocking verification       | `knowledge questions`                     |
| Which files a spec depends on              | `knowledge dep list <spec-id>`            |

## `show` takes a spec id; `describe` takes a node name

`show` and `describe` are not interchangeable, and the argument tells them apart.

- `knowledge show <spec-id>` — the id of a spec directory (`specs/<id>/`). It prints that one
  spec's prose and graph.
- `knowledge describe <{{INSTANCE_PREFIX}}:Node>` — the name of a node in the graph. It prints
  every triple touching that node, from whichever specs mention it.

Passing a spec id to `describe`, or a node name to `show`, returns nothing rather than an
error — a silent empty result you can mistake for "nothing there".

## The draft-exclusion trap

`query`, `ask`, `graph` and `contradictions` read **verified specs only**. A fact that lives
in a draft spec is invisible to them, and they say nothing about what they left out — a query
that returns three rows when the answer is five looks exactly like a query whose answer is
three.

`describe` is the exception: it always reads everything, drafts included. So when a query
comes back thinner than you expected, `describe` the node to see whether the missing facts
are sitting in a draft.

When you deliberately want drafts in the reading commands, pass `--include-drafts`, and say
that you did — an answer that quietly included unverified facts is worse than one that
excluded a verified one.

## Prefixes are prepended for you

`query` and `ask` add the project's prefix declarations to every query, so write
`{{PREFIX}}:` (vocabulary terms) and `{{INSTANCE_PREFIX}}:` (individuals) directly — do not
paste a `PREFIX` block, and do not write full IRIs. A query that declares its own prefixes on
top of the prepended ones is not wrong, just redundant.

## `dep list` shows manual dependencies, not derived ones

`knowledge dep list <spec-id>` shows the dependencies recorded for a spec. If the project
derives globs from the graph (routes, endpoints — see the project's `[dependencies]` config),
those derived globs are not what `dep list` prints; it prints the manually recorded ones.
Reading `dep list` as "everything this spec depends on" undercounts whenever derivation is on.

## Traps that depend on your vocabulary

- **Containment may not be transitive.** If your vocabulary declares a part-of style property
  and documents it as non-transitive, `?x partOf ?y` finds only _direct_ children. For the
  whole nested chain, use the SPARQL property path `partOf+`. Asking the direct query and
  reading it as the whole chain misses every indirectly nested node.
- **Inverse pairs are not inferred.** If your vocabulary declares an inverse pair (a "contains"
  reading of a "part of" relation, say), asserting one direction does _not_ create the other
  triple. Most specs assert only one direction, so a query that reads only the other finds
  nothing. Ask both directions with `p1|^p2`.

## Your knowledge base

- **Project:** {{PROJECT_NAME}}
- **Knowledge repository:** _fill in the path to the knowledge repository (where the
  `knowledge` CLI runs) relative to this code repository._
- **Current drafts:** _fill in which specs are currently drafts, so a reader knows what the
  verified-only commands are silently leaving out. Update this when a spec is verified._
- **Project-specific traps:** _fill in any predicate-points-where surprises, single-valued
  properties, or naming conventions particular to this project's vocabulary that a reader
  should know before trusting a query._
