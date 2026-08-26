#!/usr/bin/env python
"""One-shot migration: docs/wiki/*.md -> specs/<id>/{spec.md,spec.ttl} + ontology/.

Mechanical and lossless by construction. The correctness gate is in
tests/test_extraction.py: the graph assembled after extraction must be isomorphic to the
graph the wiki produced before it. This is a script rather than an agent precisely so that
the baseline is provable.

    uv run python scripts/extract_wiki.py ../monicords_app/docs/wiki
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from rdflib import Graph

from knowledge.paths import Paths, get_paths, spec_dir, spec_md, spec_ttl

TURTLE_BLOCK = re.compile(r"^```turtle\n(.*?)^```\n?", re.M | re.S)

# Neither becomes a spec: the sidebar is navigation and is generated from now on, and the
# ontology is the vocabulary the specs are written against rather than knowledge itself.
NOT_SPECS = {"_Sidebar.md", "Ontology.md"}

ONTOLOGY_VERSION = "1.0.0"


def split_page(text: str) -> tuple[str, list[str]]:
    blocks = TURTLE_BLOCK.findall(text)
    prose = re.sub(r"\n{3,}", "\n\n", TURTLE_BLOCK.sub("", text)).strip() + "\n"
    return prose, blocks


def legacy_graph(wiki_dir: Path) -> Graph:
    """Reproduce the old assembly exactly: Ontology.md first, then every other page."""
    ontology = wiki_dir / "Ontology.md"
    pages = ([ontology] if ontology.exists() else []) + sorted(
        p for p in wiki_dir.glob("*.md") if p.name != "Ontology.md"
    )
    chunks = [
        f"# --- {page.name} ---\n{block}"
        for page in pages
        for block in TURTLE_BLOCK.findall(page.read_text(encoding="utf-8"))
    ]
    g = Graph()
    g.parse(data="\n".join(chunks), format="turtle")
    return g


def write_ontology(wiki_dir: Path, paths: Paths) -> None:
    prose, blocks = split_page((wiki_dir / "Ontology.md").read_text(encoding="utf-8"))
    paths.ontology.mkdir(parents=True, exist_ok=True)
    paths.ontology_ttl.write_text(
        "\n\n".join(b.strip() for b in blocks) + "\n", encoding="utf-8", newline="\n"
    )
    paths.ontology_readme.write_text(prose, encoding="utf-8", newline="\n")
    paths.ontology_version.write_text(ONTOLOGY_VERSION + "\n", encoding="utf-8", newline="\n")


def extract(wiki_dir: Path, paths: Paths) -> list[str]:
    write_ontology(wiki_dir, paths)
    written: list[str] = []
    for page in sorted(wiki_dir.glob("*.md")):
        if page.name in NOT_SPECS:
            continue
        spec_id = page.stem.lower()
        prose, blocks = split_page(page.read_text(encoding="utf-8"))
        spec_dir(paths, spec_id).mkdir(parents=True, exist_ok=True)
        spec_md(paths, spec_id).write_text(
            f"---\nid: {spec_id}\n---\n\n{prose}", encoding="utf-8", newline="\n"
        )
        spec_ttl(paths, spec_id).write_text(
            "\n\n".join(b.strip() for b in blocks) + "\n", encoding="utf-8", newline="\n"
        )
        written.append(spec_id)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wiki_dir", type=Path, help="path to the code repo's docs/wiki")
    args = parser.parse_args()

    paths = get_paths()
    written = extract(args.wiki_dir, paths)
    print(f"{len(written)} spec(s) written to {paths.specs}")
    for spec_id in written:
        print("  -", spec_id)
    print(f"ontology written to {paths.ontology}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
