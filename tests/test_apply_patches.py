import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

TOP = Path(__file__).resolve().parent.parent

GIT_ENV = {**os.environ,
           "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   capture_output=True, env=GIT_ENV)


class TestApplyPatches(unittest.TestCase):
    def setUp(self):
        if not shutil.which("git") or not shutil.which("patch"):
            self.skipTest("git or patch not available")
        self._td = tempfile.TemporaryDirectory()
        top = Path(self._td.name)
        (top / "scripts").mkdir()
        shutil.copy(TOP / "scripts" / "apply-patches.sh", top / "scripts")
        (top / "patches").mkdir()
        (top / "patches" / "0001-x.patch").write_text(
            "--- a/code.c\n+++ b/code.c\n@@ -1,3 +1,3 @@\n"
            " int a;\n-int x;\n+int b;\n int z;\n")
        sub = top / "subprojects" / "msys2-pacman"
        sub.mkdir(parents=True)
        git("init", "-q", cwd=sub)
        git("config", "user.email", "t@t", cwd=sub)
        git("config", "user.name", "t", cwd=sub)
        (sub / "meson.build").write_text("project('x')\n")
        (sub / "code.c").write_text("int a;\nint x;\nint z;\n")
        git("add", ".", cwd=sub)
        git("commit", "-qm", "base", cwd=sub)
        self.top = top
        self.sub = sub

    def tearDown(self):
        self._td.cleanup()

    def run_script(self):
        return subprocess.run(
            ["sh", str(self.top / "scripts" / "apply-patches.sh")],
            capture_output=True, text=True, cwd=self.top, env=GIT_ENV)

    def head(self):
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.sub,
                              capture_output=True, text=True, check=True,
                              env=GIT_ENV).stdout.strip()

    def test_fresh_apply_and_skip(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.sub / "code.c").read_text(),
                         "int a;\nint b;\nint z;\n")
        stamp = self.sub / ".linsys2-patched.stamp"
        self.assertEqual(stamp.read_text().strip(), self.head())
        # Second run skips patching: WIP edits on top of patches survive.
        (self.sub / "code.c").write_text("int a;\nint b;\nint z;\nint wip;\n")
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("wip", (self.sub / "code.c").read_text())

    def test_ref_move_repatches(self):
        self.run_script()
        # Simulate a submodule update: ref moved, patch hunks wiped.
        git("checkout", "--", ".", cwd=self.sub)
        (self.sub / "code.c").write_text("int a;\nint x;\nint z;\nint c;\n")
        git("commit", "-qam", "bump", cwd=self.sub)
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.sub / "code.c").read_text(),
                         "int a;\nint b;\nint z;\nint c;\n")
        stamp = self.sub / ".linsys2-patched.stamp"
        self.assertEqual(stamp.read_text().strip(), self.head())

    def test_no_git_falls_back_to_mtime(self):
        # Tarball-like: content present but no git repo, patches pre-applied.
        shutil.rmtree(self.sub / ".git")
        (self.sub / "code.c").write_text("int a;\nint b;\nint z;\n")
        (self.sub / ".linsys2-patched.stamp").write_text("")
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.sub / "code.c").read_text(),
                         "int a;\nint b;\nint z;\n")


if __name__ == "__main__":
    unittest.main()
