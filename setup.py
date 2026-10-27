"""Include the canonical release notes in installed wheels for offline display."""
from pathlib import Path
import shutil
from setuptools import setup
from setuptools.command.build_py import build_py


class BuildPy(build_py):
    def run(self):
        super().run()
        shutil.copyfile(Path(__file__).parent / 'CHANGELOG.md', Path(self.build_lib) / 'ft_tui/CHANGELOG.md')


setup(cmdclass={'build_py': BuildPy})
