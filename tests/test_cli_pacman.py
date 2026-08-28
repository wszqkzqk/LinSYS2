import contextlib
import subprocess
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
    def test_aborts_when_init_fails(self):
        with tempfile.TemporaryDirectory() as td, \
                _patch_dirs(td), \
                mock.patch.object(cli_pacman, "get_pacman_binary",
                                  return_value="/bin/true"), \
                mock.patch.object(cli_pacman, "cmd_init", return_value=1), \
                mock.patch.object(cli_pacman.subprocess, "run") as run_mock:
            rc = cli_pacman.run_pacman("ucrt64", ["-Sy", "gcc"])
        self.assertEqual(rc, 1)
        run_mock.assert_not_called()

    def test_auto_init_when_uninitialized(self):
        with tempfile.TemporaryDirectory() as td, \
                _patch_dirs(td), \
                mock.patch.object(cli_pacman, "get_pacman_binary",
                                  return_value="/bin/true"), \
                mock.patch.object(cli_pacman, "cmd_init", return_value=0) \
                as init_mock, \
                mock.patch.object(cli_pacman.subprocess, "run",
                                  return_value=subprocess.CompletedProcess(
                                      [], returncode=0)) as run_mock:
            rc = cli_pacman.run_pacman("ucrt64", ["-Sy", "gcc"])
        self.assertEqual(rc, 0)
        init_mock.assert_called_once()
        run_mock.assert_called_once()

    def test_runs_when_initialized(self):
        with tempfile.TemporaryDirectory() as td, \
                _patch_dirs(td), \
                mock.patch.object(cli_pacman, "get_pacman_binary",
                                  return_value="/bin/true"), \
                mock.patch.object(cli_pacman, "cmd_init", return_value=1) \
                as init_mock, \
                mock.patch.object(cli_pacman.subprocess, "run",
                                  return_value=subprocess.CompletedProcess(
                                      [], returncode=0)) as run_mock:
            config = Path(td) / "config" / "ucrt64.conf"
            config.parent.mkdir(parents=True)
            config.touch()
            db = Path(td) / "data" / "ucrt64" / "var" / "lib" / "pacman"
            db.mkdir(parents=True)
            rc = cli_pacman.run_pacman("ucrt64", ["-Q"])
        self.assertEqual(rc, 0)
        init_mock.assert_not_called()
        run_mock.assert_called_once()


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


class TestIsInitialized(unittest.TestCase):
    def test_states(self):
        with tempfile.TemporaryDirectory() as td, _patch_dirs(td):
            config = Path(td) / "config" / "ucrt64.conf"
            db = Path(td) / "data" / "ucrt64" / "var" / "lib" / "pacman"
            self.assertFalse(cli_pacman.is_initialized("ucrt64"))
            config.parent.mkdir(parents=True)
            config.touch()
            self.assertFalse(cli_pacman.is_initialized("ucrt64"))
            db.mkdir(parents=True)
            self.assertTrue(cli_pacman.is_initialized("ucrt64"))
            config.unlink()
            self.assertFalse(cli_pacman.is_initialized("ucrt64"))


class TestInitRollback(unittest.TestCase):
    def test_failed_fresh_init_leaves_no_trace(self):
        """A failed first init must not look initialized, so later runs
        retry the keyring instead of failing on signature errors."""
        with tempfile.TemporaryDirectory() as td, \
                _patch_dirs(td), \
                mock.patch.object(cli_pacman, "get_pacman_key_binary",
                                  return_value="/bin/true"), \
                mock.patch.object(cli_pacman.subprocess, "run",
                                  side_effect=subprocess.CalledProcessError(
                                      1, ["pacman-key"])) as run_mock:
            rc = cli_pacman.cmd_init(Namespace(env="ucrt64", force=True))
            self.assertEqual(rc, 1)
            self.assertFalse((Path(td) / "config" / "ucrt64.conf").exists())
            self.assertFalse((Path(td) / "data" / "ucrt64"
                              / "var" / "lib" / "pacman").exists())
            # The retried init succeeds and the environment works.
            run_mock.side_effect = None
            run_mock.return_value = subprocess.CompletedProcess([], 0)
            self.assertEqual(
                cli_pacman.cmd_init(Namespace(env="ucrt64", force=True)), 0)
            self.assertTrue(cli_pacman.is_initialized("ucrt64"))

    def test_failed_reinit_keeps_existing_config(self):
        """A failed re-init of an existing environment must not wipe the
        state that was there before."""
        with tempfile.TemporaryDirectory() as td, \
                _patch_dirs(td), \
                mock.patch.object(cli_pacman, "get_pacman_key_binary",
                                  return_value="/bin/true"), \
                mock.patch.object(cli_pacman.subprocess, "run",
                                  side_effect=subprocess.CalledProcessError(
                                      1, ["pacman-key"])):
            config = Path(td) / "config" / "ucrt64.conf"
            config.parent.mkdir(parents=True)
            config.write_text("previous config")
            (Path(td) / "data" / "ucrt64" / "var" / "lib" / "pacman"
             ).mkdir(parents=True)
            rc = cli_pacman.cmd_init(Namespace(env="ucrt64", force=True))
            self.assertEqual(rc, 1)
            self.assertTrue(config.exists())


class TestAutoInitRepair(unittest.TestCase):
    def test_auto_init_does_not_prompt(self):
        """Auto-init repairs without asking; in CI there is no one to
        answer a prompt. Uses a half-initialized environment (config
        without db dir): the state where the code used to stop and ask
        "Reinitialize?" even though it had decided to repair on its own."""
        with tempfile.TemporaryDirectory() as td, \
                _patch_dirs(td), \
                mock.patch.object(cli_pacman, "get_pacman_binary",
                                  return_value="/bin/true"), \
                mock.patch.object(cli_pacman, "get_pacman_key_binary",
                                  return_value="/bin/true"), \
                mock.patch("builtins.input",
                           side_effect=AssertionError("prompted")), \
                mock.patch.object(cli_pacman.subprocess, "run",
                                  return_value=subprocess.CompletedProcess(
                                      [], returncode=0)):
            config = Path(td) / "config" / "ucrt64.conf"
            config.parent.mkdir(parents=True)
            config.touch()
            rc = cli_pacman.run_pacman("ucrt64", ["-Q"])
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
