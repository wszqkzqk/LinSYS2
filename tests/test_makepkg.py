import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import linsys2.common as common
from linsys2.cli_makepkg import (
    binfmt_registered,
    build_bwrap_argv,
    ensure_tool_links,
)


def _write_binfmt_entry(d, name, content):
    (d / name).write_text(content)


class TestBinfmtRegistered(unittest.TestCase):
    def test_literal_mz_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_binfmt_entry(d, "DOSWin",
                                "enabled\ninterpreter /usr/bin/wine\nmagic MZ\n")
            self.assertTrue(binfmt_registered(d))

    def test_hex_magic_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_binfmt_entry(d, "wine",
                                "enabled\ninterpreter /usr/bin/wine\n"
                                "magic 4d5a\n")
            self.assertTrue(binfmt_registered(d))

    def test_disabled_entry(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_binfmt_entry(d, "DOSWin",
                                "disabled\ninterpreter /usr/bin/wine\nmagic MZ\n")
            self.assertFalse(binfmt_registered(d))

    def test_no_entries(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            _write_binfmt_entry(d, "register", "")
            _write_binfmt_entry(d, "status", "")
            self.assertFalse(binfmt_registered(d))

    def test_missing_dir(self):
        self.assertFalse(binfmt_registered("/nonexistent/binfmt"))


class TestToolLinks(unittest.TestCase):
    def _make_env(self, td):
        bin_dir = Path(td) / "ucrt64" / "ucrt64" / "bin"
        bin_dir.mkdir(parents=True)
        return bin_dir

    def test_create_and_prune(self):
        with tempfile.TemporaryDirectory() as td:
            bin_dir = self._make_env(td)
            (bin_dir / "gcc.exe").touch()
            (bin_dir / "g++.exe").touch()
            (bin_dir / "ar").touch()          # real file, no .exe
            os.symlink("old.exe", bin_dir / "old")      # our pattern, dangling
            os.symlink("other.exe", bin_dir / "kept")   # foreign pattern, dangling
            with mock.patch.object(common, "DATA_DIR", Path(td)):
                ensure_tool_links("ucrt64")
                self.assertEqual(os.readlink(bin_dir / "gcc"), "gcc.exe")
                self.assertEqual(os.readlink(bin_dir / "g++"), "g++.exe")
                self.assertFalse((bin_dir / "old").exists())
                self.assertEqual(os.readlink(bin_dir / "kept"), "other.exe")
                self.assertFalse((bin_dir / "ar").is_symlink())
                # removing the .exe prunes the generated link
                (bin_dir / "gcc.exe").unlink()
                ensure_tool_links("ucrt64")
                self.assertFalse((bin_dir / "gcc").exists())

    def test_existing_name_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            bin_dir = self._make_env(td)
            (bin_dir / "gcc.exe").touch()
            (bin_dir / "gcc").touch()          # package ships a real `gcc`
            with mock.patch.object(common, "DATA_DIR", Path(td)):
                ensure_tool_links("ucrt64")
                self.assertFalse((bin_dir / "gcc").is_symlink())


class TestBwrapArgv(unittest.TestCase):
    def test_prefix_mount(self):
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
        self.assertIn("makepkg", argv[-2:])
        self.assertEqual(argv[-1], "-s")


if __name__ == "__main__":
    unittest.main()
