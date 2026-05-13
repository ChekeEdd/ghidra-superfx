#!/usr/bin/env python3
"""Run a Codex code review on the current working tree.

Wraps the Claude Code Codex plugin's companion script so any
contributor (or any agent working in this repo) can run a quick
pre-commit review with a single command:

    python scripts/review.py            # foreground, --wait
    python scripts/review.py --bg       # send to background; check
                                        # status later via the plugin
    python scripts/review.py --base main   # review vs a named branch

Output is the raw JSON from codex-companion.mjs (status + stdout +
stderr blocks). On a clean review you'll see something like

    "stdout": "I did not identify any discrete correctness issues..."

On findings you'll see numbered review comments with file paths and
priority tags (P1/P2/P3). Address everything substantive before
committing — codex has caught several real bugs in the parent
Star Fox decomp project that the human review missed.

Locating the companion:
  - The script tries the standard Claude Code plugin cache locations
    on Windows, macOS, and Linux.
  - It also accepts a CODEX_COMPANION env var override, useful if
    the plugin lives somewhere non-standard.
  - As a last resort it falls back to a system `codex review` CLI
    invocation if one is on PATH.

Exit codes:
  0  review completed (does NOT mean clean — read the JSON)
  1  review tool not located or invocation failed
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


# Known locations for the Claude Code codex plugin companion. Order
# matters: we pick the first one whose .mjs exists. Add to this list
# if Claude Code ships the plugin elsewhere on your system.
_COMPANION_CANDIDATES = [
    # Windows
    r"C:\Users\{user}\.claude\plugins\cache\openai-codex\codex\{ver}\scripts\codex-companion.mjs",
    # macOS / Linux
    "/Users/{user}/.claude/plugins/cache/openai-codex/codex/{ver}/scripts/codex-companion.mjs",
    "/home/{user}/.claude/plugins/cache/openai-codex/codex/{ver}/scripts/codex-companion.mjs",
]

# Plugin versions to look for, newest first. Update as the upstream
# plugin releases new versions.
_COMPANION_VERSIONS = ["1.4.0", "1.3.0", "1.2.0", "1.1.0", "1.0.4", "1.0.0"]


def _parse_version(name: str) -> tuple[int, ...]:
    """Parse a directory name as a dotted-int version tuple.

    Used for newest-first sorting of plugin-cache directories so that
    `1.10.0` is treated as newer than `1.9.0` (a lexicographic sort
    would do the opposite). Non-numeric components fall through to a
    very-old sentinel so they sort last.
    """
    parts: list[int] = []
    for chunk in name.split("."):
        try:
            parts.append(int(chunk))
        except ValueError:
            # Mixed alpha tags (e.g. "1.4.0-rc1"); treat the alpha
            # suffix as older than any pure-numeric sibling.
            parts.append(-1)
            break
    return tuple(parts) if parts else (-1,)


def locate_companion() -> Path | None:
    """Find the codex-companion.mjs file, or None if not present."""
    override = os.environ.get("CODEX_COMPANION")
    if override:
        p = Path(override)
        if p.is_file():
            return p
        sys.stderr.write(
            f"CODEX_COMPANION points at {override} but the file does not exist; "
            f"falling back to plugin-cache search.\n"
        )

    user = os.environ.get("USER") or os.environ.get("USERNAME") or "HOME"
    home = Path.home()
    user_paths = [
        home / ".claude" / "plugins" / "cache" / "openai-codex" / "codex",
    ]
    for base in user_paths:
        if not base.is_dir():
            continue
        # Scan the cache directory for any plugin-version subdirectory.
        # Sort by parsed version tuple (newest first) so 1.10.0 wins over
        # 1.9.0; a purely lexicographic sort would pick the older one
        # once double-digit minor versions start appearing.
        children = [c for c in base.iterdir() if c.is_dir()]
        children.sort(key=lambda c: _parse_version(c.name), reverse=True)
        for child in children:
            cand = child / "scripts" / "codex-companion.mjs"
            if cand.is_file():
                return cand

    # Try the templated paths with known plugin versions.
    for tmpl in _COMPANION_CANDIDATES:
        for ver in _COMPANION_VERSIONS:
            cand = Path(tmpl.format(user=user, ver=ver))
            if cand.is_file():
                return cand
    return None


def run_companion(companion: Path, args: argparse.Namespace) -> int:
    """Invoke codex-companion.mjs review with the user's flags."""
    cmd = ["node", str(companion), "review", "--json"]
    if args.wait:
        cmd.append("--wait")
    elif args.bg:
        cmd.append("--background")
    if args.base:
        cmd += ["--base", args.base]
    if args.scope:
        cmd += ["--scope", args.scope]

    print(f"[..] {' '.join(cmd)}", file=sys.stderr)
    try:
        # We intentionally pass stdout through so the JSON is visible.
        # Filter out the Node deprecation warning that the companion
        # emits on Node 25+; it is noise and not a real failure.
        result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    except FileNotFoundError as e:
        sys.stderr.write(f"ERROR: could not run node — is it installed? ({e})\n")
        return 1

    out = result.stdout
    err = result.stderr
    # Strip the canonical Node deprecation warning if present; keep
    # everything else.
    for noisy in ("DeprecationWarning", "trace-deprecation"):
        err = "\n".join(line for line in err.splitlines() if noisy not in line)

    sys.stdout.write(out)
    if err.strip():
        sys.stderr.write(err)
    return result.returncode


def fallback_to_codex_cli(args: argparse.Namespace) -> int:
    """If the Claude Code plugin companion isn't installed, try the
    bare `codex` CLI. This is best-effort: not all codex versions
    support the same flags we use for the plugin path."""
    codex = shutil.which("codex")
    if not codex:
        sys.stderr.write(
            "ERROR: neither the Claude Code codex-companion.mjs nor a "
            "system `codex` CLI was found.\n"
            "Install the Claude Code Codex plugin "
            "(https://github.com/openai/codex-plugin-cc) or set "
            "CODEX_COMPANION to point at codex-companion.mjs explicitly.\n"
        )
        return 1

    sys.stderr.write(
        "[..] codex-companion.mjs not found; falling back to "
        f"`{codex} review` (some flags may be unsupported)\n"
    )
    cmd = [codex, "review"]
    if args.base:
        cmd += ["--base", args.base]
    return subprocess.call(cmd, shell=False)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--wait", action="store_true", default=True,
                     help="(default) wait for the review to complete in the foreground")
    grp.add_argument("--bg", "--background", dest="bg", action="store_true",
                     help="send the review to background; check status later via the plugin's task tools")
    ap.add_argument("--base",
                    help="git ref to diff against (e.g. main); default = working-tree review")
    ap.add_argument("--scope", choices=["auto", "working-tree", "branch"],
                    help="explicit review scope (otherwise the companion auto-detects)")
    args = ap.parse_args()
    if args.bg:
        args.wait = False

    companion = locate_companion()
    if companion is None:
        return fallback_to_codex_cli(args)
    return run_companion(companion, args)


if __name__ == "__main__":
    sys.exit(main())
