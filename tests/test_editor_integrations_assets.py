"""Packaged editor assets must exist and stay installable from the wheel."""
import unittest
from importlib import resources
from pathlib import Path


class AssetTests(unittest.TestCase):
    def test_vim_plugin_is_packaged_and_sources_generated_config(self):
        root = Path(str(resources.files("ft_tui.integrations").joinpath("assets/vim")))
        text = (root / "plugin/ft_tui.vim").read_text()
        self.assertIn("ft_tui_config.vim", text)
        self.assertIn("g:loaded_ft_tui", text)

    def test_nvim_auto_plugin_respects_existing_setup(self):
        root = Path(str(resources.files("ft_tui.integrations").joinpath("assets/nvim")))
        auto = (root / "plugin/ft_tui_auto.lua").read_text()
        module = (root / "lua/ft_tui.lua").read_text()
        self.assertIn("_configured", auto)
        self.assertIn("M._configured = true", module)

    def test_packaged_assets_expose_version_and_path(self):
        from ft_tui.integrations import INTEGRATION_VERSION
        from ft_tui.features.editor_integrations.adapters.assets import PackagedAssets

        assets = PackagedAssets()
        self.assertEqual(assets.version("vim"), INTEGRATION_VERSION)
        self.assertTrue(assets.path("nvim").is_dir())

    def test_zed_asset_matches_manifest_version(self):
        from ft_tui.integrations import INTEGRATION_VERSION

        root = Path(str(resources.files("ft_tui.integrations").joinpath("assets/zed")))
        self.assertGreater((root / "extension.wasm").stat().st_size, 0)
        manifest = (root / "extension.toml").read_text()
        self.assertIn('id = "42tui-activity"', manifest)
        self.assertIn(f'version = "{INTEGRATION_VERSION}"', manifest)


if __name__ == "__main__":
    unittest.main()
