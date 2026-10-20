import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import subprocess

spec = importlib.util.spec_from_file_location(
    "deps", Path(__file__).resolve().parents[1] / "system_dependencies.py")
deps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deps)


class DependencyTests(unittest.TestCase):
    def test_new_packages_allowed(self):
        self.assertEqual(deps.validate_plan(
            "Inst bubblewrap (0.4.0 Ubuntu:focal [arm64])\n"
            "Conf bubblewrap (0.4.0 Ubuntu:focal [arm64])", {"libc6:arm64": "2.31"}),
            {"bubblewrap": "0.4.0"})

    def test_upgrade_rejected(self):
        with self.assertRaises(RuntimeError):
            deps.validate_plan("Inst libc6 [2.31] (2.32 Ubuntu [arm64])", {"libc6": "2.31"})

    def test_reinstall_rejected(self):
        with self.assertRaises(RuntimeError):
            deps.validate_plan("Inst libc6:arm64 (2.31 Ubuntu [arm64])", {"libc6": "2.31"})

    def test_removal_rejected(self):
        with self.assertRaises(RuntimeError):
            deps.validate_plan("Remv libc6 [2.31]", {"libc6": "2.31"})

    def test_reconfigure_rejected(self):
        with self.assertRaises(RuntimeError):
            deps.validate_plan("Conf libc6 (2.31 Ubuntu [arm64])", {"libc6": "2.31"})

    def test_unrecognized_inst_line_rejected(self):
        with self.assertRaises(RuntimeError):
            deps.validate_plan("Inst uncertain-format", {})

    def test_pins_keep_exact_version(self):
        text = deps.pins({"libc6:arm64": "2.31"})
        self.assertIn("Pin: version 2.31\nPin-Priority: 1001", text)
        self.assertIn("Pin: version *\nPin-Priority: -1", text)

    def test_nvidia_wrong_candidate_rejected(self):
        result = subprocess.CompletedProcess([], 0, "libnvinfer8 | 8.6.1 | repo\n")
        with patch.object(deps.subprocess, "run", return_value=result):
            with self.assertRaises(RuntimeError):
                deps.choose_version("libnvinfer8", "8.5.2")

    def test_nvidia_compatible_candidate_selected(self):
        result = subprocess.CompletedProcess([], 0,
            "libnvinfer8 | 8.6.1 | repo\nlibnvinfer8 | 8.5.2-1 | repo\n")
        with patch.object(deps.subprocess, "run", return_value=result):
            self.assertEqual(deps.choose_version("libnvinfer8", "8.5.2"), "8.5.2-1")

    def test_existing_missing_tool_package_not_reinstalled(self):
        with patch.object(deps, "installed", return_value={"bubblewrap": "0.4.0"}):
            with self.assertRaises(RuntimeError):
                deps.install_missing({"bubblewrap": None}, Path("must-not-be-created"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
