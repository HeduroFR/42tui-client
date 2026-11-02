"""Integration installs stay confined, idempotent and reversible."""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ft_tui.features.editor_integrations.adapters.files import (
    MANIFEST,
    IntegrationFilesError,
    install_tree,
    read_manifest,
    remove_tree,
)


class FileTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name) / "base"
        self.base.mkdir()
        self.source = Path(self.directory.name) / "source"
        (self.source / "plugin").mkdir(parents=True)
        (self.source / "plugin" / "ft_tui.vim").write_text("plugin")
        self.target = self.base / "ft_tui"
        self.manifest = {"editor": "vim", "version": "0.1.0", "cli_path": "/bin/42tui"}

    def test_install_is_idempotent_and_refuses_foreign_directory(self):
        install_tree(self.source, self.target, self.manifest, base=self.base)
        install_tree(self.source, self.target, self.manifest, base=self.base)
        self.assertEqual(read_manifest(self.target)["version"], "0.1.0")

        (self.target / "keep.txt").write_text("user")
        with self.assertRaises(IntegrationFilesError) as error:
            install_tree(self.source, self.target, self.manifest, base=self.base)
        self.assertEqual(error.exception.code, "target_modified")
        self.assertEqual((self.target / "keep.txt").read_text(), "user")

        foreign = self.base / "foreign"
        foreign.mkdir()
        (foreign / "keep.txt").write_text("user")
        with self.assertRaises(IntegrationFilesError) as error:
            install_tree(self.source, foreign, self.manifest, base=self.base)
        self.assertEqual(error.exception.code, "target_foreign")
        self.assertEqual((foreign / "keep.txt").read_text(), "user")

    def test_remove_tree_only_removes_manifest_owned_tree(self):
        install_tree(self.source, self.target, self.manifest, base=self.base)
        self.assertTrue(remove_tree(self.target, self.base))
        self.assertFalse(self.target.exists())

        outside = Path(self.directory.name) / "outside"
        outside.mkdir()
        (outside / "file").write_text("keep")
        self.assertFalse(remove_tree(outside, self.base))
        self.assertTrue((outside / "file").exists())

    def test_install_writes_only_confined_extra_files(self):
        install_tree(
            self.source,
            self.target,
            self.manifest,
            base=self.base,
            extra={"ft_tui_config.vim": "let g:ft_tui_command = '/bin/42tui'"},
        )
        self.assertEqual((self.target / "ft_tui_config.vim").read_text(), "let g:ft_tui_command = '/bin/42tui'")
        with self.assertRaises(IntegrationFilesError) as error:
            install_tree(self.source, self.target, self.manifest, base=self.base, extra={"../escape": "no"})
        self.assertEqual(error.exception.code, "outside_base")
        self.assertFalse((self.base / "escape").exists())

    def test_repair_restores_missing_owned_files(self):
        install_tree(self.source, self.target, self.manifest, base=self.base)
        (self.target / "plugin" / "ft_tui.vim").unlink()
        install_tree(self.source, self.target, self.manifest, base=self.base)
        self.assertTrue((self.target / "plugin" / "ft_tui.vim").is_file())

    def test_remove_tree_removes_owned_files_and_leaves_user_files(self):
        install_tree(self.source, self.target, self.manifest, base=self.base)
        (self.target / "user.txt").write_text("keep")
        self.assertTrue(remove_tree(self.target, self.base))
        self.assertFalse((self.target / "plugin" / "ft_tui.vim").exists())
        self.assertFalse((self.target / MANIFEST).exists())
        self.assertEqual((self.target / "user.txt").read_text(), "keep")

        link = self.base / "link"
        link.symlink_to(self.target)
        self.assertFalse(remove_tree(link, self.base))
        self.assertTrue(self.target.exists())

    def test_manifest_lists_installed_files(self):
        install_tree(self.source, self.target, self.manifest, base=self.base)
        manifest = json.loads((self.target / MANIFEST).read_text())
        self.assertEqual(manifest["files"], ["plugin/ft_tui.vim"])


if __name__ == "__main__":
    unittest.main()
