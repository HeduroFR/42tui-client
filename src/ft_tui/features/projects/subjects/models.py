"""Subject state and errors shared across provider and filesystem boundaries."""
class PDFCheckError(ValueError):
    """Raised when the selected subject file is missing or isn't a PDF."""


class SubjectPendingError(RuntimeError):
    """The authenticated Intra worker has not produced a current subject yet."""


def compare_subject_hashes(local_sha256: str, reference_sha256: str | None) -> str:
    """Return a simple status for a local hash and an optional provider reference."""
    if reference_sha256 is None:
        return "Reference unavailable"
    return "Up to date" if local_sha256.casefold() == reference_sha256.casefold() else "Hash differs"


class SubjectViewerUnavailable(OSError):
    """The configured system opener could not be found before launching."""
