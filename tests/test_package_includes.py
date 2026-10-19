"""Regression for package-relative includes, including the remote-package path."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(importlib.util.find_spec("esphome"), "ESPHome is required for package code generation")
class PackageIncludesTests(unittest.TestCase):
    def test_local_and_remote_package_headers(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            vendor = base / "vendor"
            (vendor / "src").mkdir(parents=True)
            shutil.copy(ROOT / "package.yaml", vendor / "package.yaml")
            for name in ("ble_values.h", "thermatik_protocol.h", "thermatik_writer.h"):
                shutil.copy(ROOT / "src" / name, vendor / "src" / name)
            for args in (["init", "-q"], ["add", "package.yaml", "src"],
                         ["-c", "user.name=Validation", "-c", "user.email=validation@example.invalid",
                          "commit", "-q", "-m", "Package fixture"]):
                subprocess.run(["git", *args], cwd=vendor, check=True, capture_output=True)
            env = dict(os.environ, GIT_CONFIG_COUNT="1", GIT_ALLOW_PROTOCOL="file",
                       GIT_CONFIG_KEY_0=f"url.{vendor.as_uri()}.insteadOf",
                       GIT_CONFIG_VALUE_0="https://package-fixture.invalid/thermatik.git")
            common = """esphome:
  name: {name}
esp32:
  board: esp32dev
  framework:
    type: esp-idf
substitutions:
  mac_address: 'AA:BB:CC:DD:EE:FF'
packages:
"""
            for kind in ("local", "remote"):
                with self.subTest(kind=kind):
                    user = base / kind
                    user.mkdir()
                    name = "thermatik-include-" + kind
                    package = "  thermatik: !include ../vendor/package.yaml\n" if kind == "local" else """  thermatik:
    url: https://package-fixture.invalid/thermatik.git
    files:
      - path: package.yaml
"""
                    config = user / "device.yaml"
                    config.write_text(common.format(name=name) + package)
                    result = subprocess.run([sys.executable, "-m", "esphome", "compile", "--only-generate", str(config)],
                                            env=env, text=True, capture_output=True)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    src = user / ".esphome/build" / name / "src"
                    for header in ("ble_values.h", "thermatik_protocol.h", "thermatik_writer.h"):
                        self.assertEqual((src / header).read_bytes(), (vendor / "src" / header).read_bytes())
                        self.assertIn('#include "' + header + '"', (src / "main.cpp").read_text())
                    self.assertNotIn("github.com/vk496/esphome-thermatik", (src / "CMakeLists.txt").read_text())
