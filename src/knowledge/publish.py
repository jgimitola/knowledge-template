"""Render specs into wiki pages and push them.

Turtle is not inlined: the wiki carries prose, and the graph is available as an exported
artifact. Only _Sidebar.md is generated — Home carries the project description and whatever
vocabulary declarations its own spec.ttl holds, so it stays an ordinary spec and publishes
like any other page.
"""

from __future__ import annotations

import re
from pathlib import Path

from knowledge import gitcmd
from knowledge.config import Sidebar
from knowledge.graph import page_name
from knowledge.paths import Paths

FRONTMATTER = re.compile(r"\A---\n.*?\n---\n\s*", re.S)


def strip_frontmatter(text: str) -> str:
    return FRONTMATTER.sub("", text)


def _spec_directory(conn, paths: Paths, spec_id: str) -> Path:
    """Resolve a spec's folder from its `path` column, kept current by `scan`, rather than
    reconstructing `paths.specs / spec_id`. The id and the folder name are only required to
    match at creation time — a rename keeps the id but changes the folder — and this is one
    of two places (with `lifecycle.mark_modeled`) that took an id straight from the database,
    which is exactly when the two can differ."""
    rows = list(conn.execute("SELECT path FROM spec WHERE id = ?", (spec_id,)))
    if not rows:
        raise RuntimeError(f"no spec with id {spec_id!r}")
    return paths.root / rows[0][0]


def render_page(conn, paths: Paths, spec_id: str) -> str:
    directory = _spec_directory(conn, paths, spec_id)
    return strip_frontmatter((directory / "spec.md").read_text(encoding="utf-8"))


def _published(conn) -> list[tuple[str, str, str]]:
    return list(conn.execute(
        "SELECT id, title, COALESCE(wiki_page, id) FROM spec"
        " WHERE publishes_to_wiki = 1 ORDER BY id"
    ))


def render_sidebar(conn, sidebar: Sidebar) -> str:
    rows = {spec_id: (title, page) for spec_id, title, page in _published(conn)}
    reference = set(sidebar.reference)
    ordered = [s for s in sidebar.order if s in rows and s not in reference]
    ordered += sorted(s for s in rows if s not in sidebar.order and s not in reference)

    lines = [f"### {sidebar.title}", ""] if sidebar.title else []
    for spec_id in ordered:
        header = sidebar.header_before.get(spec_id)
        if header:
            lines += ["", f"**{header}**", ""]
        title, page = rows[spec_id]
        label = sidebar.labels.get(spec_id, title)
        indent = "  " if spec_id in sidebar.nested_under else ""
        lines.append(f"{indent}- [{label}]({page})")

    lines += ["", "**Reference**", "", "- [Ontology](Ontology)"]
    for spec_id in sidebar.reference:
        if spec_id not in rows:
            continue
        title, page = rows[spec_id]
        lines.append(f"- [{sidebar.labels.get(spec_id, title)}]({page})")
    lines.append("")
    return "\n".join(lines)


def write_pages(conn, paths: Paths, out_dir: Path, sidebar: Sidebar) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for spec_id, _title, page in _published(conn):
        directory = _spec_directory(conn, paths, spec_id)
        if not (directory / "spec.md").is_file():
            # A row without a folder — usually `rm -rf specs/<id>` without `knowledge
            # forget`. Skip it rather than crash: a publish that omits one page and says
            # so beats one that fails entirely and publishes nothing.
            print(
                f"warning: {spec_id} has a row but no spec.md — skipping it. "
                f"Run `knowledge forget {spec_id} --by <name>` once you're sure it's "
                "meant to be gone."
            )
            continue
        # scan() always populates wiki_page, so `page` here is always page_name(spec_id)
        # already and the `if` branch never fires today. It exists so a hand-set wiki_page
        # (page != spec_id) survives untransformed instead of being re-derived from the id.
        name = f"{page_name(page) if page == spec_id else page}.md"
        (out_dir / name).write_text(
            render_page(conn, paths, spec_id), encoding="utf-8", newline="\n"
        )
        written.append(name)

    (out_dir / "Ontology.md").write_text(
        paths.ontology_readme.read_text(encoding="utf-8"), encoding="utf-8", newline="\n"
    )
    written.append("Ontology.md")

    (out_dir / "_Sidebar.md").write_text(
        render_sidebar(conn, sidebar), encoding="utf-8", newline="\n"
    )
    written.append("_Sidebar.md")
    return written


def push(
    out_dir: Path, remote: str, message: str, committer_name: str, committer_email: str
) -> bool:
    """Returns True when something was pushed, False when the wiki was already current.

    Raises subprocess.CalledProcessError on any git failure; the caller is responsible for
    turning that into a clean CLI error rather than a traceback.
    """
    gitcmd.run(
        ["-C", str(out_dir), "config", "user.name", committer_name],
        check=True, capture_output=True, text=True,
    )
    gitcmd.run(
        ["-C", str(out_dir), "config", "user.email", committer_email],
        check=True, capture_output=True, text=True,
    )
    gitcmd.run(
        ["-C", str(out_dir), "add", "-A"], check=True, capture_output=True, text=True
    )
    staged = gitcmd.run(
        ["-C", str(out_dir), "diff", "--staged", "--quiet"], check=False
    )
    if staged.returncode == 0:
        return False
    gitcmd.run(
        ["-C", str(out_dir), "commit", "-m", message],
        check=True, capture_output=True, text=True,
    )
    gitcmd.run(
        ["-C", str(out_dir), "push"], check=True, capture_output=True, text=True
    )
    return True
