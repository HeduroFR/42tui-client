"""Exercise a real terminal: argument boundaries, transcripts and Ctrl+C cleanup."""

import errno
import json
import os
import pty
import select
import subprocess
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


@unittest.skipUnless(sys.platform in {"linux", "darwin"}, "Unix PTY required")
class TesterTerminalTests(unittest.TestCase):
    def run_in_terminal(self, interrupt=False):
        with TemporaryDirectory(prefix="terminal space ") as directory:
            root = Path(directory)
            child = (
                "import sys,time; print('CHILD_READY', flush=True); time.sleep(30)"
                if interrupt else "import os,sys; print(repr(sys.argv[1:]), flush=True); print(os.environ['42TUI_TERMINAL_TEST'], flush=True)"
            )
            arguments = [sys.executable, "-c", child, "argument with spaces", "$(touch never)"]
            source = f'''
import json, os, sys, termios
from pathlib import Path
from ft_tui.services.tester_terminal import TerminalSession
root = Path({str(root)!r})
before = termios.tcgetattr(0)
interrupted = False
with (root / 'output.log').open('wb') as log:
    try:
        TerminalSession(log).run({arguments!r}, cwd=root, env={{**os.environ, "42TUI_TERMINAL_TEST": "frozen environment"}})
    except KeyboardInterrupt:
        interrupted = True
after = termios.tcgetattr(0)
# macOS sets PENDIN when restoring canonical mode; the kernel clears it
# after processing pending input. It is not a changed terminal setting.
before[3] &= ~getattr(termios, 'PENDIN', 0)
after[3] &= ~getattr(termios, 'PENDIN', 0)
(root / 'result.json').write_text(json.dumps({{'restored': before == after, 'interrupted': interrupted, 'before': repr(before), 'after': repr(after)}}))
print('PARENT_DONE', flush=True)
'''
            master, slave = pty.openpty()
            process = subprocess.Popen([sys.executable, "-c", source], stdin=slave, stdout=slave, stderr=slave,
                                       env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")})
            os.close(slave)
            output = b""
            sent = False
            try:
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    ready, _, _ = select.select([master], [], [], 0.1)
                    if ready:
                        try:
                            block = os.read(master, 65536)
                        except OSError as error:
                            if error.errno != errno.EIO:
                                raise
                            break
                        if not block:
                            break
                        output += block
                        if interrupt and not sent and b"CHILD_READY\r\n" in output:
                            os.write(master, b"\x03")
                            sent = True
                    if process.poll() is not None:
                        break
                self.assertEqual(process.wait(timeout=1), 0, output.decode(errors="replace"))
                result = json.loads((root / "result.json").read_text())
                self.assertTrue(result["restored"], result)
                self.assertEqual(result["interrupted"], interrupt)
                transcript = (root / "output.log").read_text()
                self.assertIn("CHILD_READY" if interrupt else "['argument with spaces', '$(touch never)']", transcript)
                if not interrupt:
                    self.assertIn("frozen environment", transcript)
                self.assertFalse((root / "never").exists())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                os.close(master)

    def test_live_transcript_preserves_arguments_and_restores_terminal(self):
        self.run_in_terminal()

    def test_ctrl_c_interrupts_child_and_restores_terminal(self):
        self.run_in_terminal(interrupt=True)
