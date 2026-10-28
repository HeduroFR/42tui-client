"""Open a configured project directory using the platform's file explorer."""
import os
from pathlib import Path
import shutil
import subprocess
import sys


def open_project_folder(path: str) -> None:
    directory = Path(path).expanduser().resolve()
    if not directory.is_dir():
        raise OSError("The configured project folder does not exist.")
    if sys.platform == "win32":
        os.startfile(str(directory))
        return
    command = "open" if sys.platform == "darwin" else "xdg-open"
    executable = shutil.which(command)
    if executable is None:
        raise OSError(f"{command} was not found on PATH.")
    try:
        result = subprocess.run(
            [executable, str(directory)], stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=15,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise OSError("The file explorer did not respond in time.") from error
    if result.returncode:
        raise OSError(result.stderr.strip() or f"{command} exited with status {result.returncode}.")
