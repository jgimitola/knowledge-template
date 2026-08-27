# Recipe: Next.js dependencies

`[dependencies]` lets `knowledge stale` know which source files a spec depends on by
_deriving_ them from the graph, so you do not hand-maintain a file list that drifts. For a
Next.js App Router project, a spec's `route` and `endpoint` triples become file globs.

## Why a route needs a glob, not a path

A route is a URL: `/billing/invoices`. The file that serves it is not
`app/billing/invoices/page.tsx` — Next.js route _groups_ like `(dashboard)` sit in the file
path but never appear in the URL, so the on-disk path is something like
`app/billing/(dashboard)/invoices/page.tsx`. The URL cannot tell you where the group is, so a
route maps to a **glob** whose `**` covers the segments the framework inserts and the URL
omits, not to an exact path.

Two more mismatches the derivation handles:

- **Absorbed prefixes.** A leading segment that exists in the URL but corresponds to a
  directory the glob's `**` already spans is dropped, so it is not required to appear
  literally on disk.
- **Dynamic segments.** A route's `{id}`-style dynamic segment becomes `*`, matching the
  framework's `[id]` directory on disk.

## The substitution tokens

- `route_glob` contains `{segments}`, replaced by the route's path (minus absorbed prefixes,
  with dynamic segments turned into the replacement).
- `endpoint_glob` contains `{path}`, replaced by the endpoint's path.

A non-empty `route_glob` that lacks `{segments}`, or a non-empty `endpoint_glob` that lacks
`{path}`, is rejected at load — without the token, every route would collapse to one identical
literal glob, which `stale` would read as "nothing changed" forever.

## The preset

`presets/nextjs.toml` carries the block; `knowledge init --dependency-preset nextjs` splices
it in for you, or copy it by hand:

```toml
[dependencies]
route_property      = "route"
endpoint_property   = "endpoint"
route_glob          = "app/**/{segments}/page.tsx"
endpoint_glob       = "app/{path}/**/route.ts"
absorbed_prefixes   = ["platform"]
dynamic_segment     = "{...}"
dynamic_replacement = "*"
```

`dynamic_segment` is the syntax _you_ write dynamic segments in inside your `.ttl` (here
`{...}`, i.e. `{id}`); `dynamic_replacement` is what it becomes in the glob (`*`). A framework
that writes dynamic segments as `<id>` would set `dynamic_segment = "<...>"` instead — the
derivation is not Next.js-specific, only this preset is.

## Both sides of a rename count

Staleness compares against the code repository's git history with rename detection on
(`git log -M`), so a file _moved_ counts as a change to the spec that depended on it, not as a
deletion plus an unrelated addition. A route handler renamed from one path to another demotes
the spec that documented it, which is what you want — the documentation now points at a path
that no longer exists.
