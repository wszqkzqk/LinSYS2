import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import linsys2.cli_makepkg as cli_makepkg
import linsys2.common as common
from linsys2.cli_makepkg import (
    WRAPPER_MARKER,
    acquire_env_lock,
    build_bwrap_argv,
    ensure_build_bin,
    pacman_auth,
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
            # No winepath on PATH: the Z: fallback must be used.
            with mock.patch.dict(os.environ, {"PATH": "/nonexistent"}):
                build_bin = self._run(td)

            gcc = (build_bin / "gcc").read_text()
            self.assertIn(WRAPPER_MARKER, gcc)
            self.assertIn(f"export WINEPREFIX={shlex.quote(td + '/ucrt64/wine')}", gcc)
            self.assertIn(f"exec wine {shlex.quote(str(bin_dir / 'gcc.exe'))} \"$@\"", gcc)
            self.assertTrue(os.access(build_bin / "gcc", os.X_OK))
            bat = (build_bin / "foo.bat").read_text()
            self.assertIn("exec wine cmd /c", bat)
            self.assertIn("Z:\\", bat)
            self.assertFalse((build_bin / "foo").exists())
            self.assertFalse((build_bin / "ar").exists())
            for shim in ("pacman", "pacman-conf", "cygpath", "uname", "arch"):
                self.assertTrue((build_bin / shim).exists())

    def test_exe_wins_bare_name_over_bat(self):
        with tempfile.TemporaryDirectory() as td:
            bin_dir = self._make_env(td)
            (bin_dir / "foo.exe").touch()
            (bin_dir / "foo.bat").touch()
            with mock.patch.dict(os.environ, {"PATH": "/nonexistent"}):
                build_bin = self._run(td)
            foo = (build_bin / "foo").read_text()
            self.assertIn("foo.exe", foo)
            self.assertNotIn("cmd /c", foo)
            self.assertIn("cmd /c", (build_bin / "foo.bat").read_text())

    def test_bat_wrapper_uses_winepath(self):
        with tempfile.TemporaryDirectory() as td:
            bin_dir = self._make_env(td)
            (bin_dir / "foo.bat").touch()
            stub_dir = Path(td) / "stub"
            stub_dir.mkdir()
            log = Path(td) / "log"
            (stub_dir / "winepath").write_text(
                f"#!/bin/sh\necho \"$WINEPREFIX\" > '{log}'\n"
                "printf 'Q:\\\\custom\\\\foo.bat\\n'\n")
            (stub_dir / "winepath").chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": str(stub_dir)}):
                build_bin = self._run(td)
            bat = (build_bin / "foo.bat").read_text()
            self.assertIn("Q:\\custom\\foo.bat", bat)
            self.assertEqual(log.read_text().strip(),
                             str(Path(td) / "ucrt64" / "wine"))

    def test_bat_wrapper_falls_back_on_non_utf8_winepath(self):
        with tempfile.TemporaryDirectory() as td:
            bin_dir = self._make_env(td)
            (bin_dir / "foo.bat").touch()
            stub_dir = Path(td) / "stub"
            stub_dir.mkdir()
            (stub_dir / "winepath").write_text(
                "#!/bin/sh\nprintf '\\377\\376\\n'\n")
            (stub_dir / "winepath").chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": str(stub_dir)}):
                build_bin = self._run(td)
            self.assertIn("Z:\\", (build_bin / "foo.bat").read_text())

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

    def test_prune_ignores_non_utf8_files(self):
        with tempfile.TemporaryDirectory() as td:
            bin_dir = self._make_env(td)
            (bin_dir / "gcc.exe").touch()
            build_bin = self._run(td)
            blob = build_bin / "blob"
            blob.write_bytes(b"\xff\xfe\x00\x01")
            self._run(td)
            self.assertTrue(blob.exists())
            self.assertTrue((build_bin / "gcc").exists())

    def test_non_utf8_file_at_target_name_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            bin_dir = self._make_env(td)
            (bin_dir / "gcc.exe").touch()
            build_bin = self._run(td)
            (build_bin / "gcc").write_bytes(b"\xff\xfe\x00\x01")
            self._run(td)
            self.assertIn(WRAPPER_MARKER, (build_bin / "gcc").read_text())

    def test_missing_bin_dir_only_shims(self):
        with tempfile.TemporaryDirectory() as td:
            build_bin = self._run(td)
            self.assertEqual(sorted(p.name for p in build_bin.iterdir()),
                             ["arch", "cygpath", "pacman", "pacman-conf",
                              "uname"])

    def test_custom_wineprefix_baked_into_wrappers(self):
        with tempfile.TemporaryDirectory() as td:
            bin_dir = self._make_env(td)
            (bin_dir / "gcc.exe").touch()
            with mock.patch.object(common, "DATA_DIR", Path(td)):
                ensure_build_bin("ucrt64", Path("/wp-custom"))
            gcc = (Path(td) / "ucrt64" / "build-bin" / "gcc").read_text()
            self.assertIn(f"export WINEPREFIX={shlex.quote('/wp-custom')}", gcc)

    def test_wrapper_with_quoted_paths(self):
        with tempfile.TemporaryDirectory() as td:
            bin_dir = self._make_env(td)
            (bin_dir / "gcc.exe").touch()
            wp = Path(td) / "o'brien"
            with mock.patch.object(common, "DATA_DIR", Path(td)):
                ensure_build_bin("ucrt64", wp)
            gcc = Path(td) / "ucrt64" / "build-bin" / "gcc"
            content = gcc.read_text()
            self.assertIn(f"export WINEPREFIX={shlex.quote(str(wp))}", content)
            self.assertIn(f"exec wine {shlex.quote(str(bin_dir / 'gcc.exe'))}",
                          content)
            subprocess.run(["sh", "-n", str(gcc)], check=True)

    def _uname(self, build_bin, *args, wine=None):
        # Run the shim with PATH limited to a stub dir (+ stub wine if given).
        with tempfile.TemporaryDirectory() as stub_dir:
            env = os.environ.copy()
            env["PATH"] = stub_dir
            if wine is not None:
                stub = Path(stub_dir) / "wine"
                stub.write_text(f"#!/bin/sh\nprintf '%s\\n' '{wine}'\n"
                                f"echo \"$WINEPREFIX\" > '{stub_dir}/wp'\n")
                stub.chmod(0o755)
            result = subprocess.run([str(build_bin / "uname"), *args],
                                    capture_output=True, text=True, env=env)
            wp = Path(stub_dir) / "wp"
            result.wineprefix = wp.read_text().strip() if wp.exists() else None
            return result

    def test_uname_shim_reports_msys2(self):
        with tempfile.TemporaryDirectory() as td:
            build_bin = self._run(td)
            # No wine on PATH: the shim falls back to its default.
            out = self._uname(build_bin, "-s")
            self.assertEqual(out.stdout.strip(), "MINGW64_NT-10.0-19043")
            out = self._uname(build_bin, "-m")
            self.assertEqual(out.stdout.strip(), "x86_64")
            out = self._uname(build_bin)
            self.assertEqual(out.stdout.strip(), "MINGW64_NT-10.0-19043")

    def test_uname_shim_sysname_from_wine(self):
        with tempfile.TemporaryDirectory() as td:
            build_bin = self._run(td)
            out = self._uname(build_bin, "-s",
                              wine="Microsoft Windows 10.0.26300")
            self.assertEqual(out.stdout.strip(), "MINGW64_NT-10.0-26300")
            self.assertEqual(out.wineprefix,
                             str(Path(td) / "ucrt64" / "wine"))

    def test_uname_shim_sysname_from_wine_win7(self):
        with tempfile.TemporaryDirectory() as td:
            build_bin = self._run(td)
            out = self._uname(build_bin, "-s",
                              wine="Microsoft Windows 6.1.7601")
            self.assertEqual(out.stdout.strip(), "MINGW64_NT-6.1-7601")

    def test_uname_shim_sysname_fallback(self):
        with tempfile.TemporaryDirectory() as td:
            build_bin = self._run(td)
            out = self._uname(build_bin, "-s", wine="garbage")
            self.assertEqual(out.stdout.strip(), "MINGW64_NT-10.0-19043")

    def test_uname_shim_sysname_fallback_non_utf8(self):
        with tempfile.TemporaryDirectory() as td:
            build_bin = self._run(td)
            stub_dir = Path(td) / "stub"
            stub_dir.mkdir()
            (stub_dir / "wine").write_text(
                "#!/bin/sh\nprintf '\\377\\376\\n'\n")
            (stub_dir / "wine").chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = stub_dir
            out = subprocess.run([str(build_bin / "uname"), "-s"],
                                 capture_output=True, text=True, env=env)
            self.assertEqual(out.stdout.strip(), "MINGW64_NT-10.0-19043")

    def test_uname_shim_combined_flags(self):
        with tempfile.TemporaryDirectory() as td:
            build_bin = self._run(td)
            # Combined short flags must not fall through to the host uname.
            out = self._uname(build_bin, "-sm")
            self.assertEqual(out.stdout.strip(),
                             "MINGW64_NT-10.0-19043 x86_64")
            out = self._uname(build_bin, "-srm")
            self.assertEqual(out.stdout.strip(),
                             "MINGW64_NT-10.0-19043 "
                             "3.6.10-8fbd9808.x86_64 x86_64")
            # Fixed output order, independent of option order/repetition.
            out = self._uname(build_bin, "-ms")
            self.assertEqual(out.stdout.strip(),
                             "MINGW64_NT-10.0-19043 x86_64")
            out = self._uname(build_bin, "-ss")
            self.assertEqual(out.stdout.strip(), "MINGW64_NT-10.0-19043")

    def test_uname_shim_all(self):
        with tempfile.TemporaryDirectory() as td:
            build_bin = self._run(td)
            out = self._uname(build_bin, "-a")
            self.assertEqual(
                out.stdout.strip(),
                f"MINGW64_NT-10.0-19043 {os.uname().nodename} "
                "3.6.10-8fbd9808.x86_64 2026-08-13 11:15 UTC x86_64 Msys")
            out = self._uname(build_bin, "-p")
            self.assertEqual(out.stdout.strip(), "unknown")
            out = self._uname(build_bin, "-pi")
            self.assertEqual(out.stdout.strip(), "unknown unknown")

    def test_uname_shim_long_options(self):
        with tempfile.TemporaryDirectory() as td:
            build_bin = self._run(td)
            out = self._uname(build_bin, "--machine")
            self.assertEqual(out.stdout.strip(), "x86_64")
            out = self._uname(build_bin, "--kernel-name")
            self.assertEqual(out.stdout.strip(), "MINGW64_NT-10.0-19043")
            # Obsolescent but valid GNU aliases.
            out = self._uname(build_bin, "--sysname")
            self.assertEqual(out.stdout.strip(), "MINGW64_NT-10.0-19043")
            out = self._uname(build_bin, "--release")
            self.assertEqual(out.stdout.strip(), "3.6.10-8fbd9808.x86_64")
            out = self._uname(build_bin, "--operating-system")
            self.assertEqual(out.stdout.strip(), "Msys")
            out = self._uname(build_bin, "--version")
            self.assertEqual(out.returncode, 0)
            self.assertTrue(out.stdout.startswith("uname (GNU coreutils)"))
            out = self._uname(build_bin, "--help")
            self.assertEqual(out.returncode, 0)

    def test_uname_shim_rejects_bad_usage(self):
        with tempfile.TemporaryDirectory() as td:
            build_bin = self._run(td)
            out = self._uname(build_bin, "-x")
            self.assertNotEqual(out.returncode, 0)
            self.assertIn("invalid option", out.stderr)
            out = self._uname(build_bin, "--bogus")
            self.assertNotEqual(out.returncode, 0)
            self.assertIn("unrecognized option", out.stderr)
            out = self._uname(build_bin, "foo")
            self.assertNotEqual(out.returncode, 0)
            self.assertIn("extra operand", out.stderr)
            out = self._uname(build_bin, "--", "foo")
            self.assertNotEqual(out.returncode, 0)
            self.assertIn("extra operand", out.stderr)

    def test_arch_shim(self):
        with tempfile.TemporaryDirectory() as td:
            build_bin = self._run(td)
            out = subprocess.run([str(build_bin / "arch")],
                                 capture_output=True, text=True)
            self.assertEqual(out.stdout.strip(), "x86_64")
            out = subprocess.run([str(build_bin / "arch"), "--version"],
                                 capture_output=True, text=True)
            self.assertEqual(out.returncode, 0)
            self.assertTrue(out.stdout.startswith("arch (GNU coreutils)"))
            out = subprocess.run([str(build_bin / "arch"), "foo"],
                                 capture_output=True, text=True)
            self.assertNotEqual(out.returncode, 0)


class TestPacmanAuth(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        td = Path(self._td.name)
        bin_dir = td / "ucrt64" / "ucrt64" / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "gcc.exe").touch()
        self.build_bin = td / "ucrt64" / "build-bin"
        self._env = mock.patch.dict(os.environ, {
            "LINSYS2_ENV": "ucrt64",
            "WINEPREFIX": str(td / "ucrt64" / "wine"),
        })
        self._env.start()
        self._data = mock.patch.object(common, "DATA_DIR", td)
        self._data.start()

    def tearDown(self):
        self._data.stop()
        self._env.stop()
        self._td.cleanup()

    def test_success_refreshes_wrappers(self):
        self.assertEqual(pacman_auth(["true"]), 0)
        self.assertIn(
            f"export WINEPREFIX={shlex.quote(self._td.name + '/ucrt64/wine')}",
            (self.build_bin / "gcc").read_text())

    def test_failure_no_refresh(self):
        self.assertEqual(pacman_auth(["sh", "-c", "exit 3"]), 3)
        self.assertFalse(self.build_bin.exists())

    def test_signal_maps_to_128_plus_n(self):
        self.assertEqual(pacman_auth(["sh", "-c", "kill -INT $$"]), 130)

    def test_missing_linsys2_env_still_runs_command(self):
        os.environ.pop("LINSYS2_ENV")
        self.assertEqual(pacman_auth(["true"]), 0)
        self.assertFalse(self.build_bin.exists())


class TestEnvLock(unittest.TestCase):
    def test_lock_excludes_second_build(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(common, "DATA_DIR", Path(td)):
                fd = acquire_env_lock("ucrt64")
                self.assertIsNotNone(fd)
                self.assertIsNone(acquire_env_lock("ucrt64"))
                other = acquire_env_lock("clang64")
                self.assertIsNotNone(other)
                os.close(other)
                os.close(fd)
                fd2 = acquire_env_lock("ucrt64")
                self.assertIsNotNone(fd2)
                os.close(fd2)


@unittest.skipUnless(os.path.isdir("/proc"), "requires a Linux /proc")
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


class TestRunMakepkgGate(unittest.TestCase):
    def test_errors_when_uninitialized(self):
        """Mirror of the run_pacman gate: without an initialized
        environment the build must not start."""
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(cli_makepkg, "MAKEPKG_BIN",
                                  Path(td) / "makepkg"), \
                mock.patch.object(cli_makepkg, "MAKEPKG_CONF",
                                  Path(td) / "makepkg.conf"), \
                mock.patch.object(cli_makepkg, "CONFIG_DIR",
                                  Path(td) / "config"), \
                mock.patch.object(common, "DATA_DIR", Path(td) / "data"), \
                mock.patch.object(cli_makepkg, "check_bwrap") as bwrap_mock, \
                mock.patch.object(cli_makepkg.subprocess, "run") as run_mock:
            (Path(td) / "makepkg").touch()
            (Path(td) / "makepkg.conf").touch()
            rc = cli_makepkg.run_makepkg("ucrt64", ["-s"])
        self.assertEqual(rc, 1)
        bwrap_mock.assert_not_called()
        run_mock.assert_not_called()

    def test_runs_when_config_exists(self):
        """Pairing for the gate test: with a config file present the gate
        must let the build proceed (it then stops at the bwrap check)."""
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(cli_makepkg, "MAKEPKG_BIN",
                                  Path(td) / "makepkg"), \
                mock.patch.object(cli_makepkg, "MAKEPKG_CONF",
                                  Path(td) / "makepkg.conf"), \
                mock.patch.object(cli_makepkg, "CONFIG_DIR",
                                  Path(td) / "config"), \
                mock.patch.object(common, "DATA_DIR", Path(td) / "data"), \
                mock.patch.object(cli_makepkg, "check_bwrap",
                                  return_value=False) as bwrap_mock, \
                mock.patch.object(cli_makepkg.subprocess, "run") as run_mock:
            (Path(td) / "makepkg").touch()
            (Path(td) / "makepkg.conf").touch()
            config = Path(td) / "config" / "ucrt64.conf"
            config.parent.mkdir(parents=True)
            config.touch()
            rc = cli_makepkg.run_makepkg("ucrt64", ["-s"])
        self.assertEqual(rc, 1)  # bwrap missing, but the gate let us through
        bwrap_mock.assert_called_once()
        run_mock.assert_not_called()

    def test_errors_when_wine_missing(self):
        """Like check_bwrap, a missing wine fails loudly before the
        build starts instead of crashing in wineboot."""
        with tempfile.TemporaryDirectory() as td, \
                mock.patch.object(cli_makepkg, "MAKEPKG_BIN",
                                  Path(td) / "makepkg"), \
                mock.patch.object(cli_makepkg, "MAKEPKG_CONF",
                                  Path(td) / "makepkg.conf"), \
                mock.patch.object(cli_makepkg, "CONFIG_DIR",
                                  Path(td) / "config"), \
                mock.patch.object(common, "DATA_DIR", Path(td) / "data"), \
                mock.patch.object(cli_makepkg.shutil, "which",
                                  return_value=None), \
                mock.patch.object(cli_makepkg, "check_bwrap",
                                  return_value=True), \
                mock.patch.object(cli_makepkg.subprocess, "run") as run_mock:
            (Path(td) / "makepkg").touch()
            (Path(td) / "makepkg.conf").touch()
            config = Path(td) / "config" / "ucrt64.conf"
            config.parent.mkdir(parents=True)
            config.touch()
            rc = cli_makepkg.run_makepkg("ucrt64", ["-s"])
        self.assertEqual(rc, 1)
        run_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
