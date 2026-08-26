"""knowledge.toml — the paths and remotes this repository needs to reach outside itself.

Editor settings grant permission to read the code repository; this supplies its location,
so the staleness check does not depend on how the editor was launched.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    code_repo: Path
    wiki_remote: str


def load_config(root: Path) -> Config:
    with (root / "knowledge.toml").open("rb") as handle:
        data = tomllib.load(handle)
    return Config(
        code_repo=(root / data["repo"]["code_repo"]).resolve(),
        wiki_remote=data["wiki"]["remote"],
    )
