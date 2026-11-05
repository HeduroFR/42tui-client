"""Managed Neovim loading, with isolated startup and no heartbeat subprocesses."""
import json
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ft_tui.features.editor_integrations.adapters.assets import PackagedAssets
from ft_tui.features.editor_integrations.adapters.editors import EditorCommands
from ft_tui.features.editor_integrations.adapters.files import (
    IntegrationFilesError, install_tree, read_manifest, remove_tree,
)


def lua_string(value):
    return json.dumps(str(value), ensure_ascii=False)


class NeovimTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="42tui nvim é ")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.environ = {
            "HOME": str(self.root),
            "XDG_CONFIG_HOME": str(self.root / "config space"),
            "XDG_DATA_HOME": str(self.root / "data space"),
            "XDG_STATE_HOME": str(self.root / "state"),
            "XDG_CACHE_HOME": str(self.root / "cache"),
            "XDG_CONFIG_DIRS": str(self.root / "system config"),
            "XDG_DATA_DIRS": str(self.root / "system data"),
            "NVIM_APPNAME": "test app/nvim",
        }
        self.commands = EditorCommands(
            home=self.root, environ=self.environ, which=lambda _: None,
            run=lambda *args, **kwargs: self.fail("Installation must not execute Neovim"),
        )
        self.assets = PackagedAssets().path("nvim")
        self.cli = str(self.root / "bin space/42tui")
        self.target = self.commands.target("nvim")
        self.loader = self.commands.nvim_loader_target()

    def install(self):
        return self.commands.install("nvim", self.cli, self.assets)

    def test_install_repeat_upgrade_and_uninstall_preserve_configuration(self):
        config = Path(self.environ["XDG_CONFIG_HOME"]) / self.environ["NVIM_APPNAME"]
        config.mkdir(parents=True)
        init = config / "init.lua"
        init.write_text("-- personal configuration\n")
        other = config / "after/plugin/user.lua"
        other.parent.mkdir(parents=True)
        other.write_text("-- user plugin\n")
        self.assertEqual(self.install(), self.target)
        self.assertEqual(
            self.target, Path(self.environ["XDG_DATA_HOME"]) / "test app/nvim/site/pack/42tui/start/ft_tui",
        )
        self.assertEqual(self.loader, config / "after/plugin/42tui")
        before = (self.loader / "ft_tui_loader.lua").read_bytes()
        self.install()
        self.assertEqual(before, (self.loader / "ft_tui_loader.lua").read_bytes())
        self.cli += "-new"
        self.install()
        self.assertEqual(read_manifest(self.target)["cli_path"], self.cli)
        self.assertTrue(self.commands.nvim_loader_current())
        (self.loader / "user.txt").write_text("keep")
        (self.target / "user.txt").write_text("keep data")
        self.assertTrue(self.commands.uninstall("nvim"))
        self.assertFalse(self.target.exists())
        self.assertFalse(self.loader.exists())
        self.assertEqual((self.loader.with_name("42tui-unrelated") / "user.txt").read_text(), "keep")
        self.assertEqual((self.target.with_name("ft_tui-unrelated") / "user.txt").read_text(), "keep data")
        self.assertEqual(init.read_text(), "-- personal configuration\n")
        self.assertEqual(other.read_text(), "-- user plugin\n")

    def test_default_directories_and_appname(self):
        commands = EditorCommands(home=self.root, environ={})
        self.assertEqual(commands.target("nvim"), self.root / ".local/share/nvim/site/pack/42tui/start/ft_tui")
        self.assertEqual(commands.nvim_loader_target(), self.root / ".config/nvim/after/plugin/42tui")

    def test_migrate_native_install_using_ownership_manifest(self):
        install_tree(self.assets, self.target, {
            "editor": "nvim", "version": "0.1.0", "cli_path": "/old/42tui",
        }, base=self.target.parent, extra={"lua/ft_tui_config.lua": "return {}\n"})
        self.assertFalse(self.commands.nvim_loader_current())
        self.install()
        self.assertTrue(self.commands.nvim_loader_current())
        self.assertEqual(read_manifest(self.target)["cli_path"], self.cli)
        self.assertTrue(self.commands.uninstall("nvim"))

    def test_foreign_and_symlink_targets_are_never_overwritten(self):
        for path in (self.target, self.loader):
            with self.subTest(path=path):
                path.mkdir(parents=True)
                user = path / "user.lua"
                user.write_text("keep")
                with self.assertRaises(IntegrationFilesError):
                    self.install()
                self.assertEqual(user.read_text(), "keep")
                shutil.rmtree(path)
                outside = self.root / "outside"
                outside.mkdir(exist_ok=True)
                path.symlink_to(outside, target_is_directory=True)
                with self.assertRaises(IntegrationFilesError):
                    self.install()
                self.assertFalse(self.commands.uninstall("nvim"))
                self.assertTrue(outside.is_dir())
                path.unlink()

    def test_failed_loader_update_preserves_old_loader_and_can_be_retried(self):
        self.install()
        before = (self.loader / "ft_tui_loader.lua").read_bytes()
        replace = os.replace

        def fail_loader(source, destination):
            if Path(destination) == self.loader and ".tmp-" in Path(source).name:
                raise OSError("test write failure")
            return replace(source, destination)

        self.cli += "-new"
        with patch("ft_tui.features.editor_integrations.adapters.files.os.replace", side_effect=fail_loader):
            with self.assertRaises(IntegrationFilesError):
                self.install()
        self.assertEqual(before, (self.loader / "ft_tui_loader.lua").read_bytes())
        self.assertFalse(self.commands.nvim_loader_current())
        self.install()
        self.assertTrue(self.commands.nvim_loader_current())

    def test_failed_loader_removal_keeps_the_module_and_is_recoverable(self):
        self.install()
        with patch("ft_tui.features.editor_integrations.adapters.editors.remove_tree", return_value=False):
            self.assertFalse(self.commands.uninstall("nvim"))
        self.assertTrue((self.target / "lua/ft_tui.lua").is_file())
        self.assertTrue(self.commands.uninstall("nvim"))

    def test_failed_package_removal_leaves_no_broken_startup_entry_point(self):
        self.install()

        def fail_package(target, base):
            return False if target == self.target else remove_tree(target, base)

        with patch("ft_tui.features.editor_integrations.adapters.editors.remove_tree", side_effect=fail_package):
            self.assertFalse(self.commands.uninstall("nvim"))
        self.assertFalse(self.loader.exists())
        self.assertFalse((self.target / "plugin/ft_tui_auto.lua").exists())
        self.assertIsNotNone(read_manifest(self.target))
        self.assertTrue(self.commands.uninstall("nvim"))

    def test_orphan_loader_can_be_repaired_or_uninstalled(self):
        self.install()
        self.assertTrue(remove_tree(self.target, self.target.parent))
        self.assertEqual(self.commands.installed_path("nvim"), self.loader)
        self.assertIsNotNone(self.commands.manifest("nvim"))
        self.assertFalse(self.commands.nvim_loader_current())
        self.assertTrue(self.commands.uninstall("nvim"))
        self.assertFalse(self.loader.exists())

    @unittest.skipUnless(shutil.which("nvim"), "Neovim is not installed")
    def test_standard_startup(self):
        self.check_startup()

    @unittest.skipUnless(shutil.which("nvim"), "Neovim is not installed")
    def test_standard_startup_with_native_packages_disabled(self):
        self.check_startup(without_packages=True)

    @unittest.skipUnless(shutil.which("nvim"), "Neovim is not installed")
    def test_existing_setup_overrides_are_preserved(self):
        self.check_startup(custom_setup=True)

    @unittest.skipUnless(shutil.which("nvim") and os.environ.get("FT_TUI_TEST_LAZY_NVIM"),
                         "Set FT_TUI_TEST_LAZY_NVIM to an isolated lazy.nvim checkout")
    def test_lazy_startup(self):
        self.check_startup(lazy=Path(os.environ["FT_TUI_TEST_LAZY_NVIM"]))
        self.check_startup(lazy=Path(os.environ["FT_TUI_TEST_LAZY_NVIM"]), custom_setup=True)

    def check_startup(self, *, lazy=None, custom_setup=False, without_packages=False):
        self.install()
        self.install()
        config = self.loader.parents[2]
        init = config / "init.lua"
        setup = 'require("ft_tui").setup({ command = "custom cli", min_interval = 45 })\n'
        if lazy:
            self.assertTrue((lazy / "lua/lazy/init.lua").is_file())
            init.write_text(
                (setup if custom_setup else "") + f"vim.opt.rtp:prepend({lua_string(lazy)})\n"
                'require("lazy").setup({spec = {}, install = {missing = false}, '
                'checker = {enabled = false}, change_detection = {enabled = false}})\n'
            )
        elif custom_setup:
            init.write_text(setup)
        elif without_packages:
            init.write_text('vim.opt.packpath = {vim.env.VIMRUNTIME}\n')
        else:
            init.write_text("-- isolated standard configuration\n")
        stub = self.root / "stub.lua"
        stub.write_text('''
_G.jobs, _G.timers, _G.group_count = {}, {}, 0
vim.fn.jobstart = function(argv) table.insert(jobs, argv); return 1 end
vim.defer_fn = function(callback) table.insert(timers, callback) end
local create = vim.api.nvim_create_augroup
vim.api.nvim_create_augroup = function(name, opts)
  if name == "FtTuiHeartbeat" then group_count = group_count + 1 end
  return create(name, opts)
end
''')
        assertions = self.root / "assert.lua"
        assertions.write_text(f'''
local module = require("ft_tui")
assert(module._configured, "integration did not initialize")
assert(module.command == {lua_string("custom cli" if custom_setup else self.cli)})
assert(module.min_interval == {45 if custom_setup else 30})
dofile({lua_string(self.loader / "ft_tui_loader.lua")})
dofile({lua_string(self.loader / "ft_tui_loader.lua")})
dofile({lua_string(self.target / "plugin/ft_tui_auto.lua")})
assert(group_count == 1, "setup ran more than once")
assert(#vim.api.nvim_get_autocmds({{group = "FtTuiHeartbeat"}}) == 4)
vim.cmd("edit " .. vim.fn.fnameescape({lua_string(self.root / "file space.lua")}))
assert(#jobs == 1, "expected one initial heartbeat")
vim.api.nvim_exec_autocmds("TextChanged", {{}})
vim.api.nvim_exec_autocmds("TextChangedI", {{}})
vim.api.nvim_exec_autocmds("BufWritePost", {{}})
assert(#timers == 1, "expected one pending heartbeat timer")
timers[1]()
assert(#jobs == 2 and jobs[2][#jobs[2]] == "--write")
assert(jobs[1][1] == module.command and jobs[1][2] == "heartbeat")
assert(jobs[1][4] == {lua_string(self.root / "file space.lua")})
''')
        command = [
            shutil.which("nvim"), "--headless", "-i", "NONE",
            "--cmd", f"lua dofile({lua_string(stub)})",
            "-c", f"lua local ok, err = pcall(dofile, {lua_string(assertions)}); "
                  "if not ok then print(err); vim.cmd('cquit 1') end",
            "-c", "qa!",
        ]
        environment = {
            key: value for key, value in os.environ.items()
            if key in ("PATH", "TMPDIR", "LANG", "LC_ALL", "TERM")
        }
        result = subprocess.run(command, env={**environment, **self.environ}, cwd=self.root,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("Error", result.stderr)
        if not custom_setup:
            self.assertTrue(self.commands.uninstall("nvim"))
            assertions.write_text('assert(not package.loaded["ft_tui"], "integration survived uninstall")\n')
            result = subprocess.run(command, env={**environment, **self.environ}, cwd=self.root,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("Error", result.stderr)


if __name__ == "__main__":
    unittest.main()
