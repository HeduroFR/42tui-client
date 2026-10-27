"""Opt-in real Textual/PTY/Docker smoke test; uses incomplete local C fixtures.

Run with a working local Docker engine: python tests/manual/tester_smoke.py ROOT
It builds/reuses Francinette, runs all three projects, and interrupts one run.
ROOT must be a new directory. No Docker context or global settings are changed.
"""

from __future__ import annotations

import asyncio
import errno
import json
import os
import platform
import pty
import select
import shutil
import struct
import subprocess
import sys
import termios
import time
from dataclasses import replace
from pathlib import Path


def child(root):
    from textual.worker import WorkerCancelled

    from ft_tui.db.database import make_session_factory
    from ft_tui.db.models import Project
    from ft_tui.services.tester_catalog import load_catalog
    from ft_tui.services.tester_docker import TesterDocker
    from ft_tui.services.user_settings import save_settings
    from ft_tui.ui.app import FortyTwoTuiApp
    from ft_tui.ui.project_testers import ProjectTesters, TesterAction

    root.mkdir(parents=True, exist_ok=False)
    fixtures = root / 'projects'
    shutil.copytree(Path(__file__).parent / 'fixtures', fixtures)
    factory = make_session_factory(f'sqlite:///{root / "ui.sqlite3"}')
    with factory() as session:
        save_settings(session, {'onboarding_completed': 'true', 'language': 'en'})
        for folder in fixtures.iterdir():
            slug = folder.name.split(' ')[0]
            session.add(Project(slug=slug, name=slug, local_path=str(folder)))
        session.commit()
    results = []

    class SmokeApp(FortyTwoTuiApp):
        async def on_mount(self):
            await super().on_mount()
            self.run_worker(self.smoke(), exit_on_error=True)

        async def inspected(self, widget):
            while True:
                worker = widget._inspection_worker
                try:
                    await worker.wait()
                except WorkerCancelled:
                    continue
                if worker is widget._inspection_worker:
                    return

        async def operate(self, widget, action, tester, *, click=False):
            started = time.monotonic()
            if click:
                button = widget.query_one(TesterAction)
                assert not button.disabled
                button.press()
                button.press()  # A queued double click must start one operation.
                await asyncio.sleep(.1)
            else:
                widget._start(action, tester)
            while widget._operating:
                await asyncio.sleep(.1)
            await self.inspected(widget)
            message = widget._messages[tester.id]
            results.append({'action': action, 'project': widget.project.slug, 'message': message,
                            'seconds': round(time.monotonic() - started, 3)})
            assert 'completed' in message or 'interrupted' in message, message

        async def smoke(self):
            widget = self.query_one(ProjectTesters)
            tester = self.tester_catalog.testers[0]
            projects = {project.slug: project for project in self.projects.values()}
            self._show_project(projects['libft'])
            await self.inspected(widget)
            self.query_one('#show-project-testers').press()
            await asyncio.sleep(.1)
            assert self.focused is widget.query_one(TesterAction)
            await self.operate(widget, 'install', tester)
            image_before = self.tester_docker._capture([
                self.tester_docker.docker(), 'image', 'inspect', '--format', '{{.Id}}', self.tester_docker.image(tester)
            ]).stdout
            for slug in ('libft', 'ft_printf', 'get_next_line'):
                self._show_project(projects[slug])
                await self.inspected(widget)
                self.action_project_testers()
                await asyncio.sleep(.1)  # Textual applies focus on the next message-pump turn.
                assert self.focused is widget.query_one(TesterAction)
                await self.operate(widget, 'run', tester, click=True)
                transcript = max((root / 'testers/logs').glob('*-run-*.log'), key=lambda file: file.stat().st_mtime)
                output = transcript.read_text(errors='replace')
                assert 'Summary' in output, transcript
                assert 'unhandled dwarf2' not in output, transcript
                assert 'Valgrind: debuginfo reader' not in output, transcript
            interrupted = replace(tester, command=(
                'python3', '-c', "import time; print('42TUI_INTERRUPT_READY', flush=True); time.sleep(60)"
            ))
            await self.operate(widget, 'run', interrupted)
            assert 'interrupted' in results[-1]['message']
            assert not self.tester_docker.busy
            image_after = self.tester_docker._capture([
                self.tester_docker.docker(), 'image', 'inspect', '--format', '{{.Id}}', self.tester_docker.image(tester)
            ]).stdout
            assert image_before == image_after
            for file in fixtures.rglob('*'):
                assert file.stat().st_uid == os.getuid(), str(file)
            (root / 'result.json').write_text(json.dumps({
                'system': platform.platform(), 'python': platform.machine(),
                'tester_architecture': self.tester_docker.architecture(tester),
                'image': image_after.strip(), 'operations': results, 'ownership_verified': True,
            }, indent=2))
            self.exit()

    app = SmokeApp(factory, None)
    app.tester_catalog = load_catalog(root / 'absent.toml')
    app.tester_docker = TesterDocker(root / 'testers')
    app.run()
    factory.kw['bind'].dispose()


def drive(root):
    master, slave = pty.openpty()
    import fcntl
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 65, 160, 0, 0))
    process = subprocess.Popen([sys.executable, __file__, str(root), '--child'],
                               stdin=slave, stdout=slave, stderr=slave,
                               env={**os.environ, 'TERM': 'xterm-256color'})
    os.close(slave)
    pending = b''
    prompts = 0
    interrupted = False
    try:
        deadline = time.monotonic() + 1800
        with root.with_suffix('.pty.log').open('wb') as log:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([master], [], [], .2)
                if ready:
                    try:
                        block = os.read(master, 65536)
                    except OSError as error:
                        if error.errno != errno.EIO:
                            raise
                        break
                    if not block:
                        break
                    log.write(block)
                    log.flush()
                    pending += block
                    marker = b'Press any key to return to 42TUI.'
                    while marker in pending:
                        _, pending = pending.split(marker, 1)
                        time.sleep(.1)
                        os.write(master, b'x')
                        prompts += 1
                    if not interrupted and b'42TUI_INTERRUPT_READY\r\n' in pending:
                        os.write(master, b'\x03')
                        interrupted = True
                    pending = pending[-65536:]
                if process.poll() is not None:
                    break
        assert process.wait(timeout=3) == 0, root.with_suffix('.pty.log')
        result = json.loads((root / 'result.json').read_text())
        assert prompts == 5, prompts
        assert len(list((root / 'testers/logs').glob('*.log'))) == 5
        print(json.dumps(result, indent=2))
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        os.close(master)


if __name__ == '__main__':
    destination = Path(sys.argv[1]).resolve()
    if '--child' in sys.argv:
        child(destination)
    else:
        drive(destination)
