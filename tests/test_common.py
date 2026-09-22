import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import linsys2.common as common
from linsys2.common import (
    DEFAULT_ENV,
    ENVIRONMENTS,
    get_bin_dir,
    get_env_dir,
    get_wineprefix,
    resolve_wineprefix,
)


class TestEnvironments(unittest.TestCase):
    def test_required_fields(self):
        for name, cfg in ENVIRONMENTS.items():
            for key in ("prefix", "install_prefix", "mirror_path",
                        "msystem", "chost"):
                self.assertIn(key, cfg, f"{name}.{key}")

    def test_default_env_exists(self):
        self.assertIn(DEFAULT_ENV, ENVIRONMENTS)

    def test_paths(self):
        self.assertEqual(get_env_dir("ucrt64").name, "ucrt64")
        self.assertEqual(get_bin_dir("ucrt64").name, "bin")
        self.assertIn("ucrt64", str(get_bin_dir("ucrt64")))
        self.assertEqual(get_wineprefix("ucrt64").name, "wine")


class TestResolveWineprefix(unittest.TestCase):
    def test_explicit_arg_wins(self):
        self.assertEqual(resolve_wineprefix("ucrt64", "/wp/x"), Path("/wp/x"))

    def test_wine_config_and_default(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(common, "DATA_DIR", Path(td)):
                self.assertEqual(resolve_wineprefix("ucrt64"),
                                 Path(td) / "ucrt64" / "wine")
                cfg = Path(td) / "ucrt64" / "wine.config"
                cfg.parent.mkdir(parents=True)
                cfg.write_text("WINEPREFIX=/wp/from-config\n")
                self.assertEqual(resolve_wineprefix("ucrt64"),
                                 Path("/wp/from-config"))

    def test_prefer_user_from_env_var(self):
        with mock.patch.dict(os.environ, {"WINEPREFIX": "/wp/env"}):
            self.assertEqual(resolve_wineprefix("ucrt64", prefer_user=True),
                             Path("/wp/env"))

    def test_prefer_user_default_wine(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            with mock.patch.dict(os.environ, clear=True), \
                    mock.patch.object(Path, "home", return_value=home), \
                    mock.patch.object(common, "DATA_DIR", Path(td) / "data"):
                self.assertEqual(resolve_wineprefix("ucrt64", prefer_user=True),
                                 home / ".wine")

    def test_prefer_user_wine_config_override(self):
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / ".wine").mkdir()
            data_dir = Path(td) / "data"
            cfg = data_dir / "ucrt64" / "wine.config"
            cfg.parent.mkdir(parents=True)
            cfg.write_text("WINEPREFIX=/wp/from-config\n")
            with mock.patch.dict(os.environ, clear=True), \
                    mock.patch.object(Path, "home", return_value=home), \
                    mock.patch.object(common, "DATA_DIR", data_dir):
                self.assertEqual(resolve_wineprefix("ucrt64", prefer_user=True),
                                 Path("/wp/from-config"))


if __name__ == "__main__":
    unittest.main()
