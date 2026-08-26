"""Every git subprocess this package starts runs against the repository its path names,
never the one the ambient environment points at.

git exports GIT_DIR to the hooks it runs, and in a linked worktree that is an absolute path
to the worktree's gitdir. Anything a hook starts inherits it, and GIT_DIR outranks
`-C <path>` — it is checked before repository discovery, so `-C` only changes the working
directory. Under a pre-push hook that means `git init <tmpdir>` reinitialises the
*invoking* repository and leaves <tmpdir> with no repository at all, and
`git -C <tmpdir> add -A` stages <tmpdir>'s files into the invoking repository's index.

This tool reads a code repository and writes a wiki clone, both of them repositories other
than the one a hook would be running in, so `-C` meaning what it reads as is not a
convenience: `knowledge validate` runs from this repository's own pre-push hook, and
without the scrub it would have read this repository's history in place of the code
repository's and recorded the answer in the database.
"""

from __future__ import annotations

import os
import subprocess

# Kept because they describe the git installation or how it reaches a remote, not which
# repository it operates on. Everything else beginning with GIT_ is dropped — GIT_DIR,
# GIT_WORK_TREE, GIT_INDEX_FILE, GIT_OBJECT_DIRECTORY, GIT_COMMON_DIR, GIT_NAMESPACE and
# GIT_PREFIX bind git to a repository, and the GIT_AUTHOR_*/GIT_COMMITTER_* pair that git
# exports during a commit hook or a rebase would silently reattribute commits made here.
ENV_KEPT = frozenset(
    {
        "GIT_EXEC_PATH",
        "GIT_ASKPASS",
        "GIT_SSH",
        "GIT_SSH_COMMAND",
        "GIT_SSL_CAINFO",
        "GIT_SSL_NO_VERIFY",
        "GIT_TERMINAL_PROMPT",
    }
)


def clean_env(env: dict[str, str] | None = None) -> dict[str, str]:
    """`env` (os.environ by default) without the GIT_* variables that bind git to a
    repository. Non-GIT_ variables are untouched, GITHUB_* among them — the prefix tested
    is GIT_ with the underscore, so GITHUB_TOKEN and friends survive."""
    source = os.environ if env is None else env
    return {
        key: value
        for key, value in source.items()
        if not key.startswith("GIT_") or key in ENV_KEPT
    }


def run(args: list[str], *, env: dict[str, str] | None = None, **kwargs):
    """`git <args>` with the repository-binding environment scrubbed. Takes the argument
    list without the leading "git" and passes every other keyword through to
    subprocess.run, so callers keep check=, capture_output= and text=."""
    return subprocess.run(["git", *args], env=clean_env(env), **kwargs)
