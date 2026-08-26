#!/usr/bin/env python
"""One-shot: seed statuses from what actually happened during authoring.

Eighteen pages were walked live with Playwright at 1280 and 420 while being written, in
both create and edit modes. Three never were: architecture and concepts are contributor
documentation, and home is the index. Those three start as drafts.

The verified ones are stamped against the code repository's current HEAD, while they were
in fact verified against the deployed application. If the deployment lags the branch, the
first staleness run will demote some of them — which is correct, and a useful smoke test.

    uv run python scripts/seed_statuses.py --by "Jesús Imitola"
"""

from __future__ import annotations

import argparse

from knowledge import db, lifecycle
from knowledge.config import load_config
from knowledge.paths import get_paths

WALKED_LIVE = [
    "assets",
    "expenses",
    "expenses-calendar",
    "expenses-log",
    "expenses-plan",
    "incomes",
    "incomes-detail",
    "loans-out",
    "onboarding",
    "onboarding-landing",
    "onboarding-welcome",
    "onboarding-workspace",
    "profile",
    "profile-account",
    "profile-categories",
    "profile-password",
    "profile-settings",
    "profile-workspaces",
]

NEVER_WALKED = ["architecture", "concepts", "home"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--by", required=True, help="who is attesting to these pages")
    args = parser.parse_args()

    paths = get_paths()
    conn = db.connect(paths)
    config = load_config(paths.root)
    version = paths.ontology_version.read_text(encoding="utf-8").strip()
    sha = lifecycle.head_commit(config.code_repo)

    for spec_id in WALKED_LIVE + NEVER_WALKED:
        lifecycle.mark_modeled(conn, paths, spec_id, by="extract_wiki", ontology_version=version)

    for spec_id in WALKED_LIVE:
        lifecycle.verify(conn, paths, config, spec_id, by=args.by, prune=[], commit=sha)

    db.save(conn, paths)
    print(f"{len(WALKED_LIVE)} verified against {sha}, {len(NEVER_WALKED)} left as drafts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
