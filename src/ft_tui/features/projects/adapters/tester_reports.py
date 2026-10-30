"""Read explicitly configured reports without following project-controlled links."""
import json
import os
from contextlib import contextmanager
from pathlib import PurePosixPath
import stat

from ft_tui.features.projects.tester_results import TestSummary

MAX_REPORT_BYTES = 65536


@contextmanager
def _parent(project, name):
    path = PurePosixPath(name)
    if (path.is_absolute() or not path.parts or "\x00" in name
            or any(part in {"..", ".git"} for part in path.parts)):
        raise ValueError("Report must be a file inside the project copy")
    descriptor = os.open(project, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor, path.name
    finally:
        os.close(descriptor)


def clear_report(project, name):
    """Remove an inherited report only in the copy; missing parents are allowed."""
    try:
        with _parent(project, name) as (parent, filename):
            os.unlink(filename, dir_fd=parent)
    except FileNotFoundError:
        pass


def read_report(project, name):
    with _parent(project, name) as (parent, filename):
        descriptor = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(descriptor, "rb") as report:
            info = os.fstat(report.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_REPORT_BYTES:
                raise ValueError("Report must be a regular file of at most 64 KiB")
            content = report.read(MAX_REPORT_BYTES + 1)
            if len(content) > MAX_REPORT_BYTES:
                raise ValueError("Report exceeds 64 KiB")
    return TestSummary.from_report(json.loads(content.decode("utf-8")))
