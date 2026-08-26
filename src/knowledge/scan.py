"""Reconcile what is on disk with what the database believes.

The link between a row and its files is the `id` in the spec's frontmatter, not its path.
That is the whole reason the id exists: a folder rename must not orphan a verification
trail, and matching by path would do exactly that. A verified spec whose audited hash no
longer matches what's on disk is reconciled too — back to `draft`, since the status was a
claim about content that has since moved.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from knowledge import db
from knowledge.graph import page_name
from knowledge.lifecycle import demote
from knowledge.paths import Paths

FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
HEADING = re.compile(r"^# (.+)$", re.M)

RESOURCE_KINDS = {
    ".csv": "data",
    ".json": "data",
    ".tsv": "data",
    ".md": "interview",
    ".pdf": "reference",
}


@dataclass
class ScanReport:
    added: list[str] = field(default_factory=list)
    moved: list[tuple[str, str, str]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    demoted: list[str] = field(default_factory=list)


def read_frontmatter(path: Path) -> dict[str, str]:
    match = FRONTMATTER.match(path.read_text(encoding="utf-8"))
    if not match:
        return {}
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


def read_title(path: Path, fallback: str) -> str:
    match = HEADING.search(path.read_text(encoding="utf-8"))
    return match.group(1).strip() if match else fallback


def file_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative(paths: Paths, path: Path) -> str:
    return path.relative_to(paths.root).as_posix()


def _sync_resources(conn, paths: Paths, spec_id: str, directory: Path) -> None:
    """Rows are keyed by a path relative to the spec folder, so a rename does not move
    them. Only rows whose file has genuinely gone are dropped — a hand-set kind or note
    is the reason this column exists and must survive a rescan."""
    resources = directory / "resources"
    found = sorted(p for p in resources.rglob("*") if p.is_file()) if resources.is_dir() else []
    current = {p.relative_to(directory).as_posix() for p in found}

    for (path,) in list(
        conn.execute("SELECT path FROM spec_resource WHERE spec_id = ?", (spec_id,))
    ):
        if path not in current:
            conn.execute(
                "DELETE FROM spec_resource WHERE spec_id = ? AND path = ?", (spec_id, path)
            )

    for resource in found:
        conn.execute(
            "INSERT INTO spec_resource (spec_id, path, kind, note) VALUES (?,?,?,NULL)"
            " ON CONFLICT (spec_id, path) DO NOTHING",
            (spec_id, resource.relative_to(directory).as_posix(),
             RESOURCE_KINDS.get(resource.suffix)),
        )


def scan(conn, paths: Paths) -> ScanReport:
    """Reconcile spec files on disk against the database.

    Ends by calling db.save, so callers must not save again.
    """
    report = ScanReport()
    if not paths.specs.is_dir():
        return report
    known = {
        row[0]: row[1:]
        for row in conn.execute(
            "SELECT id, path, title, md_hash, ttl_hash, status,"
            " modeled_md_hash, modeled_ttl_hash FROM spec"
        )
    }
    seen: set[str] = set()

    for directory in sorted(d for d in paths.specs.iterdir() if (d / "spec.md").is_file()):
        md = directory / "spec.md"
        spec_id = read_frontmatter(md).get("id")
        if not spec_id:
            raise RuntimeError(f"{md} has no `id` in its frontmatter")
        seen.add(spec_id)

        path = _relative(paths, directory)
        title = read_title(md, spec_id)
        md_hash = file_hash(md)
        ttl_hash = file_hash(directory / "spec.ttl")
        timestamp = db.now()

        if spec_id not in known:
            conn.execute(
                "INSERT INTO spec (id,title,path,status,md_hash,ttl_hash,publishes_to_wiki,"
                "wiki_page,created_at,updated_at) VALUES (?,?,?,'draft',?,?,1,?,?,?)",
                (spec_id, title, path, md_hash, ttl_hash, page_name(spec_id),
                 timestamp, timestamp),
            )
            db.record_event(conn, spec_id, "created", "scan", None)
            report.added.append(spec_id)
        else:
            (known_path, known_title, known_md_hash, known_ttl_hash,
             status, modeled_md_hash, modeled_ttl_hash) = known[spec_id]
            if known_path != path:
                report.moved.append((spec_id, known_path, path))
                db.record_event(conn, spec_id, "moved", "scan", f"{known_path} -> {path}")
            else:
                report.unchanged.append(spec_id)
            current = (path, title, md_hash, ttl_hash)
            if (known_path, known_title, known_md_hash, known_ttl_hash) != current:
                conn.execute(
                    "UPDATE spec SET title=?, path=?, md_hash=?, ttl_hash=?, updated_at=?"
                    " WHERE id=?",
                    (title, path, md_hash, ttl_hash, timestamp, spec_id),
                )
            # modeled_md_hash/modeled_ttl_hash are NULL until the first `knowledge model`
            # — a verified spec with no frozen hash predates this check (or was verified
            # through a test shortcut) and cannot be judged drifted or clean, so it is left
            # alone rather than guessed at either way.
            if (status == "verified" and modeled_md_hash is not None
                    and modeled_ttl_hash is not None
                    and (md_hash != modeled_md_hash or ttl_hash != modeled_ttl_hash)):
                demote(conn, spec_id, "content changed since the writer's audit", "scan")
                report.demoted.append(spec_id)
        _sync_resources(conn, paths, spec_id, directory)

    report.missing = sorted(set(known) - seen)
    db.save(conn, paths)
    return report
