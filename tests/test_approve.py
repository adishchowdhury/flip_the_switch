"""Tests for the human approval gate, using real git repositories."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sh(*cmd, cwd=None, env=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, env=env)


class ApproveGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = Path(self.tmp.name) / "ws"
        env = {**os.environ, "SWITCHOPS_HOME": str(self.ws)}
        r = sh(str(ROOT / "scripts/build_demo_workspace.sh"), env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.eng = self.ws / "engineer" / "checkout-service"

    def tearDown(self):
        self.tmp.cleanup()

    def approve(self, *args):
        return sh("python3", str(ROOT / "scripts/approve.py"), "--workspace", str(self.ws), *args)

    def make_fix(self, branch="fix/test", good=True):
        sh("git", "switch", "-c", branch, cwd=self.eng)
        if good:
            h = self.eng / "checkout/handler.py"
            h.write_text(h.read_text().replace('resp.get("status")', 'resp.get("state")').replace('resp["transaction_id"]', 'resp["id"]'))
        else:
            (self.eng / "checkout/handler.py").write_text("# broken\n")
        sh("git", "commit", "-qam", "change", cwd=self.eng)

    def remote_branches(self):
        return sh("git", "branch", "--list", cwd=self.ws / "origin.git").stdout

    def test_engineer_has_no_remote(self):
        self.assertEqual(sh("git", "remote", cwd=self.eng).stdout.strip(), "")

    def test_broken_bug_is_real_on_main(self):
        r = sh("python3", "-m", "unittest", "discover", "-s", "tests", cwd=self.eng)
        self.assertNotEqual(r.returncode, 0)

    def test_good_fix_is_pushed_and_audited(self):
        self.make_fix()
        r = self.approve("--branch", "fix/test", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("fix/test", self.remote_branches())
        self.assertIn('"merged": false', (self.ws / "approvals.log").read_text())

    def test_failing_branch_is_refused(self):
        self.make_fix("fix/bad", good=False)
        r = self.approve("--branch", "fix/bad", "--yes")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("fix/bad", self.remote_branches())

    def test_no_approval_without_typed_yes(self):
        self.make_fix()
        r = subprocess.run(["python3", str(ROOT / "scripts/approve.py"), "--workspace", str(self.ws),
                            "--branch", "fix/test"], input="no\n", capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("fix/test", self.remote_branches())

    def test_main_cannot_be_approved(self):
        self.assertNotEqual(self.approve("--branch", "main", "--yes").returncode, 0)

    def test_merge_fast_forwards_main(self):
        self.make_fix()
        r = self.approve("--branch", "fix/test", "--merge", "--yes")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        log = sh("git", "log", "--oneline", "main", cwd=self.ws / "origin.git").stdout
        self.assertIn("change", log)


if __name__ == "__main__":
    unittest.main()
