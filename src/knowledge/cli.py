"""The knowledge CLI.

Every subcommand opens the repository, does one thing and returns an exit code. Mutating
commands go through db.save so the tracked dump.sql is always current.
"""

from __future__ import annotations

import argparse
import sqlite3
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from knowledge import db, gitcmd, graph, scan
from knowledge.config import Config, load_config
from knowledge.paths import Paths, find_root, get_paths

VERSION = "0.1.0"


def open_repo(_args: argparse.Namespace) -> tuple[Paths, Config, sqlite3.Connection]:
    root = find_root()
    config = load_config(root)
    paths = get_paths(root, config.vocabulary.ontology_file)
    return paths, config, db.connect(paths)


def _rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[tuple]:
    return list(conn.execute(sql, params))


def _print_table(headers: list[str], rows: list[tuple]) -> None:
    if not rows:
        print("(nothing)")
        return
    widths = [
        max(len(str(headers[i])), max(len(str(row[i])) for row in rows))
        for i in range(len(headers))
    ]
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("  ".join("-" * w for w in widths))
    for row in rows:
        print("  ".join(str(value).ljust(widths[i]) for i, value in enumerate(row)))


def cmd_scan(args: argparse.Namespace) -> int:
    paths, _config, conn = open_repo(args)
    report = scan.scan(conn, paths)
    print(f"added {len(report.added)}, moved {len(report.moved)}, "
          f"unchanged {len(report.unchanged)}, missing {len(report.missing)}, "
          f"demoted {len(report.demoted)}")
    for spec_id in report.added:
        print("  + ", spec_id)
    for spec_id, old, new in report.moved:
        print("  ~ ", f"{spec_id}: {old} -> {new}")
    for spec_id in report.demoted:
        print("  v ", f"{spec_id}: content changed since it was last modeled")
    for spec_id in report.missing:
        print("  ! ", f"{spec_id} has a row but no files")
    return 1 if report.missing else 0


def cmd_list(args: argparse.Namespace) -> int:
    paths, _config, conn = open_repo(args)
    where: list[str] = []
    params: list[str] = []
    if args.status:
        where.append("status = ?")
        params.append(args.status)
    if args.confidence:
        where.append("confidence = ?")
        params.append(args.confidence)
    if args.unmodeled:
        version = paths.ontology_version.read_text(encoding="utf-8").strip()
        where.append(
            # The writer's worklist. Three triggers: never modeled (modeled_at IS NULL),
            # content edited since modeling (md_hash/ttl_hash moved past the frozen
            # modeled_* pair), or modeled against an outdated ontology version. A fourth
            # clause guards a shape none of those three catch: modeled_at set but
            # modeled_md_hash still NULL — a row written before modeled_md_hash existed, or
            # replayed from a pre-Task-1 dump. SQL NULL != anything evaluates to NULL, not
            # true, so without this the drift clause silently never fires for that row.
            "(modeled_at IS NULL OR modeled_md_hash IS NULL"
            " OR md_hash != modeled_md_hash OR ttl_hash != modeled_ttl_hash"
            " OR ontology_version != ?)"
        )
        params.append(version)
    if args.has_questions:
        where.append(
            "id IN (SELECT spec_id FROM open_question WHERE status = 'open')"
        )
    if args.stale:
        where.append("demoted_at IS NOT NULL")
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    rows = _rows(
        conn,
        "SELECT id, status, COALESCE(confidence,'-'), COALESCE(verified_by,'-'),"
        f" COALESCE(modeled_at,'-') FROM spec{clause} ORDER BY id",
        tuple(params),
    )
    _print_table(["id", "status", "confidence", "verified by", "modeled at"], rows)
    print(f"\n{len(rows)} spec(s)")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    _, _config, conn = open_repo(args)
    rows = _rows(conn, "SELECT * FROM spec WHERE id = ?", (args.id,))
    if not rows:
        print(f"no spec with id {args.id!r}")
        return 1
    columns = [d[0] for d in conn.execute("SELECT * FROM spec LIMIT 0").description]
    for name, value in zip(columns, rows[0], strict=True):
        print(f"{name:24} {value if value is not None else '-'}")

    questions = _rows(
        conn,
        "SELECT id, status, COALESCE(claim_iri,'-'), question FROM open_question"
        " WHERE spec_id = ? ORDER BY id",
        (args.id,),
    )
    print(f"\nquestions ({len(questions)}):")
    for qid, status, claim, question in questions:
        print(f"  #{qid} [{status}] {question}")
        if claim != "-":
            print(f"       about {claim}")

    events = _rows(
        conn,
        "SELECT at, event, COALESCE(actor,'-'), COALESCE(detail,'') FROM spec_event"
        " WHERE spec_id = ? ORDER BY id",
        (args.id,),
    )
    print(f"\nhistory ({len(events)}):")
    for at, event, actor, detail in events:
        print(f"  {at}  {event:18} {actor:10} {detail}")
    return 0


