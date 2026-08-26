"""What code does a spec depend on, and has any of it changed since verification?

Two sources. Derived globs come from the spec's own triples — a mon:route or a
mon:endpoint resolves mechanically to a file pattern — and are recomputed on every run, so
they cannot themselves go stale. Manual globs in spec_dependency cover what the ontology
does not model: services, Prisma models, shared utilities.

This never blocks a build. A code change failing on documentation is a check people learn
to bypass; staleness is data, surfaced as work.
"""

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from knowledge import gitcmd, lifecycle
from knowledge.config import Config
from knowledge.graph import load_spec_graph, run_query
from knowledge.paths import Paths

DYNAMIC_SEGMENT = re.compile(r"^\{.+\}$")

# Routes whose files sit under a Next.js route group. /platform/assets lives at
# app/platform/(menuLayout)/assets/page.tsx: the group sits between `platform` and the
# module, so `platform` is dropped and the ** absorbs it along with the group.
ROUTE_PREFIXES_ABSORBED_BY_GLOB = ("platform",)


def route_to_glob(route: str) -> str:
    """A route says nothing about Next.js route groups — (menuLayout) is in the path but
    not the URL — so the glob absorbs them with **. A dynamic segment like
    {incomeSourceId} becomes *, matching the real directory name [incomeSourceId]."""
    segments = [part for part in route.strip("/").split("/") if part]
    if segments and segments[0] in ROUTE_PREFIXES_ABSORBED_BY_GLOB:
        segments = segments[1:]
    segments = ["*" if DYNAMIC_SEGMENT.match(part) else part for part in segments]
    return "app/**/" + "/".join(segments) + "/page.tsx"


def endpoint_to_glob(endpoint: str) -> str:
    path = endpoint.split()[-1]  # tolerate "GET /api/cron" as well as "/api/cron"
    return "app/" + path.strip("/") + "/**/route.ts"


def derived_globs(paths: Paths, spec_id: str) -> set[str]:
    g = load_spec_graph(paths, spec_id)
    globs = {route_to_glob(row[0]) for row in run_query(g, "SELECT ?r WHERE { ?s mon:route ?r }")}
    globs |= {
        endpoint_to_glob(row[0])
        for row in run_query(g, "SELECT ?e WHERE { ?s mon:endpoint ?e }")
    }
    return globs


def manual_globs(conn, spec_id: str) -> set[str]:
    return {
        row[0]
        for row in conn.execute("SELECT glob FROM spec_dependency WHERE spec_id = ?", (spec_id,))
    }


def spec_globs(conn, paths: Paths, spec_id: str) -> set[str]:
    return derived_globs(paths, spec_id) | manual_globs(conn, spec_id)


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
    its own workspace, which is not where knowledge.toml points."""
    root = code_repo if code_repo is not None else config.code_repo
    findings: list[tuple[str, list[str]]] = []
    rows = list(conn.execute(
        "SELECT id, verified_against_commit FROM spec"
        " WHERE status = 'verified' AND verified_against_commit IS NOT NULL ORDER BY id"
    ))
    for spec_id, since in rows:
        hits = matches(spec_globs(conn, paths, spec_id), changed_files(root, since))
        if not hits:
            continue
        findings.append((spec_id, hits))
        if demote:
            lifecycle.demote(
                conn, spec_id, "changed since verification: " + ", ".join(hits), "stale-check"
            )
    return findings


def uncheckable(conn, paths: Paths) -> list[str]:
    """Verified specs with zero dependencies — no mon:route/mon:endpoint and no manual
    glob. `check` reports these as clean, which is misleading: "checked and clean" and
    "cannot be checked" are different states, and conflating them is the same sin as
    guessing a missing exchange rate."""
    ids = [
        row[0] for row in conn.execute("SELECT id FROM spec WHERE status = 'verified' ORDER BY id")
    ]
    return [spec_id for spec_id in ids if not spec_globs(conn, paths, spec_id)]
