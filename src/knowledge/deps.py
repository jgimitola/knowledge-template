"""What code does a spec depend on, and has any of it changed since verification?

Two sources. Derived globs come from the spec's own triples — a route or an endpoint
resolves mechanically to a file pattern — and are recomputed on every run, so they cannot
themselves go stale. Manual globs in spec_dependency cover what the ontology does not
model: services, Prisma models, shared utilities.

The route/endpoint -> glob shape is framework-specific (a route group absorbed by **, a
dynamic segment's on-disk spelling) and lives entirely in `knowledge.toml`'s
`[dependencies]` table — see `presets/nextjs.toml` for a worked example. Nothing here
hardcodes one framework, and by default `[dependencies]` is empty: a project that has not
configured it gets manual globs only, not a guess.

This never blocks a build. A code change failing on documentation is a check people learn
to bypass; staleness is data, surfaced as work.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from knowledge import gitcmd, lifecycle
from knowledge.config import Config, Dependencies
from knowledge.graph import load_spec_graph, run_query
from knowledge.paths import Paths


def _dynamic_delimiters(settings: Dependencies) -> tuple[str, str]:
    """`{...}` -> ("{", "}"), `<...>` -> ("<", ">"). The syntax a project writes dynamic
    route segments in is the project's, not this tool's."""
    opening, _, closing = settings.dynamic_segment.partition("...")
    return opening, closing


def route_to_glob(route: str, settings: Dependencies) -> str:
    """A route says nothing about directories a framework inserts and the URL omits, so an
    absorbed prefix is dropped and the glob's ** covers it. A dynamic segment becomes the
    configured replacement, matching whatever the real directory is called."""
    opening, closing = _dynamic_delimiters(settings)
    segments = [part for part in route.strip("/").split("/") if part]
    if segments and segments[0] in settings.absorbed_prefixes:
        segments = segments[1:]
    segments = [
        settings.dynamic_replacement
        if part.startswith(opening) and part.endswith(closing)
        else part
        for part in segments
    ]
    return settings.route_glob.replace("{segments}", "/".join(segments))


def endpoint_to_glob(endpoint: str, settings: Dependencies) -> str:
    path = endpoint.split()[-1]  # tolerate "GET /api/cron" as well as "/api/cron"
    return settings.endpoint_glob.replace("{path}", path.strip("/"))


def derived_globs(paths: Paths, config: Config, spec_id: str) -> set[str]:
    """Empty when `config.dependencies.derives` is False — the shipped default, since a
    project that has not configured `[dependencies]` has told this tool nothing about how
    its routes map to files, and guessing would risk a glob that matches the wrong thing
    (or nothing) silently."""
    settings = config.dependencies
    if not settings.derives:
        return set()
    vocab = config.vocabulary
    g = load_spec_graph(paths, vocab, spec_id)
    globs: set[str] = set()
    if settings.route_property and settings.route_glob:
        rows = run_query(
            g, vocab, f"SELECT ?r WHERE {{ ?s {vocab.prefix}:{settings.route_property} ?r }}"
        )
        globs |= {route_to_glob(row[0], settings) for row in rows}
    if settings.endpoint_property and settings.endpoint_glob:
        rows = run_query(
            g, vocab, f"SELECT ?e WHERE {{ ?s {vocab.prefix}:{settings.endpoint_property} ?e }}"
        )
        globs |= {endpoint_to_glob(row[0], settings) for row in rows}
    return globs


def manual_globs(conn, spec_id: str) -> set[str]:
    return {
        row[0]
        for row in conn.execute("SELECT glob FROM spec_dependency WHERE spec_id = ?", (spec_id,))
    }


def spec_globs(conn, paths: Paths, config: Config, spec_id: str) -> set[str]:
    return derived_globs(paths, config, spec_id) | manual_globs(conn, spec_id)


def changed_files(code_repo: Path, since: str) -> list[str]:
    """Both sides of a rename count. git reports only the destination path by default, so
    a renamed dependency directory would match no glob and the spec would never be flagged
    — a silent failure, and the one kind staleness cannot report on itself."""
    result = gitcmd.run(
        ["-C", str(code_repo), "diff", "--name-status", "-M", f"{since}..HEAD"],
        capture_output=True, text=True, check=True,
    )
    paths: list[str] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        # A rename or copy line is "R100\told\tnew"; everything else is "M\tpath".
        paths.extend(parts[1:] if parts[0][:1] in {"R", "C"} else parts[1:2])
    return paths


def tracked_files(code_repo: Path) -> list[str]:
    """Every path git tracks today, so a manual glob can be checked against reality at the
    moment it is added rather than trusted blind."""
    result = gitcmd.run(
        ["-C", str(code_repo), "ls-files"],
        capture_output=True, text=True, check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def matches(globs: set[str], changed: list[str]) -> list[str]:
    return sorted(
        path for path in changed
        if any(PurePosixPath(path).full_match(pattern) for pattern in globs)
    )


def check(conn, paths: Paths, config: Config, demote: bool,
          code_repo: Path | None = None) -> list[tuple[str, list[str]]]:
    """code_repo overrides the configured path. CI checks the code repository out inside
    its own workspace, which is not where knowledge.toml points.

    Raises RuntimeError when neither is set. Silently reporting no findings would be
    indistinguishable from a spec that was actually compared against code and found
    unchanged — the same false confidence as guessing a missing value instead of saying
    it is missing.
    """
    root = code_repo if code_repo is not None else config.code_repo
    if root is None:
        raise RuntimeError(
            "no code repository configured — set repo.code_repo in knowledge.toml,"
            " or pass --code-repo"
        )
    findings: list[tuple[str, list[str]]] = []
    rows = list(conn.execute(
        "SELECT id, verified_against_commit FROM spec"
        " WHERE status = 'verified' AND verified_against_commit IS NOT NULL ORDER BY id"
    ))
    for spec_id, since in rows:
        hits = matches(
            spec_globs(conn, paths, config, spec_id), changed_files(root, since)
        )
        if not hits:
            continue
        findings.append((spec_id, hits))
        if demote:
            lifecycle.demote(
                conn, spec_id, "changed since verification: " + ", ".join(hits), "stale-check"
            )
    return findings


def uncheckable(conn, paths: Paths, config: Config) -> list[str]:
    """Verified specs with zero dependencies — no derived route/endpoint and no manual
    glob. `check` reports these as clean, which is misleading: "checked and clean" and
    "cannot be checked" are different states, and conflating them is the same sin as
    guessing a missing exchange rate."""
    ids = [
        row[0] for row in conn.execute("SELECT id FROM spec WHERE status = 'verified' ORDER BY id")
    ]
    return [spec_id for spec_id in ids if not spec_globs(conn, paths, config, spec_id)]
