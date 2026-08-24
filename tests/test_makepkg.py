import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import linsys2.common as common
from linsys2.cli_makepkg import (
    WRAPPER_MARKER,
    build_bwrap_argv,
    ensure_build_bin,
)


class TestBuildBin(unittest.TestCase):
    def _make_env(self, td):
        bin_dir = Path(td) / "ucrt64" / "ucrt64" / "bin"
        bin_dir.mkdir(parents=True)
        return bin_dir

    def _run(self, td):
        with mock.patch.object(common, "DATA_DIR", Path(td)):
            ensure_build_bin("ucrt64")
        return Path(td) / "ucrt64" / "build-bin"

    def test_exe_and_bat_wrappers(self):
        with tempfile.TemporaryDirectory() as td:
            bin_dir = self._make_env(td)
            (bin_dir / "gcc.exe").touch()
            (bin_dir / "g++.exe").touch()
            (bin_dir / "foo.bat").touch()
            (bin_dir / "ar").touch()  # real file, no wrapper needed
            build_bin = self._run(td)

            gcc = (build_bin / "gcc").read_text()
            self.assertIn(WRAPPER_MARKER, gcc)
            self.assertIn(f"export WINEPREFIX='{td}/ucrt64/wine'", gcc)
            self.assertIn(f"exec wine '{bin_dir}/gcc.exe' \"$@\"", gcc)
            self.assertTrue(os.access(build_bin / "gcc", os.X_OK))
            self.assertIn("exec wine cmd /c", (build_bin / "foo").read_text())
            self.assertFalse((build_bin / "ar").exists())
            for shim in ("pacman", "pacman-conf", "cygpath", "uname"):
                self.assertTrue((build_bin / shim).exists())

    def test_shim_names_win_over_exe(self):
        with tempfile.TemporaryDirectory() as td:
            bin_dir = self._make_env(td)
            (bin_dir / "pacman.exe").touch()
            build_bin = self._run(td)
            self.assertIn("linsys2-pacman", (build_bin / "pacman").read_text())

    def test_stale_wrapper_pruned(self):
        with tempfile.TemporaryDirectory() as td:
            bin_dir = self._make_env(td)
            (bin_dir / "gcc.exe").touch()
            build_bin = self._run(td)
            self.assertTrue((build_bin / "gcc").exists())
            (bin_dir / "gcc.exe").unlink()
            (build_bin / "keep").write_text("#!/bin/sh\n# mine\n")
            self._run(td)
            self.assertFalse((build_bin / "gcc").exists())
            self.assertTrue((build_bin / "keep").exists())

    def test_missing_bin_dir_only_shims(self):
        with tempfile.TemporaryDirectory() as td:
            build_bin = self._run(td)
            self.assertEqual(sorted(p.name for p in build_bin.iterdir()),
                             ["cygpath", "pacman", "pacman-conf", "uname"])

    def test_uname_shim_reports_msys2(self):
        with tempfile.TemporaryDirectory() as td:
            build_bin = self._run(td)
            out = subprocess.run([str(build_bin / "uname"), "-s"],
                                 capture_output=True, text=True,
                                 check=True).stdout.strip()
            self.assertEqual(out, "MINGW64_NT-10.0-26100")
            out = subprocess.run([str(build_bin / "uname"), "-m"],
                                 capture_output=True, text=True,
                                 check=True).stdout.strip()
            self.assertEqual(out, "x86_64")


class TestBwrapArgv(unittest.TestCase):
    def test_prefix_mount(self):
        with mock.patch("linsys2.cli_makepkg._can_mount_fresh_proc",
                        return_value=True):
            argv = build_bwrap_argv("ucrt64", ["makepkg", "-s"])
        self.assertEqual(argv[0], "bwrap")
        env_prefix = str(common.DATA_DIR / "ucrt64" / "ucrt64")
        i = argv.index(env_prefix)
        self.assertEqual(argv[i - 1], "--bind")
        self.assertEqual(argv[i + 1], "/ucrt64")
        # the /ucrt64 top-level dir must not also be bound from the host
        for j, a in enumerate(argv[:-2]):
            if a == "--bind" and argv[j + 1] == "/ucrt64" \
                    and argv[j + 2] == "/ucrt64":
                self.fail("host /ucrt64 leaked into namespace")
        self.assertIn("--proc", argv)
        self.assertIn("makepkg", argv[-2:])
        self.assertEqual(argv[-1], "-s")

    def test_proc_bind_fallback(self):
        with mock.patch("linsys2.cli_makepkg._can_mount_fresh_proc",
                        return_value=False):
            argv = build_bwrap_argv("ucrt64", ["makepkg"])
        self.assertNotIn("--proc", argv)
        for j, a in enumerate(argv[:-2]):
            if a == "--bind" and argv[j + 1] == "/proc" \
                    and argv[j + 2] == "/proc":
                break
        else:
            self.fail("/proc not bound in fallback mode")


if __name__ == "__main__":
    unittest.main()
