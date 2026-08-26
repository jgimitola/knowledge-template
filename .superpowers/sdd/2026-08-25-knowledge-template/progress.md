# SDD ledger — plan: docs/superpowers/plans/2026-08-25-knowledge-template.md

Spec: docs/superpowers/specs/2026-08-25-knowledge-template-design.md (read, reachable)
Work happens in: C:/Users/jesus/Documents/Proyectos/knowledge-template (new git repo, probed writable)
monicords-knowledge is READ-ONLY for this plan except this workspace directory.

## Pre-flight conflict scan

### Per-task self-agreement

| Task | Self-agreement check | Found |
| --- | --- | --- |
| 1 | copy list vs pyproject vs test run | Clean. Copies only generic files; `uv run pytest` works because every test builds its fixture in tmp_path. |
| 2 | tests vs code vs TOML | Clean. `Config` field order (project_name, vocabulary, surveys, code_repo, dependencies, publish, unconfigured) matches every positional construction later. |
| 3 | fixture rewrite vs graph signatures | Clean, but see cross-task row C2 and C6. |
| 4 | check list vs `_check` vs cmd_validate | Clean. `invented_predicates` + `invented_types` never return None, so the `+` in cmd_validate is safe. |
| 5 | test vs `functional_conflicts` vs cmd_contradictions | Clean. |
| 6 | glob tests vs `route_to_glob` vs preset file | Wording defect — see C4. |
| 7 | sidebar tests vs `render_sidebar` vs `seeded_conn` | Clean; `seeded_conn` fixture is defined inside Task 7. |
| 8 | `main_argv` vs guards vs sweep | Clean. |
| 9 | fake-template fixture vs `init.run` vs MANIFEST | Clean. Fake tree has no placeholder in `specs/example/spec.ttl`, so Task 10's manifest extension does not break Task 9's tests. |
| 10 | subprocess tests vs seed vs example spec | Two notes — see C7 and C8. |
| 11 | agent edits vs MANIFEST assertion | Clean. All three paths are in Task 9's `MANIFEST`. |
| 12 | doc list vs "names no project" assertion | Clean. Recipes replace owner/branch names. |
| 13 | verification sequence vs publication | Defect — see C9. |

### Cross-task producer/consumer

| ID | Tasks | Produces / consumes | Found |
| --- | --- | --- | --- |
| C1 | 2 → 3 | `cli.open_repo` | Task 2 defines it, Task 3 redefines it (adds `find_root` + configured ontology filename). Contradiction in plan text. |
| C2 | 2 → 3 | `tests/conftest.py` fixture namespaces | Task 2 says keep the monicords namespaces; Global Constraints forbid monicords IRIs. |
| C3 | 3 → 7, 3 → scan.py | `graph.page_name` rename | Clean. Task 3 renames and updates both importers. |
| C4 | 2 → 6 | `deps.spec_globs` signature | Task 6's Interfaces block says `spec_globs(conn, paths, config, spec_id)`; Step 3's prose ("thread `config` in place of `paths, config` pairs") is ambiguous. |
| C5 | 6 → 8 | code-repo guard | Both add a "no code repository configured" guard (`deps.check` and `cmd_stale`). Duplicate, not conflicting. |
| C6 | 3, 4, 5, 6 | `write_spec` import in tests | Tasks 4, 5 do `from tests.conftest import write_spec`; there is no `tests/__init__.py`, so this import is fragile. |
| C7 | 10 | `test_the_shipped_template_validates_as_it_stands` runs `scan` | The test mutates `.metadata/dump.sql` as a side effect. |
| C8 | 9 → 10 | `init.run` substitution manifest | Task 10 Step 4 extends it to include `specs/example/spec.ttl`. Consistent with Task 9. |
| C9 | 13 | scratch directory | Step 2 uses `/tmp/kt-check`; this is Windows/Git Bash, and the session has a designated scratchpad. |
| C10 | 4 → 12 | rubric vs plan | Nothing the plan mandates is treated as a defect by the review rubric (no assert-nothing tests, no duplicated logic blocks). Clean. |

### Rulings

Ruling: C1 — Task 3's `open_repo` (using `find_root` plus the configured ontology filename) is the final form; Task 2's is a stepping stone, not a competing spec. Cost if wrong: one small rewrite of a four-line function.

Ruling: C2 — Task 2 keeps the monicords namespace strings in the test fixture, because `graph.MON` is still a hardcoded constant at that point and a mismatch would break the suite. The Global Constraint governs the SHIPPED template, which Task 8 Step 4's sweep and Tasks 11-12's tests verify; it does not govern intermediate commits. Cost if wrong: one extra commit renaming fixture strings.