def cmd_questions(args: argparse.Namespace) -> int:
    _, _config, conn = open_repo(args)
    where: list[str] = []
    params: list[str] = []
    if args.spec:
        where.append("spec_id = ?")
        params.append(args.spec)
    if args.claim:
        where.append("claim_iri = ?")
        params.append(args.claim)
    if args.open:
        where.append("status = 'open'")
    clause = (" WHERE " + " AND ".join(where)) if where else ""
    rows = _rows(
        conn,
        f"SELECT id, spec_id, status, asked_by, question FROM open_question{clause}"
        " ORDER BY spec_id, id",
        tuple(params),
    )
    _print_table(["#", "spec", "status", "asked by", "question"], rows)
    print(f"\n{len(rows)} question(s)")
    return 0


def _selected_ids(conn: sqlite3.Connection, paths: Paths, include_drafts: bool) -> list[str]:
    if include_drafts:
        return graph.spec_ids(paths)
    verified = {row[0] for row in conn.execute("SELECT id FROM spec WHERE status='verified'")}
    return [spec_id for spec_id in graph.spec_ids(paths) if spec_id in verified]


def _check(name: str, items: Sequence[str] | None, ok_message: str, strict: bool) -> bool:
    """Report one validate check, and say whether it should fail the run.

    `name` is the plural noun phrase printed after the count, so the heading reads
    "N <name>:". A clean check prints `ok_message` instead. Only `strict` decides whether
    findings are fatal — the caller passes True for the checks that always are.

    `items is None` means the check has no configuration to run against — a project without
    a rule class has no rules for `restated_rule_comments` to be about. That is reported as
    skipped, never as a pass: printing `ok_message` would claim a check ran clean when it
    never ran at all.
    """
    if items is None:
        print(f"skipped (not configured): {name}")
        return False
    if not items:
        print(ok_message)
        return False
    print(f"\n{len(items)} {name}:")
    for item in items:
        print("  -", item)
    return strict


def cmd_validate(args: argparse.Namespace) -> int:
    paths, config, _ = open_repo(args)
    vocab = config.vocabulary
    from knowledge import lint
    ids = graph.spec_ids(paths)
    print(f"{len(ids)} spec(s)")
    try:
        g = graph.load_graph(paths, vocab, ids)
    except Exception as exc:  # noqa: BLE001 - the parser's message is the useful part
        print(f"\nPARSE FAILED: {exc}")
        return 1
    print(f"parsed OK: {len(g)} triples")

    strict = args.strict
    failures = [
        _check("term(s) referenced but never declared", graph.dangling_terms(g, vocab),
               "no dangling references", True),
        _check("link(s) point at pages that do not exist", graph.broken_links(paths, ids),
               "all internal links resolve", strict),
        _check("invented ontology term(s) never declared",
               lint.invented_predicates(g, vocab) + lint.invented_types(g, vocab),
               "no invented ontology terms", strict),
        _check("rule(s) whose comment restates the label or is missing",
               lint.restated_rule_comments(g, vocab),
               "every rule's comment says more than its label", strict),
        _check("naming violation(s)", lint.naming_violations(g, vocab),
               "no naming violations", strict),
        _check("concept(s) redeclared locally instead of referenced",
               lint.locally_redeclared_concepts(paths, vocab, ids),
               "no locally redeclared concepts", strict),
        _check("predicate(s) used outside their declared domain or range",
               lint.domain_range_violations(g, vocab),
               "every predicate stays inside its declared domain and range", strict),
        _check("ungrounded literal(s) no prose states",
               lint.ungrounded_literals(paths, vocab, ids),
               "every verbatim string appears in its spec's prose", strict),
    ]
    return 1 if any(failures) else 0


