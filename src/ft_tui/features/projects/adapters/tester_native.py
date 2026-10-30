"""Pinned native testers in disposable projects and private Python environments."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from ft_tui.features.projects.adapters.tester_docker import TesterError, Host
from ft_tui.features.projects.adapters.tester_reports import clear_report, read_report
from ft_tui.features.projects.tester_results import TesterRunResult


def run_native(tester, project_path, terminal):
    project = Path(project_path).expanduser().resolve() if project_path else None
    if project is None or not project.is_dir():
        raise TesterError('Configure an existing local project folder to run tests.')
    if sys.platform not in tester.platforms or Host.detect().architecture not in tester.architectures:
        raise TesterError('This tester is unavailable on this platform.')
    git = shutil.which('git')
    if not git:
        raise TesterError('Git is required for native tester setup.')
    with tempfile.TemporaryDirectory(prefix='42tui-native-') as directory:
        root = Path(directory).resolve()
        copy, source, environment = root / 'project', root / 'source', root / 'venv'
        terminal.write('Preparing a disposable project copy…')
        shutil.copytree(project, copy, symlinks=True, ignore=shutil.ignore_patterns('.git'))
        # Native code can follow host paths: never retain links back into the checkout.
        try:
            for path in copy.rglob('*'):
                if path.is_symlink() and (os.path.isabs(os.readlink(path)) or not path.resolve().is_relative_to(copy)):
                    raise TesterError('Native tester copies cannot contain links outside the copy.')
        except (OSError, RuntimeError) as error:
            raise TesterError('Native tester copies cannot contain links outside the copy.') from error
        terminal.write('Preparing the native tester…')
        terminal.run([git, 'init', str(source)])
        terminal.run([git, '-C', str(source), 'fetch', '--depth=1', '--no-tags', tester.repository, tester.ref])
        terminal.run([git, '-C', str(source), 'checkout', '--detach', tester.ref])
        terminal.run([sys.executable, '-m', 'venv', '--without-pip', str(environment)])
        python = environment / 'bin/python'
        context = (source / tester.context).resolve()
        if not context.is_relative_to(source) or not context.is_dir():
            raise TesterError('Native tester context must stay inside the repository.')
        def command(args):
            return [arg.replace('{source}', str(context)).replace('{project}', str(copy))
                    .replace('{python}', str(python)) for arg in args]
        env = {**os.environ, 'VIRTUAL_ENV': str(environment), 'PATH': str(environment / 'bin') + os.pathsep + os.environ.get('PATH', ''),
               'PYTHONNOUSERSITE': '1'}
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
        for prepare in tester.prepare:
            terminal.run(command(prepare), cwd=copy, env=env)
        if tester.result_file:
            clear_report(copy, tester.result_file)
        terminal.write('Running the tester…')
        try:
            terminal.run(command(tester.command), cwd=copy, env=env)
            code = 0
        except subprocess.CalledProcessError as error:
            code = error.returncode
        if tester.result_file:
            try:
                return TesterRunResult(code, read_report(copy, tester.result_file))
            except (OSError, ValueError, TypeError, KeyError, RecursionError):
                return TesterRunResult(code, unreadable=True)
        return TesterRunResult(code)