Ruling: C4 — the signature is `spec_globs(conn, paths, config, spec_id)`; `manual_globs(conn, spec_id)` is unchanged. `derived_globs(paths, config, spec_id)` as the Interfaces block states. Cost if wrong: a signature mismatch caught immediately by the test run.

Ruling: C5 — keep both guards. `deps.check`'s protects library callers, `cmd_stale`'s produces the clean CLI message the test asserts. Cost if wrong: three redundant lines.

Ruling: C6 — `write_spec` becomes a pytest fixture in `tests/conftest.py` (`@pytest.fixture def write_spec(): return _write_spec`), and Tasks 4-7 request it as a fixture argument instead of importing from `tests.conftest`. Carried into Task 3's dispatch, which is where conftest is rewritten. Cost if wrong: an import error surfacing on the first test run of Task 4.

Ruling: C7 — acceptable. `scan` regenerates a byte-identical dump when nothing changed, which is exactly what the monicords CI check relies on. No change. Cost if wrong: a spuriously dirty working tree, visible in `git status`.

Ruling: C9 — Task 13 Step 2 uses the session scratchpad, not `/tmp`: `C:/Users/jesus/AppData/Local/Temp/claude/C--Users-jesus-Documents-Proyectos-monicords-app/5e6111b2-528b-448d-9b0d-9744cb935aae/scratchpad/kt-check`. Cost if wrong: the round-trip check runs in a different directory; no effect on the deliverable.

## Progress

Task 1: dispatched (implementer a1f2260, haiku) — BASE = empty tree 4b825dc642cb6eb9a060e54bf8d69288fbee4904 (new repository, no prior commit)
Briefs extracted: tasks 1-4

### Ruling added during execution (missed by the pre-flight scan)

| ID | Tasks | Produces / consumes | Found |
| --- | --- | --- | --- |
| C11 | 1 | `tests/*.py` copy list vs dropped `scripts/` | `tests/test_extraction.py` does `from scripts import extract_wiki`. Task 1 copies every `tests/*.py` while the plan drops `scripts/`, so the copy list is internally inconsistent. Verified: the import is real, and the file's three `requires_wiki` tests are the 3 skips in the suite. |

