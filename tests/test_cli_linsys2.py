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


if __name__ == "__main__":
    unittest.main()
