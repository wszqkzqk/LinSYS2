import os
import subprocess
import sys
import unittest
from pathlib import Path

SHIM = Path(__file__).resolve().parent.parent / "python" / "linsys2" / "shims" / "cygpath"


def run(*args, env=None):
    return subprocess.run([sys.executable, str(SHIM), *args],
                          capture_output=True, text=True, env=env)


class TestCygpath(unittest.TestCase):
    def test_to_windows(self):
        r = run("-w", "/foo/bar")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "Z:\\foo\\bar")

    def test_to_unix(self):
        r = run("-u", "Z:\\foo\\bar")
        self.assertEqual(r.stdout.strip(), "/foo/bar")

    def test_mixed(self):
        r = run("-m", "/a/b")
        self.assertEqual(r.stdout.strip(), "Z:/a/b")

    def test_drive_letter_via_wineprefix(self):
        env = os.environ.copy()
        env["WINEPREFIX"] = "/wp"
        r = run("-u", "C:\\x\\y", env=env)
        self.assertEqual(r.stdout.strip(), "/wp/drive_c/x/y")

    def test_path_list(self):
        r = run("-u", "-p", "Z:\\a;Z:\\b")
        self.assertEqual(r.stdout.strip(), "/a:/b")
        r = run("-w", "-p", "/a:/b")
        self.assertEqual(r.stdout.strip(), "Z:\\a;Z:\\b")

    def test_path_list_keeps_drive_letters(self):
        r = run("-w", "-p", "Z:/a/lib:/ucrt64/lib")
        self.assertEqual(r.stdout.strip(), "Z:\\a\\lib;Z:\\ucrt64\\lib")

    def test_help_and_version(self):
        self.assertEqual(run("--help").returncode, 0)
        self.assertEqual(run("--version").returncode, 0)

    def test_unknown_option_fails(self):
        self.assertNotEqual(run("--bogus", "/x").returncode, 0)


if __name__ == "__main__":
    unittest.main()