def cmd_graph(args: argparse.Namespace) -> int:
    paths, config, conn = open_repo(args)
    ids = _selected_ids(conn, paths, args.include_drafts)
    g = graph.load_graph(paths, config.vocabulary, ids)
    output = Path(args.output)
    output.write_text(g.serialize(format="turtle"), encoding="utf-8", newline="\n")
    print(f"{len(g)} triples from {len(ids)} spec(s) written to {output}")
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    paths, config, conn = open_repo(args)
    vocab = config.vocabulary
    g = graph.load_graph(paths, vocab, _selected_ids(conn, paths, args.include_drafts))
    rows = graph.run_query(g, vocab, args.sparql)
    print(f"{len(rows)} result(s)")
    for row in rows:
        print("   ", "  ".join(row))
    return 0


def cmd_describe(args: argparse.Namespace) -> int:
    paths, config, _ = open_repo(args)
    vocab = config.vocabulary
    g = graph.load_graph(paths, vocab)
    term = args.term if ":" in args.term else f"{vocab.instance_prefix}:{args.term}"
    print(f"--- {term} as subject ---")
    for row in graph.run_query(g, vocab, f"SELECT ?p ?o WHERE {{ {term} ?p ?o }}"):
        print("   ", "  ".join(row))
    print(f"\n--- {term} as object ---")
    for row in graph.run_query(g, vocab, f"SELECT ?s ?p WHERE {{ ?s ?p {term} }}"):
        print("   ", "  ".join(row))
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    paths, config, conn = open_repo(args)
    vocab = config.vocabulary
    presets = graph.surveys(config)
    if not presets:
        print("no `ask` presets configured — add [[ask]] tables to knowledge.toml")
        return 0
    g = graph.load_graph(paths, vocab, _selected_ids(conn, paths, args.include_drafts))
    for title, sparql in presets:
        rows = graph.run_query(g, vocab, sparql)
        print(f"\n{title} - {len(rows)} result(s)")
        for row in rows:
            print("   ", "  ".join(row))
    return 0


def cmd_contradictions(args: argparse.Namespace) -> int:
    paths, config, conn = open_repo(args)
    vocab = config.vocabulary
    from knowledge import contradictions, lint
    ids = _selected_ids(conn, paths, args.include_drafts)
    g = graph.load_graph(paths, vocab, ids)
    found = False
    skipped = 0

    conflicts = contradictions.functional_conflicts(g, vocab)
    if conflicts is None:
        skipped += 1
        print("skipped (not configured): functional-property conflicts")
    elif conflicts:
        found = True
        print(f"{len(conflicts)} functional-property conflict(s):")
        for subject, prop, values in conflicts:
            print(f"  - {subject} {vocab.prefix}:{prop} has {len(values)} values:"
                  f" {', '.join(values)}")

    dangling = graph.dangling_terms(g, vocab)
    if dangling:
        found = True
        print(f"\n{len(dangling)} term(s) referenced but never declared:")
        for term in dangling:
            print("  -", term)

    redeclared = lint.locally_redeclared_concepts(paths, vocab, ids)
    if redeclared is None:
        skipped += 1
        print("skipped (not configured): locally redeclared concepts")
    elif redeclared:
        found = True
        print(f"\n{len(redeclared)} concept(s) redeclared locally instead of referenced:")
        for msg in redeclared:
            print("  -", msg)

    if not found:
        if skipped:
            print(
                f"no contradictions found by the checks that ran"
                f" ({skipped} skipped — see above)"
            )
        else:
            print("no mechanical contradictions found")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    paths, _config, conn = open_repo(args)
    from knowledge import lifecycle
    md = lifecycle.new_spec(paths, args.id, args.title or args.id.replace("-", " ").title())
    scan.scan(conn, paths)
    print(f"created {md}")
    return 0


def cmd_model(args: argparse.Namespace) -> int:
    paths, _config, conn = open_repo(args)
    from knowledge import lifecycle
    version = paths.ontology_version.read_text(encoding="utf-8").strip()
    try:
        lifecycle.mark_modeled(conn, paths, args.id, args.by, version)
    except RuntimeError as exc:
        print(f"refused: {exc}")
        return 1
    db.save(conn, paths)
    print(f"{args.id} modeled by {args.by} against ontology {version}")
    return 0


