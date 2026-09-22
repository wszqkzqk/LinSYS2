import os
import subprocess
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

import linsys2.cli_linsys2 as cli_linsys2
import linsys2.common as common


def _make_env(td):
    bin_dir = Path(td) / "ucrt64" / "ucrt64" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "foo.exe").touch()


def _fake_run(calls):
    def run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0, stdout="Z:\\mock\n")
    return run


class TestWineEnv(unittest.TestCase):
    def test_run_disables_winemenubuilder(self):
        with tempfile.TemporaryDirectory() as td:
            _make_env(td)
            calls = []
            with mock.patch.object(common, "DATA_DIR", Path(td)), \
                    mock.patch.object(cli_linsys2, "ensure_wine"), \
                    mock.patch.dict(os.environ, clear=True), \
                    mock.patch.object(cli_linsys2.subprocess, "run",
                                      side_effect=_fake_run(calls)):
                rc = cli_linsys2.cmd_run(
                    Namespace(env="ucrt64", prefix=None,
                              program="foo", args=[]))
            self.assertEqual(rc, 0)
            wine_env = next(kw["env"] for c, kw in calls if c[0] == "wine")
            self.assertEqual(wine_env["WINEDLLOVERRIDES"],
                             "winemenubuilder.exe=d")

    def test_run_merges_user_winedlloverrides(self):
        with tempfile.TemporaryDirectory() as td:
            _make_env(td)
            calls = []
            with mock.patch.object(common, "DATA_DIR", Path(td)), \
                    mock.patch.object(cli_linsys2, "ensure_wine"), \
                    mock.patch.dict(
                        os.environ, {"WINEDLLOVERRIDES": "d3d9=n"}), \
                    mock.patch.object(cli_linsys2.subprocess, "run",
                                      side_effect=_fake_run(calls)):
                rc = cli_linsys2.cmd_run(
                    Namespace(env="ucrt64", prefix=None,
                              program="foo", args=[]))
            self.assertEqual(rc, 0)
            wine_env = next(kw["env"] for c, kw in calls if c[0] == "wine")
            self.assertEqual(wine_env["WINEDLLOVERRIDES"],
                             "winemenubuilder.exe=d;d3d9=n")

    def test_run_user_override_wins_on_conflict(self):
        with tempfile.TemporaryDirectory() as td:
            _make_env(td)
            calls = []
            with mock.patch.object(common, "DATA_DIR", Path(td)), \
                    mock.patch.object(cli_linsys2, "ensure_wine"), \
                    mock.patch.dict(
                        os.environ,
                        {"WINEDLLOVERRIDES": "winemenubuilder.exe=b"}), \
                    mock.patch.object(cli_linsys2.subprocess, "run",
                                      side_effect=_fake_run(calls)):
                rc = cli_linsys2.cmd_run(
                    Namespace(env="ucrt64", prefix=None,
                              program="foo", args=[]))
            self.assertEqual(rc, 0)
            wine_env = next(kw["env"] for c, kw in calls if c[0] == "wine")
            self.assertEqual(wine_env["WINEDLLOVERRIDES"],
                             "winemenubuilder.exe=d;winemenubuilder.exe=b")

    def test_shell_disables_winemenubuilder(self):
        with tempfile.TemporaryDirectory() as td:
            _make_env(td)
            calls = []
            with mock.patch.object(common, "DATA_DIR", Path(td)), \
                    mock.patch.object(cli_linsys2, "ensure_wine"), \
                    mock.patch.dict(os.environ, {"SHELL": "/bin/bash"},
                                    clear=True), \
                    mock.patch.object(cli_linsys2.subprocess, "run",
                                      side_effect=_fake_run(calls)):
                rc = cli_linsys2.cmd_shell(
                    Namespace(env="ucrt64", prefix=None))
            self.assertEqual(rc, 0)
            shell_env = next(kw["env"] for c, kw in calls
                             if c[0] == "/bin/bash")
            self.assertEqual(shell_env["WINEDLLOVERRIDES"],
                             "winemenubuilder.exe=d")


class TestRegister(unittest.TestCase):
    def _run(self, func, td, ns, extra_env=None, home=None):
        calls = []
        env = extra_env if extra_env is not None else {}
        patches = [
            mock.patch.object(common, "DATA_DIR", Path(td)),
            mock.patch.object(cli_linsys2, "ensure_wine"),
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(cli_linsys2.subprocess, "run",
                              side_effect=_fake_run(calls)),
        ]
        if home is not None:
            patches.append(mock.patch.object(Path, "home", return_value=home))
        for p in patches:
            p.start()
        try:
            rc = func(ns)
        finally:
            for p in reversed(patches):
                p.stop()
        return rc, calls

    def test_register_defaults_to_home_wine(self):
        with tempfile.TemporaryDirectory() as td:
            _make_env(td)
            home = Path(td) / "home"
            home.mkdir()
            rc, calls = self._run(
                cli_linsys2.cmd_register, td,
                Namespace(env="ucrt64", prefix=None), home=home)
            self.assertEqual(rc, 0)
            cmds = [c for c, _ in calls]
            self.assertIn(["wineboot", "--init"], cmds)
            self.assertTrue(any(c[:3] == ["wine", "reg", "add"] for c in cmds))
            for _, kw in calls:
                self.assertEqual(kw["env"]["WINEPREFIX"], str(home / ".wine"))
            self.assertFalse((Path(td) / "ucrt64" / "wine").exists())

    def test_register_initializes_uninitialized_prefix(self):
        with tempfile.TemporaryDirectory() as td:
            _make_env(td)
            target = Path(td) / "fresh-prefix"
            rc, calls = self._run(
                cli_linsys2.cmd_register, td,
                Namespace(env="ucrt64", prefix=str(target)))
            self.assertEqual(rc, 0)
            cmds = [c for c, _ in calls]
            self.assertIn(["wineboot", "--init"], cmds)
            for _, kw in calls:
                self.assertEqual(kw["env"]["WINEPREFIX"], str(target))

    def test_register_into_existing_prefix(self):
        with tempfile.TemporaryDirectory() as td:
            _make_env(td)
            prefix = Path(td) / "user-wine"
            prefix.mkdir()
            rc, calls = self._run(
                cli_linsys2.cmd_register, td,
                Namespace(env="ucrt64", prefix=str(prefix)))
            self.assertEqual(rc, 0)
            cmds = [c for c, _ in calls]
            self.assertNotIn(["wineboot", "--init"], cmds)
            self.assertTrue(any(c[:3] == ["wine", "reg", "add"] for c in cmds))
            for _, kw in calls:
                self.assertEqual(kw["env"]["WINEPREFIX"], str(prefix))
                self.assertEqual(kw["env"]["WINEDLLOVERRIDES"],
                                 "winemenubuilder.exe=d")

    def test_unregister_without_existing_prefix_is_noop(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            home.mkdir()
            rc, calls = self._run(
                cli_linsys2.cmd_unregister, td,
                Namespace(env="ucrt64", prefix=None), home=home)
            self.assertEqual(rc, 0)
            self.assertEqual(calls, [])

    def test_env_uninitialized_prefix_has_no_side_effects(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / "home"
            home.mkdir()
            rc, calls = self._run(
                cli_linsys2.cmd_env, td,
                Namespace(env="ucrt64", prefix=None), home=home)
            self.assertEqual(rc, 0)
            self.assertEqual(calls, [])
            self.assertFalse((home / ".wine").exists())


if __name__ == "__main__":
    unittest.main()
