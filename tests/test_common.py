import unittest

from linsys2.common import (
    DEFAULT_ENV,
    ENVIRONMENTS,
    get_bin_dir,
    get_env_dir,
    get_wineprefix,
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


if __name__ == "__main__":
    unittest.main()
