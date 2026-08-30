import contextlib
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock

import linsys2.cli_pacman as cli_pacman
import linsys2.common as common


@contextlib.contextmanager
def _patch_dirs(td):
    """Redirect CONFIG_DIR and DATA_DIR into a temp directory."""
    with mock.patch.object(cli_pacman, "CONFIG_DIR", Path(td) / "config"), \
            mock.patch.object(common, "DATA_DIR", Path(td) / "data"):
        yield


@contextlib.contextmanager
def _mock_init_deps(prompt_return="n", prompt_side_effect=None):
    """Mock everything cmd_init touches after the prompt: config creation,
    pacman-key, and input()."""
    input_kwargs = ({"side_effect": prompt_side_effect}
                    if prompt_side_effect is not None
                    else {"return_value": prompt_return})
    with mock.patch.object(cli_pacman, "create_config"), \
            mock.patch.object(cli_pacman, "get_pacman_key_binary",
                              return_value="/bin/true"), \
            mock.patch.object(cli_pacman.subprocess, "run"), \
            mock.patch("builtins.input", **input_kwargs) as input_mock:
        yield input_mock


class TestRunPacman(unittest.TestCase):
    def test_errors_when_uninitialized(self):
        with tempfile.TemporaryDirectory() as td, \
                _patch_dirs(td), \
                mock.patch.object(cli_pacman, "get_pacman_binary",
                                  return_value="/bin/true"), \
                mock.patch.object(cli_pacman.subprocess, "run") as run_mock:
            rc = cli_pacman.run_pacman("ucrt64", ["-Sy", "gcc"])
        self.assertEqual(rc, 1)
        run_mock.assert_not_called()

    def test_runs_when_config_exists(self):
        """The gate checks the config file only; after init, pacman owns
        everything under RootDir."""
        with tempfile.TemporaryDirectory() as td, \
                _patch_dirs(td), \
                mock.patch.object(cli_pacman, "get_pacman_binary",
                                  return_value="/bin/true"), \
                mock.patch.object(cli_pacman.subprocess, "run",
                                  return_value=subprocess.CompletedProcess(
                                      [], returncode=0)) as run_mock:
            config = Path(td) / "config" / "ucrt64.conf"
            config.parent.mkdir(parents=True)
            config.touch()
            rc = cli_pacman.run_pacman("ucrt64", ["-Q"])
        self.assertEqual(rc, 0)
        run_mock.assert_called_once()

    def _run_with_config(self, td, run_kwargs):
        with _patch_dirs(td), \
                mock.patch.object(cli_pacman, "get_pacman_binary",
                                  return_value="/bin/true"), \
                mock.patch.object(cli_pacman.subprocess, "run",
                                  **run_kwargs):
            config = Path(td) / "config" / "ucrt64.conf"
            config.parent.mkdir(parents=True)
            config.touch()
            return cli_pacman.run_pacman("ucrt64", ["-Syu"])

    def test_signal_exit_maps_to_128_plus_n(self):
        with tempfile.TemporaryDirectory() as td:
            rc = self._run_with_config(
                td, {"return_value": subprocess.CompletedProcess(
                    [], returncode=-2)})
        self.assertEqual(rc, 130)

    def test_keyboard_interrupt_maps_to_130(self):
        with tempfile.TemporaryDirectory() as td:
            rc = self._run_with_config(
                td, {"side_effect": KeyboardInterrupt})
        self.assertEqual(rc, 130)


class TestCmdInit(unittest.TestCase):
    def test_wine_prefix_alone_does_not_prompt(self):
        with tempfile.TemporaryDirectory() as td, \
                _patch_dirs(td), _mock_init_deps(
                    prompt_side_effect=AssertionError("prompted")) \
                as input_mock:
            (Path(td) / "data" / "ucrt64" / "wine").mkdir(parents=True)
            rc = cli_pacman.cmd_init(Namespace(env="ucrt64", force=False))
        self.assertEqual(rc, 0)
        input_mock.assert_not_called()

    def test_existing_config_prompts(self):
        with tempfile.TemporaryDirectory() as td, \
                _patch_dirs(td), _mock_init_deps() as input_mock:
            config = Path(td) / "config" / "ucrt64.conf"
            config.parent.mkdir(parents=True)
            config.touch()
            rc = cli_pacman.cmd_init(Namespace(env="ucrt64", force=False))
        self.assertEqual(rc, 1)
        input_mock.assert_called_once()

    def test_existing_db_prompts(self):
        with tempfile.TemporaryDirectory() as td, \
                _patch_dirs(td), _mock_init_deps() as input_mock:
            (Path(td) / "data" / "ucrt64" / "var" / "lib" / "pacman"
             ).mkdir(parents=True)
            rc = cli_pacman.cmd_init(Namespace(env="ucrt64", force=False))
        self.assertEqual(rc, 1)
        input_mock.assert_called_once()

    def test_force_skips_prompt(self):
        with tempfile.TemporaryDirectory() as td, \
                _patch_dirs(td), _mock_init_deps(
                    prompt_side_effect=AssertionError("prompted")) \
                as input_mock:
            config = Path(td) / "config" / "ucrt64.conf"
            config.parent.mkdir(parents=True)
            config.touch()
            rc = cli_pacman.cmd_init(Namespace(env="ucrt64", force=True))
        self.assertEqual(rc, 0)
        input_mock.assert_not_called()


