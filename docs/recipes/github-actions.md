# Recipe: GitHub Actions

The template ships no `.github/workflows/`, on purpose — a workflow encodes your branch, your
secrets and your schedule, which are yours to decide. Below are three workflows to copy into
`.github/workflows/` when you want them, each with the reasoning that shapes it.

Replace `<owner>/<repo>` with your code repository, `<branch>` with your default branch, and
adjust paths to match your layout.

## Why staleness runs here, not in the code repository

Staleness — a verified spec whose documented code has changed — is _documentation work_. It
belongs in the knowledge repository, surfaced where that work is done. Put the check in the
code repository instead and it becomes a documentation failure blocking an unrelated code
change: a red X people learn to bypass, which trains everyone to ignore exactly the signal
you built. Running it on a schedule in the knowledge repository keeps it visible without
holding anyone's pull request hostage.

## Why cross-repository access needs a PAT

The default `GITHUB_TOKEN` is scoped to the repository the workflow runs in. The staleness
job has to read the _code_ repository's history to see what changed, which is a second
repository, so it needs a token with access to both — a fine-grained personal access token
(or a GitHub App token), stored as a secret. `GITHUB_TOKEN` cannot reach across the boundary.

## Validate on pull request

Parse the graph and run the strict checks on every pull request, so no invented term or
broken reference merges.

```yaml
name: validate
on:
  pull_request:
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --all-extras --dev
      - run: uv run knowledge scan
      - run: uv run knowledge validate --strict
      - run: uv run pytest -q
```

## Publish on push to the default branch

Render the verified specs and publish them whenever the default branch moves.

```yaml
name: publish
on:
  push:
    branches: [<branch>]
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --all-extras --dev
      # Configure [publish] in knowledge.toml first. For a github-wiki target the wiki must
      # already have at least one page (see the wiki-publishing recipe).
      - run: uv run knowledge publish
        env:
          # Only needed if the publish target pushes to a separate repository (e.g. a wiki).
          GITHUB_TOKEN: ${{ secrets.WIKI_PUSH_TOKEN }}
```

## Nightly staleness demotion

Once a night, demote any verified spec whose code has changed back to draft.

```yaml
name: stale
on:
  schedule:
    - cron: "0 6 * * *" # daily at 06:00 UTC
  workflow_dispatch: # so you can run it by hand too
jobs:
  stale:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --all-extras --dev
      # The code repository is a SECOND checkout — staleness compares against its history,
      # which the default GITHUB_TOKEN cannot reach. Use a fine-grained PAT with read access
      # to both repositories.
      - uses: actions/checkout@v4
        with:
          repository: <owner>/<repo>
          path: code
          token: ${{ secrets.CODE_READ_TOKEN }}
      - run: uv run knowledge stale --demote --code-repo ./code
      # Commit the demotions back, if any, so the tracked dump.sql stays current.
      - run: |
          if ! git diff --quiet; then
            git config user.name "github-actions[bot]"
            git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
            git commit -am "chore: demote stale specs"
            git push
          fi
```
