"""Local PDF fingerprinting for checking project subject revisions."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
import os
import platform
import shutil
import subprocess
from ..models import PDFCheckError, compare_subject_hashes,SubjectViewerUnavailable


def sha256_pdf(path: str | Path) -> str:
    """Calculate a PDF's SHA-256 digest without loading the whole file into memory."""
    pdf_path = Path(path).expanduser().resolve(strict=False)
    if pdf_path.suffix.casefold() != ".pdf":
        raise PDFCheckError("Choose a file with the .pdf extension.")
    if not pdf_path.is_file():
        raise PDFCheckError("The selected PDF does not exist or is not a regular file.")

    digest = sha256()
    try:
        with pdf_path.open("rb") as pdf_file:
            if pdf_file.read(5) != b"%PDF-":
                raise PDFCheckError("The selected file does not have a valid PDF header.")
            pdf_file.seek(0)
            for chunk in iter(lambda: pdf_file.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise PDFCheckError(f"Could not read the PDF: {error}") from error
    return digest.hexdigest()


def ensure_pdf_gitignore(project_root: str | Path) -> bool:
    """Ensure project-root PDFs are ignored; return whether .gitignore changed."""
    root = Path(project_root).expanduser()
    if not root.is_dir():
        return False
    gitignore = root / ".gitignore"
    if gitignore.is_symlink():
        raise OSError("Refusing to modify a symlinked .gitignore.")
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    if any(line.strip() == "*.pdf" for line in existing.splitlines()):
        return False
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    content = f"{existing}{prefix}# 42TUI: keep downloaded project subjects out of Git\n*.pdf\n"
    gitignore.write_text(content, encoding="utf-8")
    return True


def synchronize_subject_pdf(slug, destination: Path, downloader, reference: str | None, *, current=lambda: True) -> str | None:
    """Validate a staged download before atomically installing an upstream revision."""
    if destination.is_symlink():
        raise PDFCheckError("Refusing to read or replace a symlinked subject.pdf.")
    try:
        digest = sha256_pdf(destination) if destination.is_file() else None
    except PDFCheckError:
        if reference is None:
            raise
        digest = None
    if callable(downloader) and (digest is None or reference is not None and digest != reference):
        with NamedTemporaryFile(suffix=".pdf", dir=destination.parent, delete=False) as staged:
            temporary = Path(staged.name)
        try:
            if not current():return digest
            if not downloader(slug, temporary):
                if reference is not None:
                    raise PDFCheckError("The provider could not download the current subject PDF.")
                return digest
            downloaded_digest = sha256_pdf(temporary)
            if reference is not None and downloaded_digest != reference:
                raise PDFCheckError("Downloaded subject PDF does not match the current reference.")
            if destination.is_symlink():
                raise PDFCheckError("Refusing to replace a symlinked subject.pdf.")
            if not current():return digest
            temporary.replace(destination)
            digest = downloaded_digest
        finally:
            temporary.unlink(missing_ok=True)
    return digest


class SubjectFiles:
    def root(self,path):
        if not path:return None
        root=Path(path).expanduser().resolve(strict=False)
        return root if root.is_dir() else None

    def subject(self,root):return root/'subject.pdf'
    def regular(self,path):return path is not None and path.is_file()
    def symlink(self,path):return path.is_symlink()
    def ensure_ignore(self,root):return ensure_pdf_gitignore(root)
    def synchronize(self,*args,**kwargs):return synchronize_subject_pdf(*args,**kwargs)

    def inspect(self,local_path,subject_path):
        path=Path(subject_path).expanduser() if subject_path else None
        if path is None and local_path:path=Path(local_path).expanduser()/'subject.pdf'
        folder=bool(local_path and Path(local_path).expanduser().is_dir())
        return path,folder,self.regular(path)

    def viewer(self,name):return shutil.which(name)

    def run_tdf(self,executable,path):
        return subprocess.run((executable,str(path)),cwd=path.parent,check=False)

    def open_system(self,path):
        system=platform.system()
        if system=='Windows':
            os.startfile(str(path))
        else:
            opener='open' if system=='Darwin' else 'xdg-open'
            executable=shutil.which(opener)
            if executable is None:raise SubjectViewerUnavailable(f'{opener} was not found on PATH.')
            subprocess.Popen((executable,str(path)),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL,start_new_session=True)