Ruling: C11 — drop BOTH. `scripts/extract_wiki.py` and `scripts/seed_statuses.py` are one-time monicords migration scripts (the spec's module table says "Dropped"), and `tests/test_extraction.py` tests nothing else. Removing both also makes the suite output pristine (no skips). The implementer resolved this the other way, copying `scripts/` in; that is a scope violation against the brief's explicit exclusion. Cost if wrong: a template user who wanted a wiki-extraction helper writes their own; the git history in monicords-knowledge still has it.

Task 1: implementer reported DONE but with a scope deviation — treating as DONE_WITH_CONCERNS and fixing before review, per the skill's handling of scope concerns.
Task 1: fix round 1/5 (1 addressed, 0 open — scripts/ and tests/test_extraction.py dropped per Ruling C11; commits 21b38af..2976990)
Task 1: controller error corrected — my fix message said "expect 145 passed"; correct figure is 147 passed / 0 skipped. Implementer stopped rather than bend code to my wrong number, which was the right call.
Task 1: review dispatched (reviewer a1bfa76, sonnet) — package task-1-review-package.md (byte-identity check, not raw diff: bootstrap vs empty tree is verbatim copies)
Task 1: minor (deferred): commit 21b38af transiently included pytest_output.txt and scripts/*, cleaned two commits later. HEAD clean; squash would tidy history.
Task 1: minor (deferred): stale untracked tests/__pycache__/*.pyc from before the removal; gitignored, harmless.
Task 1: complete (commits 4b825dc..2976990, review clean)
Task 2: dispatched — BASE = 2976990

| C12 | 2, 9, 10 | shipped `knowledge.toml` + shipped `.ttl` vs "template validates as it stands" | Load-bearing plan defect, found by the Task 2 implementer and reproduced by the controller. Two halves: (D1) `_clean` blanks `{{PLACEHOLDER}}`, so `vocabulary.prefix/namespace/instances` read empty and `load_config` raises `ConfigError: knowledge.toml: vocabulary.prefix is required` on the shipped template — which would also break `knowledge init` itself, since `init.run` calls `load_config`. (D2) `@prefix {{PREFIX}}:` is not legal Turtle — rdflib: `Bad syntax (expected qname after @prefix)` — so Task 10's `test_the_shipped_template_validates_as_it_stands` could never pass. |

Ruling: C12 — split placeholders by who reads them. **Machine-read values ship as working defaults**, not tokens: `[vocabulary] namespace = "https://example.com/ontology#"`, `instances = "https://example.com/id/"`, `prefix = "ex"`, and Task 10's `ontology/ontology.ttl` and `specs/example/spec.ttl` use `ex:` with those IRIs. **Prose-read placeholders stay**: `{{PROJECT_NAME}}`, `{{CODE_REPO}}`, and every token in README/agents/skill/ontology README — those load fine and keep `init --check` meaningful. The spec's goal ("a half-configured repository is impossible to mistake for a configured one") is carried by the `[template] unconfigured = true` marker and `init`'s refusal to re-run, which is where it actually belongs; it was never the IRI placeholder doing that work. Consequence for Task 9: `init.run` must *rewrite* the three `[vocabulary]` values and the ontology's `@prefix ex:` line (regex on the old prefix) in addition to substituting tokens. Consequence for Task 10: the shipped template now genuinely parses and validates, so its test is honest. Cost if wrong: a fresh clone ships example.com IRIs that a careless user could leave in place — mitigated because `init` rewrites them and `[template]` flags the unconfigured state.

Task 2: concerns 1 and 2 accepted, no action — fixing the 6 test files the schema change broke was required to keep the suite green, and removing `load_config` redundancy from 4 call sites rather than the 2 the brief named is the brief under-counting, not scope creep.
Task 2: fix round 1/5 (1 addressed, 0 open — vocabulary defaults per Ruling C12; commits e341c15..901c7b8). Load check: `ex https://example.com/ontology# True`. Suite 156/156, pristine.
Task 2: review dispatched (reviewer a4cba58, sonnet) — package task-2-review-package.md (1428 lines, full -U10 diff)
Task 2: reviewer ⚠️ resolved by controller — diffed shipped knowledge.toml against the design doc's Configuration section; the ONLY delta is the C12 vocabulary block. Checks keys and the [[ask]] survey are verbatim. No gap.
Task 2: minor (deferred): report says "23 call sites" in cli.py; actual is 19. Code correct, report figure wrong.
Task 2: minor (deferred): tests/test_paths.py's make_repo() still writes the old [repo]/[wiki] TOML shape. Inert (nothing there calls load_config) but stale as an example.
Task 2: complete (commits 2976990..901c7b8, review clean)
Task 3: dispatched — BASE = 901c7b8

| C13 | 3 vs 4, 5, 6 | `graph.MON`/`APP` deletion vs their importers | Ordering defect in the plan, escalated by the Task 3 implementer as NEEDS_CONTEXT (correctly — it refused to guess Task 6's rework). Task 3 deletes `MON`/`APP` and adds a required `vocab` parameter to four graph functions, but `lint.py` (`from knowledge.graph import APP, MON`), `contradictions.py` (`import MON`) and `deps.py` (`load_spec_graph`, `run_query`) all break the moment it lands — and each is owned by a later task. Task 3 cannot be green in isolation. |

Ruling: C13 — Task 3 does **minimal mechanical `vocab` threading** through those three files and their tests: pass `vocab` in, use `vocab.term()`/`is_term()`/`is_instance()`/`prefix` in place of the deleted constants, and leave every term NAME hardcoded exactly as it is today ("Rule", "Field", "Concept", "emptyState", the FUNCTIONAL_PROPERTIES tuple, "route"/"endpoint"). Behaviour is identical before and after; only the plumbing changes. Tasks 4, 5 and 6 then do what they were always for — making those hardcoded names configurable and adding the None sentinel — against signatures that already exist. The alternative, folding 4/5/6 into 3, would collapse three independent review surfaces into one and is worse. Signature note: Task 3 threads `vocab` (what graph functions need); Task 6 later widens `deps` to `config`, which is a one-line change it already owns. Cost if wrong: Tasks 4-6 each rewrite a signature Task 3 just wrote — small, and caught immediately by their own tests.
Task 3: implemented under Ruling C13 (scope extended to contradictions.py, lint.py, deps.py + tests). Commit 58d9446, 17 files, +471/-373. Suite 160/160 pristine (156 baseline + 4 new). Implementer reports no test assertion changed — only call signatures and namespace strings — which is the behaviour-unchanged evidence C13 asked for.
Task 3: review dispatched (reviewer aaacde7, sonnet) — package task-3-review-package.md (2019 lines)
Task 3: reviewer ⚠️ resolved by controller — KNOWLEDGE_TOML is a parameterised sibling of the brief-mandated CONFIG_TOML, carrying the same example vocabulary plus the keys Tasks 4-6 consume (rule_class, functional_properties, [dependencies]). Documented with a comment explaining the split. Not defensive bloat; no gap.
Task 3: minor (deferred): lint.domain_range_violations' describe() now falls back to a raw IRI for a type outside the vocabulary namespace, where it previously fabricated a "mon:"-prefixed name. Unreachable in any current corpus, untested, and arguably a fix to a latent bug.
Task 3: minor (deferred): cmd_ask's switch from built-in SANITY_QUERIES to configured [[ask]] presets has no CLI-level test, before or after. Brief-mandated change; worth covering later.
Task 3: minor (deferred): KNOWLEDGE_TOML's expansion was not listed in the report's own beyond-brief touch-ups.
Task 3: complete (commits 901c7b8..58d9446, review clean)
Task 4: dispatched — BASE = 58d9446

| C14 | 4 | plan's `naming_violations` vs its own test | The brief's literal implementation fails the brief's own `test_unconfigured_checks_return_none_rather_than_passing`: that test blanks `field_class` but leaves `field_name_pattern`/`underscore_reserved` at the fixture's values, so the guard `if pattern is None and not checks.underscore_reserved` never fires and the function returns a list where the test expects None. Found by the Task 4 implementer. |

Ruling: C14 — accept the implementer's one-line `if not checks.field_class: return None` guard. It is semantically right, not a workaround: with no field class configured, `fields` is empty, so the underscore half would flag every legitimate field as a violation — a false-positive machine. Both halves of the check are meaningless without the class they are about. Also accept filling in `tests/conftest.py::make_config`'s empty `Checks()`, whose docstring already claimed it matched KNOWLEDGE_TOML while passing bare defaults — a pre-existing latent bug that this task's first real consumer exposed. Cost if wrong: a project that wants the underscore rule without a field class cannot have it; no such project is known and the ontology guide never suggests that shape.
Task 4: implemented under Ruling C14. Commit 6a7ed46. Suite 164/164 pristine.
Task 4: review found 1 Important (undocumented None sentinel in naming_violations, ungrounded_literals, locally_redeclared_concepts) + 2 Minors. Fix round 1 dispatched.
Task 4: minor (deferred): test_ungrounded_literals_covers_every_configured_property never configures >1 property, so this task's multi-property loop is untested. Inherited verbatim from the plan — controller's defect, not the implementer's.
Task 4: minor (deferred): no test isolates one half of naming_violations while asserting on findings rather than on the None return.
Task 4: fix round 1 implementer (ab0fea6) TERMINATED by an account session limit before applying the fix. Verified nothing was lost: HEAD still 6a7ed46, working tree clean, only restated_rule_comments documents its sentinel.
Task 4: fix round 1 re-dispatched fresh (a22a298, haiku — single-file docstring-only change, cheapest tier per Model Selection). Carries brief + prior report + the finding.
Task 4: fix round 1/5 (1 addressed, 0 open — None sentinel documented in all three docstrings; commits 6a7ed46..cb02250). Re-review: all ADDRESSED on substance, no new breakage, docstrings-only scope confirmed.
Task 4: complete (commits 58d9446..cb02250, review clean)
Task 5: dispatched — BASE = cb02250

| C15 | 5 | `cmd_contradictions`' summary line vs the spec's core principle | Raised by the Task 5 implementer as a non-defect ("the pattern Task 4 already set"); controller reproduced and disagrees. With both configurable checks unconfigured the command prints two `skipped (not configured)` lines and then `no mechanical contradictions found` — a clean bill of health when only `dangling_terms` actually ran. This is precisely the conflation the spec forbids ("checked and clean" vs "cannot be checked"). It is NOT the Task 4 pattern: `cmd_validate` prints per-check lines and an exit code, with no blanket all-clear summary. |

Ruling: C15 — the summary line must account for what ran. When nothing was found AND at least one check was skipped, say so: `no contradictions found by the checks that ran (N skipped — see above)`. When nothing was found and nothing was skipped, the existing `no mechanical contradictions found` is correct and stays. Cost if wrong: one extra clause in one CLI message.
Task 5: minor (deferred, controller-raised): CLI print strings contain em-dashes (cli.py:278,330,409,428,506,587). Verified sys.stdout.encoding is cp1252 here, which HAS U+2014 at 0x97, so no UnicodeEncodeError. Pre-existing throughout the inherited CLI, not introduced by Task 5. Latent risk only on a cp437/cp850 console, which a publicly published template may well meet. Final review should decide whether the shipped CLI should be ASCII-only.
Task 5: fix round 1/5 (1 addressed, 0 open — C15 summary accounting; commits 19ab1bf..74b6741)
Task 5: minor (deferred): dead f-string prefix on the first half of the split skip-summary message (cli.py ~325).
Task 5: minor (deferred): no test pins the literal per-check skip-line text; only the aggregate "2 skipped" count. A garbled skip string with an intact count would slip through.
Task 5: minor (deferred): no test covers the partial-skip case (1 of 2 configurable checks unconfigured). Same code branch, coverage-completeness only.
Task 5: complete (commits cb02250..74b6741, review clean)
Task 6: dispatched — BASE = 74b6741

| C16 | 6 | `dynamic_segment` validation | Raised by the Task 6 implementer, reproduced by the controller. `_dynamic_delimiters` splits on `"..."`; a value lacking it silently yields no substitution. `dynamic_segment = "{}"` (a plausible typo) turns route `/incomes/{id}` into glob `app/**/incomes/{id}/page.tsx` — a literal `{id}` matching no file, so `stale` finds nothing changed for that spec forever and reports it clean. A silent false "checked and clean", the exact failure class this project keeps guarding against. |

Ruling: C16 — validate at load, not at use. `load_config` raises `ConfigError` naming `dependencies.dynamic_segment` when the value does not contain the literal `...`, matching the existing `publish.target` validation pattern. This rejects the typo class (`{}`, `X`) while accepting any legitimate delimiter syntax (`{...}`, `<...>`, `[...]`, `:...`). Validation belongs at load because that is where a template user's mistake should surface — at the first command they run, naming the key they mistyped, rather than as globs that quietly match nothing months later. Cost if wrong: a project wanting a literal-substring dynamic marker with no `...` convention must pick a different syntax; no such convention is known.
Task 6: implemented (be63ff6) + fix round 1/5 (1 addressed, 0 open — C16 dynamic_segment validation; c4cc611). Suite 174/174 pristine. presets/nextjs.toml created; grep confirms nothing in src/ reads it.
Task 6: review dispatched (reviewer a9ff0ae, sonnet) — package task-6-review-package.md

Ruling: C16 EXTENDED (found by the Task 6 reviewer, reproduced by the controller). The same footgun exists for the glob templates themselves, and my original C16 ruling was too narrow. `str.replace` is a silent no-op when the token is absent, so `route_glob = "app/page.tsx"` (a plausible typo dropping `{segments}`) collapses every distinct route to one identical literal glob — verified: /incomes, /expenses/{id} and /assets all yield `app/page.tsx`. Indistinguishable from "checked and clean" to a `stale` reader, exactly as with dynamic_segment. Extend the load-time validation: a non-empty `route_glob` must contain `{segments}` and a non-empty `endpoint_glob` must contain `{path}`, each raising ConfigError naming its key. Empty stays legal — that is how the derivation ships off by default. Cost if wrong: a project wanting a deliberately constant glob for every route must use a manual glob instead, which is the correct tool for that anyway.
Task 6: fix round 2/5 (1 addressed, 0 open — C16-extended glob-token validation; c4cc611..b3f8401). Re-review: ADDRESSED, empty-stays-legal boundary confirmed intact, no new breakage.
Task 6: minor (deferred): removed test_endpoint_to_glob dropped a multi-segment case (/api/loans-out/summary). No uncovered code path (endpoint_to_glob does not branch on segment count) but the intent is no longer visible in a test.
Task 6: complete (commits 74b6741..b3f8401, review clean)
Task 7: dispatched — BASE = b3f8401

| C17 | 7 | `cmd_publish` dispatch ordering vs `--dry-run` | Two concerns raised by the Task 7 implementer plus a third found by the controller. The brief's "at the top of cmd_publish" ordering produced: none-gate -> directory -> dry_run -> github-wiki. (a) `--dry-run` under target="none" now errors, so a fresh template user cannot preview before choosing a destination. (b) `--dry-run` under target="directory" never reaches the dry-run branch at all — silently ignored, doing a real write without the stale-page clearing. (c) the directory branch never calls `_clear_markdown`, unlike dry-run and github-wiki, so a renamed or deleted spec leaves a stale page a reader takes as current. |

Ruling: C17 — separate rendering from publishing. `--dry-run` means "render locally, push nothing" and must work regardless of `publish.target`, so its branch moves ABOVE the target gate. The `none` gate then guards only real publishing, which is what it was for. The `directory` target clears stale pages like the other two — a render that leaves a page for a spec that no longer exists is the same "claims a result it did not earn" failure this project keeps rejecting. Cost if wrong: a user who wanted `--dry-run` to be blocked until they configured a destination is not blocked; no such user is plausible, since the flag exists precisely to inspect output before committing to a destination.
Task 7: implemented (9118e93) + fix round 1/5 (3 addressed, 0 open — C17 dispatch restructure; 7169aed). Suite 189/189 pristine.
Task 7: MILESTONE — controller verified `grep -rni "monicords" src/ tests/ --include=*.py` returns nothing. The project-wide no-monicords-strings constraint is closed; Tasks 3-7 cleared it file by file.
Task 7: review dispatched (reviewer a4ff721, sonnet) — package task-7-review-package.md
Task 7: fix round 2/5 (1 addressed, 0 open — _render_to helper shared by both callers; 7169aed..7ab0b21). Re-review: ADDRESSED, stat confirms cli.py only, 189 unchanged.
Task 7: minor (deferred): --dry-run with --out-dir silently ignores --out-dir (dry-run path reads args.output only).
Task 7: minor (deferred): directory branch omits dry-run's per-page listing; _render_to's list_pages parameter makes this trivial to change if wanted.
Task 7: complete (commits b3f8401..7ab0b21, review clean)
Task 8: dispatched — BASE = 7ab0b21
Task 8: implemented (d2d4c16). Suite 193/193 pristine (189 + 4 new). Step 4 sweep confirmed no-op (Task 7 had closed it). graph.broken_links docstring already generic — implementer diffed against the reference and correctly made no change.
Task 8: review dispatched (reviewer a3fff0d, sonnet) — package task-8-review-package.md

Ruling: C5 REVISED (superseding the pre-flight ruling; prompted by two Important findings in the Task 8 review). My original C5 said keep both the library-layer and CLI-layer no-code-repo guards, justifying the CLI one as "produces the clean CLI message the test asserts". That justification is false and I could not have known it at pre-flight: `deps.check`'s message and `cmd_stale`'s guard message are the SAME STRING, so deleting the CLI guard changes nothing observable — `deps.check` raises, `main_argv` catches `RuntimeError`, and the user sees the same text. The guard's own comment claims it gives "its own clean, dedicated message"; that claim is untrue. This is why the brief's `test_stale_without_a_configured_code_repo_fails_clearly` cannot fail for the reason it is named after, exactly as the reviewer traced.

Revised: DROP `cmd_stale`'s guard as genuine redundancy. KEEP `cmd_dep add`'s guard — it is load-bearing for a different reason than C5 gave: it prevents a database row being inserted before the git validation fails, an observable side effect its test already asserts. This resolves both Important findings at once, since the verbatim duplication disappears with the redundant copy. `cmd_stale`'s test is rewritten to assert the real path (exit 1, message on stderr via deps.check + main_argv), which IS discriminating for that path. Cost if wrong: the `stale` error line gains an `error: ` prefix it did not have; arguably an improvement, and it matches every other error main_argv renders.
Task 8: fix round 1/5 (2 addressed, 0 open — C5-revised: cmd_stale guard deleted, test rewritten and proven discriminating; d2d4c16..e7f8443). Discrimination evidence real: with deps.check's guard disabled, stale exits 0 with "nothing has gone stale" — the false clean bill of health, now caught.
Task 8: minor (deferred): except (RuntimeError, ConfigError) is redundant since ConfigError subclasses RuntimeError. Implementer flagged it honestly; plan-mandated wording.
Task 8: complete (commits 7ab0b21..e7f8443, review clean)
Task 9: dispatched — BASE = e7f8443

Ruling: C18 — accept dropping `.py` from `init.TEXT_SUFFIXES`. Found by the Task 9 implementer, verified by the controller: `config.py:84`'s docstring legitimately contains the literal `{{PLACEHOLDER}}` while explaining that an unsubstituted token reads as empty. Sweeping `.py` would make `knowledge init --check` fail forever in EVERY generated repository, over the tooling's own prose. No `.py` file appears in `init.MANIFEST`, so no Python file should ever carry a real placeholder — the suffix earns no coverage and costs a permanent false failure. Cost if wrong: a placeholder accidentally introduced into a `.py` file goes unswept; the manifest makes that unreachable by construction.

Ruling: C19 — accept the implementer's correction to my `slugify` test. The brief asserted `slugify("Acme Widgets, Inc.") == "acmewidgets"`; the documented implementation (strip non-alphanumerics, lowercase) yields `"acmewidgetsinc"`, which I confirmed. My test was simply wrong — I dropped "Inc" when writing the expectation. The implementation is correct and the test now matches it. Cost if wrong: none; the rule is documented in the function's own docstring.

Note for Task 10: its draft uses `{{PREFIX}}` tokens inside `ontology/ontology.ttl` and `specs/example/spec.ttl`, which is invalid Turtle. C12 already covers this; the Task 9 implementer independently confirmed it. Task 10's dispatch must carry the correction — the seed ships `ex:` with the example.com IRIs, and `init` rewrites it.

Ruling: C20 — the ontology prefix rewrite must fire only in Turtle code positions. Found by the Task 9 reviewer, reproduced by the controller: `\bex:` rewrites correctly in `ex:Concept a rdfs:Class ;` but ALSO corrupts `rdfs:comment "Write ex: before every term."@en .` and `# ... ex: is just a starting point.`. The seed ontology Task 10 writes is hand-authored prose-heavy Turtle whose comments explain the vocabulary, so this is a live vector, not a hypothetical. Fix: skip `#` comments and `"..."` string literals when substituting bare prefix usages. Defence in depth — Task 10's dispatch will also say not to use the prefix as English shorthand in the seed's prose. Cost if wrong: a project whose ontology genuinely wants `oldprefix:` inside a literal must fix it by hand after init; far cheaper than silent corruption.
Task 9: fix round 1/5 (3 addressed, 0 open — C20 scanner, rmtree guard, install-skill comment; 6bf11ac..22bb265). Controller independently verified the C20 headline case; re-reviewer probed 5 scanner edges (# in IRI, # in literal, escaped quote, prefix after literal) — all correct.
Task 9: minor (deferred): the line-scoped scanner does not track triple-quoted literals across lines, so mid-string prose on a later line containing the old prefix would corrupt. Assumption is documented at PROTECTED_SPAN; not reachable by the shipped seed. Task 10 is instructed not to use triple-quoted literals.
Task 9: minor (deferred): except UnicodeDecodeError lacks an inline reason; stale [template] comment remains after init; dependency_preset splice depends on exact double-space formatting; no direct cmd_init CLI test.
Task 9: complete (commits e7f8443..22bb265, review clean)
Task 10: dispatched — BASE = 22bb265

Ruling: C21 — accept the Task 10 implementer's correction. My brief's Step 7 put a `{{ONTOLOGY_FILE}}` token in `ontology/examples/webapp.ttl`, which is NOT in `init.MANIFEST` (verified: the manifest is knowledge.toml, ontology/README.md, docs/README.template.md, both agents, the skill). An unsubstituted token there would make `knowledge init --check` fail permanently in every generated repository — the same class of defect as C18. Using the literal default filename is correct. Cost if wrong: the comment names `ontology.ttl` even for a user who renamed the file; harmless prose.

| C22 | 9, 10 | `init` rewrites the project prefix but NOT the instance prefix declaration | Found by the CONTROLLER running the full lifecycle in a scratch copy, after Task 10 landed the seed. `init --name "Acme Widgets" --base-iri https://acme.test/ --prefix acme` produced `knowledge.toml` with `instances = "https://acme.test/id/"` but left `ontology/ontology.ttl` line 2 as `@prefix app: <https://example.com/id/> .`. |

Ruling: C22 — `init` must rewrite the instance prefix declaration's IRI (and its name, if `instance_prefix` changed) alongside the project prefix. The mismatch is silent and load-bearing: an `app:Foo` in any spec resolves to `https://example.com/id/Foo`, while `vocab.is_instance()` tests against `https://acme.test/id/` and returns False. That silently disables `dangling_terms`' instance half and `naming_violations`' underscore half — checks that then report clean without having checked, the exact failure this project has rejected seven times. It did not surface earlier because `init` deletes `specs/example/`, leaving a graph with no instances at all. Fix belongs in `init._rewrite_ontology_prefix`, which is Task 9's code. Cost if wrong: none identified; the two declarations must agree with the config by construction.

Task 9: fix round 2/5 (1 addressed, 0 open — C22 instance prefix; 22bb265..4715e43). Controller independently verified in a scratch init: `@prefix acme: <https://acme.test/ontology#>` and `@prefix app: <https://acme.test/id/>` both now agree with load_config. Implementer also fixed knowledge.toml's instance_prefix key, an adjacent gap it found while wiring — accepted, same failure class.

| C23 | 9 | `_reset_metadata` does not empty the dump | Found by the Task 9 implementer's own end-to-end proof, reproduced independently by the controller against the real repository: `.metadata/dump.sql` has 2 INSERT rows before init and 2 after. `db.connect()` reloads the existing dump into the "fresh" database before `db.save` writes it back unchanged, so deleting the .db file achieves nothing. Post-init, `knowledge scan` reports `missing 1: example has a row but no files` — every generated repository starts with a phantom row for the spec init just deleted. Did not surface in round 1 because the test fixture's dump.sql was trivial; Task 10's real dump has genuine content. |

Ruling: C23 — `_reset_metadata` must produce a genuinely empty dump: delete `.metadata/dump.sql` as well as the `.db` before connecting, so `db.connect()` has nothing to reload, then save. A generated repository must start with no spec rows at all. This is the same family as every other ruling here — state claiming something that is not so — and it is the first thing a new user would hit, since `scan` is step one of the documented workflow. Cost if wrong: none; a fresh template has no history worth preserving.
Task 9: fix round 3/5 (1 addressed, 0 open — C23 dump reset; 4715e43..49b41f9). Controller independently verified a generated repo end to end: 0 INSERT rows, scan missing 0, validate --strict exit 0, init --check clean, both @prefix lines agreeing with load_config.
Task 10: implemented (d810790). Suite 211/211 pristine. Implementer caught C21 (a {{ONTOLOGY_FILE}} token my brief put in a file outside init.MANIFEST) before it shipped.
Reviews dispatched in parallel (read-only, independent): Task 9 fix rounds 2-3 (a9a9cd3) and Task 10 content (a122581).

| C24 | 9 | two sequential prefix rewrites collide | Found by the Task 9 re-reviewer, reproduced independently by the controller. `_rewrite_ontology_prefix` runs `_rewrite_prefix_pair` twice in sequence. When the new project prefix equals the OLD instance prefix — i.e. `--prefix app`, where `app` is both the shipped default and the CLI's own suggested instance-prefix default — pass 1 rewrites `ex:` to `app:`, and pass 2's `count=1` declaration regex then matches the FIRST `@prefix app:` line, which is now the project declaration it just wrote. Verified output for `--prefix app`: line 1 becomes `@prefix app: <https://acme.test/id/>` (ontology namespace lost, replaced by the instances IRI) and line 2 stays `<https://example.com/id/>` (stale), leaving two `@prefix app:` declarations — rdflib takes the last, so every vocabulary term resolves into the instances namespace. With `--prefix app --instance-prefix ind`, the project's chosen prefix disappears from the file entirely and both declarations collapse onto `ind:`. The docstring claims order does not matter "because each searches only for its own old prefix text"; that claim is false once pass 1's output contains pass 2's search term. |

Ruling: C24 — replace the two sequential passes with ONE simultaneous substitution. Build a single mapping {old_project: new_project, old_instance: new_instance} and rewrite in one traversal, so no pass can ever observe another's output. This is the standard swap problem and sequential replacement cannot be made safe by ordering. Additionally, reject `prefix == instance_prefix` at the CLI: two prefixes that are equal cannot distinguish vocabulary terms from individuals, and no correct rewrite exists for that input. Cost if wrong: a user wanting one prefix for both roles is refused; that configuration is incoherent by construction, since `vocab.is_term` and `vocab.is_instance` would both match everything.

Task 9: entering fix round 4 — per the skill's escalation rule, dispatching a FRESH implementer on a more capable model rather than resuming (the incumbent's context is ~339k tokens and rounds 4-5 call for a capability bump).

| C25 | 10 | AUTHORING.md misdescribes `lint.domain_range_violations` | Found by the Task 10 reviewer, verified empirically by the controller. The guide claims that declaring two `rdfs:range` values would make the check "flag every single assertion of the property as wrong", permanently red. Ran it: with `ex:touches` declaring `rdfs:range ex:Field , ex:Concept`, a value typed only `Field` and a value typed only `Concept` BOTH pass — `domain_range_violations` returns `[]`. The function builds `ranges` as a set and flags only when `not (ranges & object_types)`, which is OR semantics on the object's type, not AND. |

Ruling: C25 — correct the guide to the true mechanism, which argues the same conclusion more strongly. Two ranges do not turn the check red; they make it PERMISSIVE, silently accepting any value typed as either, which hollows out `rdfs:range` as a promise about what a reader finds at the far end of the arrow. The general RDFS-entailment claim (two ranges jointly entail both types under a reasoner) is textbook-correct and may stay — the defect is the causal link drawn to THIS tool's checker. This matters because the guide's entire value is that a stranger can trust its reasoning about a codebase they have not read; a reader debugging a check that passed when they expected it to fail would find the guide contradicting the code. Cost if wrong: none — the corrected text is verifiable by running the linter.
