#!/usr/bin/env python3
"""Human approval gate: the ONLY way a SwitchOps fix reaches the remote.

Agents have no remote and are denied `git push`. A human runs this script, which:
  1. fetches the proposed branch from the engineer's clone into a scratch clone of origin,
  2. re-runs the test suite itself (it does not trust any agent's report),
  3. shows the diff and asks for an explicit typed "yes" (or --yes for scripted runs),
  4. pushes the branch to origin, and with --merge fast-forwards main to it,
  5. appends an audit line to approvals.log.

Nothing here deploys anything.
"""
import argparse
import getpass
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def run(*cmd, cwd=None, check=True):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and p.returncode:
        sys.exit(f"command failed: {' '.join(cmd)}\n{p.stdout}{p.stderr}")
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--branch", required=True)
    ap.add_argument("--workspace", default=os.environ.get("SWITCHOPS_HOME", str(Path.home() / "switchops-workspace")))
    ap.add_argument("--repo", default="checkout-service")
    ap.add_argument("--merge", action="store_true", help="also fast-forward main to the branch")
    ap.add_argument("--yes", action="store_true", help="skip the interactive prompt (scripted runs)")
    a = ap.parse_args(argv)

    ws = Path(a.workspace)
    origin = ws / "origin.git"
    source = ws / "engineer" / a.repo
    if not origin.exists() or not source.exists():
        sys.exit(f"workspace not found at {ws}")
    if a.branch in ("main", "master"):
        sys.exit("refusing: approve a fix branch, not main")

    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp) / a.repo
        run("git", "clone", "-q", str(origin), str(scratch))
        fetched = run("git", "fetch", "-q", str(source), f"{a.branch}:{a.branch}", cwd=scratch, check=False)
        if fetched.returncode:
            sys.exit(f"branch {a.branch!r} not found in the engineer's clone:\n{fetched.stderr}")
        run("git", "switch", "-q", a.branch, cwd=scratch)
        sha = run("git", "rev-parse", "--short", "HEAD", cwd=scratch).stdout.strip()

        print(run("git", "log", "--oneline", f"origin/main..{a.branch}", cwd=scratch).stdout)
        print(run("git", "diff", "--stat", f"origin/main..{a.branch}", cwd=scratch).stdout)
        tests = run("python3", "-m", "unittest", "discover", "-s", "tests", "-v", cwd=scratch, check=False)
        if tests.returncode == 0 and "NO TESTS RAN" in tests.stderr:
            tests.returncode = 1  # zero tests is not a pass
        print(tests.stderr[-1500:])
        if tests.returncode:
            sys.exit("REFUSED: the test suite fails on this branch. Nothing was pushed.")

        action = "push and MERGE into main" if a.merge else "push the branch to origin"
        if not a.yes:
            answer = input(f"Tests pass at {sha}. Type 'yes' to {action}: ").strip().lower()
            if answer != "yes":
                sys.exit("Not approved. Nothing was pushed.")

        if a.merge:
            # ff-only: git rejects the push if main moved, so we never overwrite history
            run("git", "push", "-q", "origin", f"{a.branch}:main", cwd=scratch)
        else:
            run("git", "push", "-q", "origin", a.branch, cwd=scratch)

    entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "approver": getpass.getuser(),
             "branch": a.branch, "sha": sha, "merged": a.merge, "tests": "pass"}
    with open(ws / "approvals.log", "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"APPROVED and done: {action} ({sha}). Audit entry written to {ws / 'approvals.log'}.")


if __name__ == "__main__":
    main()