def cmd_forget(args: argparse.Namespace) -> int:
    paths, _config, conn = open_repo(args)
    from knowledge import lifecycle
    try:
        lifecycle.forget(conn, paths, args.id, args.by)
    except RuntimeError as exc:
        print(f"refused: {exc}")
        return 1
    db.save(conn, paths)
    print(f"forgot {args.id}")
    return 0


def cmd_ask_question(args: argparse.Namespace) -> int:
    paths, _config, conn = open_repo(args)
    from knowledge import lifecycle
    if not list(conn.execute("SELECT 1 FROM spec WHERE id = ?", (args.spec,))):
        print(f"refused: no spec with id {args.spec!r}")
        return 1
    qid = lifecycle.open_question(conn, args.spec, args.question, args.by, args.claim)
    db.save(conn, paths)
    print(f"opened question #{qid} on {args.spec}")
    return 0


def cmd_answer(args: argparse.Namespace) -> int:
    paths, _config, conn = open_repo(args)
    from knowledge import lifecycle
    lifecycle.answer_question(conn, args.question_id, args.answer, args.by)
    db.save(conn, paths)
    print(f"answered #{args.question_id}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    paths, config, conn = open_repo(args)
    from knowledge import lifecycle
    try:
        prune = [(int(qid), reason) for qid, reason in (args.prune or [])]
    except ValueError:
        print("refused: --prune takes a numeric question id, e.g. --prune 7 \"reason\"")
        return 1
    try:
        lifecycle.verify(conn, paths, config, args.id, args.by, prune)
    except RuntimeError as exc:
        print(f"refused: {exc}")
        return 1
    except subprocess.CalledProcessError as exc:
        print(
            "error: git could not read the code repository's current commit — check "
            "the `code_repo` path in knowledge.toml. This is the day-one experience if "
            "the code repository is not checked out beside this one."
        )
        print(f"   {exc}")
        return 1
    db.save(conn, paths)
    print(f"{args.id} verified by {args.by}")
    return 0


def cmd_stale(args: argparse.Namespace) -> int:
    paths, config, conn = open_repo(args)
    from knowledge import deps
    override = Path(args.code_repo).resolve() if args.code_repo else None
    try:
        findings = deps.check(conn, paths, config, demote=args.demote, code_repo=override)
    except subprocess.CalledProcessError as exc:
        print(
            "error: git could not compare against the verified commit — either the "
            "verified_against_commit is not reachable in this checkout (a shallow clone "
            "missing history, or a ref other than the one the spec was verified against), "
            "or the commit no longer exists at all. In CI, check the code repository out "
            "with `fetch-depth: 0` and the right `ref:` so the full, correct history is "
            "available."
        )
        print(f"   {exc}")
        return 1

    if not findings:
        print("nothing has gone stale")
    else:
        for spec_id, hits in findings:
            print(f"{spec_id}: {len(hits)} dependency change(s)")
            for path in hits:
                print("   ", path)
        if args.demote:
            db.save(conn, paths)
            print(f"\n{len(findings)} spec(s) demoted to draft")
        else:
            print(f"\n{len(findings)} spec(s) would be demoted (pass --demote to apply)")

    gaps = deps.uncheckable(conn, paths, config.vocabulary)
    if gaps:
        print(f"\n{len(gaps)} verified spec(s) have no dependencies and cannot be checked:")
        print("   ", ", ".join(gaps))
        print('  Add one with: knowledge dep add <spec> "<glob>"')
    return 0


def _clear_markdown(out_dir: Path) -> list[str]:
    """Unlink every top-level *.md in out_dir, returning what was removed.

    --dry-run and the real push must not diverge on this: the real path drops whatever the
    wiki currently has before writing fresh pages, which is how a dropped or renamed spec
    actually disappears from the wiki. Both call this same helper so a preview stays a
    faithful preview of the one irreversible step.
    """
    removed = sorted(p.name for p in out_dir.glob("*.md"))
    for stale in out_dir.glob("*.md"):
        stale.unlink()
    return removed


def cmd_publish(args: argparse.Namespace) -> int:
    import shutil
    import tempfile

    paths, config, conn = open_repo(args)
    from knowledge import publish

    if args.dry_run:
        out = Path(args.output) if args.output else paths.root / "build" / "wiki"
        out.mkdir(parents=True, exist_ok=True)
        existing = set(_clear_markdown(out))
        written = publish.write_pages(conn, paths, out)
        print(f"{len(written)} page(s) written to {out}")
        for name in sorted(written):
            print("   ", name)
        stale = sorted(existing - set(written))
        if stale:
            print(f"{len(stale)} stale page(s) removed: {', '.join(stale)}")
        return 0

    workdir = Path(tempfile.mkdtemp(prefix="knowledge-wiki-"))
    try:
        clone = workdir / "wiki"
        try:
            gitcmd.run(
                ["clone", config.publish.remote, str(clone)],
                check=True, capture_output=True, text=True,
            )
        except subprocess.CalledProcessError as exc:
            print("error: could not clone the wiki repository")
            print(f"   {exc.stderr.strip()}")
            print(
                "   A GitHub wiki repository does not exist until at least one page has been "
                "created through the web UI — if this is a brand-new wiki, create a page "
                "there first, then retry."
            )
            return 1

        _clear_markdown(clone)
        written = publish.write_pages(conn, paths, clone)
        try:
            pushed = publish.push(
                clone, config.publish.remote, f"docs: sync {len(written)} page(s)"
            )
        except subprocess.CalledProcessError as exc:
            print("error: could not push to the wiki repository")
            print(f"   {exc.stderr.strip()}")
            return 1
        print(f"{len(written)} page(s) {'pushed' if pushed else 'already current'}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return 0


def cmd_dep(args: argparse.Namespace) -> int:
    paths, config, conn = open_repo(args)
    from knowledge import deps
    if args.action in ("add", "remove") and not args.glob:
        print(f'usage: knowledge dep {args.action} <spec> "<glob>"')
        return 1
    if args.action == "add":
        if not list(conn.execute("SELECT 1 FROM spec WHERE id = ?", (args.spec,))):
            print(f"refused: no spec with id {args.spec!r}")
            return 1
        conn.execute(
            "INSERT OR REPLACE INTO spec_dependency (spec_id, glob, note) VALUES (?,?,?)",
            (args.spec, args.glob, args.note),
        )
        db.record_event(conn, args.spec, "dependency_added", "cli", args.glob)
        db.save(conn, paths)
        print(f"{args.spec} now depends on {args.glob}")
        try:
            tracked = deps.tracked_files(config.code_repo)
        except subprocess.CalledProcessError as exc:
            print(f"  warning: could not check the code repository ({exc})")
        else:
            if not deps.matches({args.glob}, tracked):
                print("  warning: this glob matches no file in the code repository today")
    elif args.action == "remove":
        conn.execute(
            "DELETE FROM spec_dependency WHERE spec_id = ? AND glob = ?", (args.spec, args.glob)
        )
        db.record_event(conn, args.spec, "dependency_removed", "cli", args.glob)
        db.save(conn, paths)
        print(f"{args.spec} no longer depends on {args.glob}")
    else:
        derived = deps.derived_globs(paths, config.vocabulary, args.spec)
        manual = deps.manual_globs(conn, args.spec)
        print(f"derived from the graph ({len(derived)}):")
        for glob in sorted(derived):
            print("   ", glob)
        print(f"manual ({len(manual)}):")
        for glob in sorted(manual):
            print("   ", glob)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="knowledge",
        description="Author, track and publish a project's knowledge base.",
    )
    parser.add_argument("--version", action="version", version=VERSION)
    parser.set_defaults(handler=None)
    sub = parser.add_subparsers(dest="command")

    scan_p = sub.add_parser("scan", help="reconcile spec files against the database")
    scan_p.set_defaults(handler=cmd_scan)

    list_p = sub.add_parser("list", help="list specs")
    list_p.add_argument("--status", choices=["draft", "verified"])
    list_p.add_argument("--confidence", choices=["low", "medium", "high"])
    list_p.add_argument("--unmodeled", action="store_true",
                        help="never modeled, edited since, or modeled against an old "
                             "ontology version — the writer's worklist")
    list_p.add_argument("--has-questions", action="store_true")
    list_p.add_argument("--stale", action="store_true",
                        help="was verified and has since been demoted")
    list_p.set_defaults(handler=cmd_list)

    show_p = sub.add_parser("show", help="everything known about one spec")
    show_p.add_argument("id")
    show_p.set_defaults(handler=cmd_show)

    q_p = sub.add_parser("questions", help="list open questions")
    q_p.add_argument("--spec")
    q_p.add_argument("--claim")
    q_p.add_argument("--open", action="store_true")
    q_p.set_defaults(handler=cmd_questions)

    val_p = sub.add_parser("validate", help="parse the graph and check references and links")
    val_p.add_argument("--strict", action="store_true", help="broken links fail too")
    val_p.set_defaults(handler=cmd_validate)

    g_p = sub.add_parser("graph", help="write the graph to a .ttl file")
    g_p.add_argument("-o", "--output", default="graph.ttl")
    g_p.add_argument("--include-drafts", action="store_true")
    g_p.set_defaults(handler=cmd_graph)

    qy_p = sub.add_parser("query", help="run SPARQL (prefixes are added for you)")
    qy_p.add_argument("sparql")
    qy_p.add_argument("--include-drafts", action="store_true")
    qy_p.set_defaults(handler=cmd_query)

    d_p = sub.add_parser("describe", help="every triple touching one node")
    d_p.add_argument("term")
    d_p.set_defaults(handler=cmd_describe)

    ask_p = sub.add_parser("ask", help="run the configured [[ask]] survey queries")
    ask_p.add_argument("--include-drafts", action="store_true")
    ask_p.set_defaults(handler=cmd_ask)

    cx_p = sub.add_parser(
        "contradictions", help="mechanical contradiction checks for the interviewer"
    )
    cx_p.add_argument("--include-drafts", action="store_true")
    cx_p.set_defaults(handler=cmd_contradictions)

    new_p = sub.add_parser("new", help="scaffold a new spec folder")
    new_p.add_argument("id")
    new_p.add_argument("--title")
    new_p.set_defaults(handler=cmd_new)

    model_p = sub.add_parser("model", help="record that the writer audited this spec's graph")
    model_p.add_argument("id")
    model_p.add_argument("--by", required=True)
    model_p.set_defaults(handler=cmd_model)

    forget_p = sub.add_parser(
        "forget", help="remove a spec's row after its folder is gone from disk"
    )
    forget_p.add_argument("id")
    forget_p.add_argument("--by", required=True)
    forget_p.set_defaults(handler=cmd_forget)

    aq_p = sub.add_parser("ask-question", help="open a question against a spec")
    aq_p.add_argument("spec")
    aq_p.add_argument("question")
    aq_p.add_argument("--by", required=True)
    aq_p.add_argument("--claim", help="the app: IRI the question is about")
    aq_p.set_defaults(handler=cmd_ask_question)

    ans_p = sub.add_parser("answer", help="answer an open question")
    ans_p.add_argument("question_id", type=int)
    ans_p.add_argument("answer")
    ans_p.add_argument("--by", required=True)
    ans_p.set_defaults(handler=cmd_answer)

    ver_p = sub.add_parser("verify", help="confirm a spec is true (a human act)")
    ver_p.add_argument("id")
    ver_p.add_argument("--by", required=True)
    ver_p.add_argument("--prune", nargs=2, action="append", metavar=("QID", "REASON"),
                       help="drop an open question deliberately; repeatable")
    ver_p.set_defaults(handler=cmd_verify)

    stale_p = sub.add_parser("stale", help="find verified specs whose code has changed")
    stale_p.add_argument("--demote", action="store_true", help="return them to draft")
    stale_p.add_argument("--code-repo", help="override the path in knowledge.toml")
    stale_p.set_defaults(handler=cmd_stale)

    dep_p = sub.add_parser("dep", help="inspect or edit a spec's manual dependencies")
    dep_p.add_argument("action", choices=["list", "add", "remove"])
    dep_p.add_argument("spec")
    dep_p.add_argument("glob", nargs="?")
    dep_p.add_argument("--note")
    dep_p.set_defaults(handler=cmd_dep)

    pub_p = sub.add_parser("publish", help="render the specs and push them to the wiki")
    pub_p.add_argument("--dry-run", action="store_true", help="write locally, do not push")
    pub_p.add_argument("-o", "--output", help="where --dry-run writes (default build/wiki)")
    pub_p.set_defaults(handler=cmd_publish)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.handler is None:
        parser.print_help()
        return 1
    try:
        return args.handler(args)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
