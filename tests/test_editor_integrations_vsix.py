"""The VS Code extension package is built locally without Node tooling."""
import json
import unittest
import zipfile
from importlib import resources
from pathlib import Path
from tempfile import TemporaryDirectory

from ft_tui.features.editor_integrations.adapters.vsix import build_vsix


def package_dir() -> Path:
    return Path(str(resources.files("ft_tui.integrations").joinpath("assets/vscode")))


class VsCodePackageTests(unittest.TestCase):
    def test_vsix_contains_extension_and_injected_cli_path(self):
        with TemporaryDirectory() as tmp:
            output = build_vsix(
                Path(tmp) / "42tui-activity.vsix", package_dir(), "0.1.0", "/opt/bin/42tui"
            )
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                self.assertIn("extension/package.json", names)
                self.assertIn("extension/extension.js", names)
                self.assertIn("extension.vsixmanifest", names)
                self.assertEqual(
                    archive.read("extension/42tui-path.txt").decode(), "/opt/bin/42tui"
                )
                manifest = archive.read("extension.vsixmanifest").decode()
                self.assertIn('Publisher="42tui"', manifest)
                self.assertIn('Version="0.1.0"', manifest)

    def test_package_manifest_is_plain_javascript_and_versioned(self):
        from ft_tui.integrations import INTEGRATION_VERSION

        package = json.loads((package_dir() / "package.json").read_text())
        self.assertEqual(package["version"], INTEGRATION_VERSION)
        self.assertEqual(package["main"], "./extension.js")
        self.assertNotIn("devDependencies", package)
        properties = package["contributes"]["configuration"]["properties"]
        self.assertEqual(properties["42tui.cliPath"]["default"], "")


if __name__ == "__main__":
    unittest.main()