class TestUpdateKeyring(unittest.TestCase):
    def test_oserror_reports_cleanly(self):
        with tempfile.TemporaryDirectory() as td, _patch_dirs(td):
            config = Path(td) / "config" / "ucrt64.conf"
            config.parent.mkdir(parents=True)
            config.touch()
            with mock.patch.object(cli_pacman, "get_pacman_key_binary",
                                   return_value="/missing/pacman-key"), \
                    mock.patch.object(cli_pacman.subprocess, "run",
                                      side_effect=OSError("no such file")):
                rc = cli_pacman.cmd_update_keyring(Namespace(env="ucrt64"))
        self.assertEqual(rc, 1)


class TestMain(unittest.TestCase):
    def _main(self, *argv):
        with mock.patch.object(sys, "argv", ["linsys2-pacman", *argv]), \
                mock.patch.object(cli_pacman, "run_pacman",
                                  return_value=0) as rp:
            rc = cli_pacman.main()
        return rc, rp

    def test_version_after_env(self):
        rc, rp = self._main("--env", "clang64", "--version")
        self.assertEqual(rc, 0)
        rp.assert_not_called()

    def test_help_after_env(self):
        rc, rp = self._main("--env", "clang64", "help")
        self.assertEqual(rc, 0)
        rp.assert_not_called()

    def test_pacman_help_passthrough(self):
        rc, rp = self._main("-Syu", "--help")
        self.assertEqual(rc, 0)
        rp.assert_called_once_with(cli_pacman.DEFAULT_ENV,
                                   ["-Syu", "--help"])


class TestCreateConfig(unittest.TestCase):
    def test_creates_config_and_mirrorlist(self):
        with tempfile.TemporaryDirectory() as td, _patch_dirs(td):
            cli_pacman.create_config("ucrt64")
            config = Path(td) / "config" / "ucrt64.conf"
            self.assertIn("SigLevel     = Required DatabaseOptional",
                          config.read_text())
            self.assertIn("Server = ",
                          (Path(td) / "config" / "mirrorlist.mingw")
                          .read_text())

    def test_pristine_files_rewritten_silently(self):
        with tempfile.TemporaryDirectory() as td, _patch_dirs(td):
            cli_pacman.create_config("ucrt64")
            with mock.patch.object(cli_pacman, "info") as info_mock:
                cli_pacman.create_config("ucrt64")
            info_mock.assert_not_called()

    def test_modified_config_gets_pacnew(self):
        with tempfile.TemporaryDirectory() as td, _patch_dirs(td):
            cli_pacman.create_config("ucrt64")
            config = Path(td) / "config" / "ucrt64.conf"
            config.write_text("# my custom config\n")
            cli_pacman.create_config("ucrt64")
            self.assertEqual(config.read_text(), "# my custom config\n")
            pacnew = Path(td) / "config" / "ucrt64.conf.pacnew"
            self.assertIn("SigLevel", pacnew.read_text())

    def test_modified_mirrorlist_gets_pacnew(self):
        with tempfile.TemporaryDirectory() as td, _patch_dirs(td):
            cli_pacman.create_config("ucrt64")
            mirrorlist = Path(td) / "config" / "mirrorlist.mingw"
            mirrorlist.write_text("Server = https://my.mirror/\n")
            cli_pacman.create_config("ucrt64")
            self.assertEqual(mirrorlist.read_text(),
                             "Server = https://my.mirror/\n")
            pacnew = Path(td) / "config" / "mirrorlist.mingw.pacnew"
            self.assertTrue(pacnew.exists())


if __name__ == "__main__":
    unittest.main()
