# Recipe: GitHub wiki publishing

Set `publish.target = "github-wiki"` and `knowledge publish` renders every verified spec into
a page and pushes the set to your repository's wiki, with a generated sidebar. This is what
each piece does.

## Configuration

```toml
[publish]
target = "github-wiki"
remote = "https://github.com/<owner>/<repo>.wiki.git"

[publish.sidebar]
title         = "Your Project"
order         = ["overview", "concepts"]  # listed pages come first, in this order
reference     = ["ontology"]              # pushed to a "Reference" section at the bottom
nested_under  = { billing = "overview" }  # indent `billing` under `overview`
header_before = { concepts = "Domain" }   # a bold header printed before `concepts`
labels        = { overview = "Home" }     # override the sidebar label for a spec
```

Anything not named in `order` is appended alphabetically, so a new spec appears without any
sidebar edit. `nested_under`, `header_before` and `labels` are all optional — an empty
`[publish.sidebar]` renders every spec flat and alphabetical under the title.

## The page-naming rule

A spec id becomes a wiki page name by splitting on hyphens and capitalising each part:
`loans-out` becomes `Loans-Out`, `overview` becomes `Overview`. The links in the generated
sidebar use these names, and GitHub's wiki resolves a page by its file name, so the rule has
to be applied consistently — which is why the tool generates the links rather than trusting
you to hand-write them.

## Only the sidebar is generated

`knowledge publish` writes `_Sidebar.md` and one page per verified spec. Every _other_ page in
the wiki is a spec's rendered content — there are no hand-maintained wiki pages competing with
the generated ones. The ontology reference page is generated from `ontology/README.md`.

## GitHub creates the wiki remote lazily

A brand-new repository has **no wiki git remote until the wiki has at least one page**. Pushing
to `https://github.com/<owner>/<repo>.wiki.git` before then fails with a repository-not-found
error that looks like an auth problem but is not. Create one page by hand in the wiki UI first
(anything — the first `publish` overwrites it), and the remote exists from then on.

## Previewing before you push

`knowledge publish --dry-run` renders the pages and the sidebar to a local directory
(`build/wiki` by default, or `-o <dir>`) and pushes nothing, so you can read the output before
it goes live. `--dry-run` works regardless of `publish.target`, so you can preview even before
choosing a destination.
