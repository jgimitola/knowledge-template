"""Every path in the knowledge repository is derived from one marker file.

Commands may be run from anywhere inside the repository, so the root is found by
walking up for knowledge.toml rather than by assuming the working directory.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

MARKER = "knowledge.toml"


@dataclass(frozen=True)
class Paths:
    root: Path
    specs: Path
    ontology: Path
    ontology_ttl: Path
    ontology_readme: Path
    ontology_version: Path
    metadata: Path
    db: Path
    dump: Path


def find_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in [current, *current.parents]:
        if (candidate / MARKER).is_file():
            return candidate
    raise RuntimeError(f"no {MARKER} found in {current} or any parent directory")


def get_paths(start: Path | None = None) -> Paths:
    root = find_root(start)
    ontology = root / "ontology"
    metadata = root / ".metadata"
    return Paths(
        root=root,
        specs=root / "specs",
        ontology=ontology,
        ontology_ttl=ontology / "monicords.ttl",
        ontology_readme=ontology / "README.md",
        ontology_version=ontology / "VERSION",
        metadata=metadata,
        db=metadata / "knowledge.db",
        dump=metadata / "dump.sql",
    )


def spec_dir(paths: Paths, spec_id: str) -> Path:
    return paths.specs / spec_id


def spec_md(paths: Paths, spec_id: str) -> Path:
    return spec_dir(paths, spec_id) / "spec.md"


def spec_ttl(paths: Paths, spec_id: str) -> Path:
    return spec_dir(paths, spec_id) / "spec.ttl"


def spec_resources(paths: Paths, spec_id: str) -> Path:
    return spec_dir(paths, spec_id) / "resources"
