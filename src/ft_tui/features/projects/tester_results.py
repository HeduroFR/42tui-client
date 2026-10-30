"""Portable tester observations; process completion is not test validation."""
from dataclasses import dataclass


@dataclass(frozen=True)
class TestSummary:
    total: int
    passed: int
    failed: int
    skipped: int
    errors: int
    incomplete: bool = False

    def __post_init__(self):
        counts = (self.total, self.passed, self.failed, self.skipped, self.errors)
        if (any(type(value) is not int or value < 0 for value in counts)
                or type(self.incomplete) is not bool or self.total != sum(counts[1:])
                or self.total == 0 or (self.total == self.skipped and not self.incomplete)):
            raise ValueError("Expected consistent nonnegative counts and at least one executed test")

    @classmethod
    def from_report(cls, report):
        if not isinstance(report, dict) or type(report.get("version")) is not int or report["version"] != 1:
            raise ValueError("Expected a version 1 tester report")
        return cls(**{key: report[key] for key in ("total", "passed", "failed", "skipped", "errors")},
                   incomplete=report.get("incomplete", False))


@dataclass(frozen=True)
class TesterRunResult:
    exit_code: int
    summary: TestSummary | None = None
    unreadable: bool = False

    @property
    def status(self) -> str:
        if self.unreadable:
            return "unreadable"
        if self.summary is not None and (self.summary.failed or self.summary.errors):
            return "failed"
        if self.exit_code:
            return "process_failed"
        if self.summary is not None and (self.summary.incomplete or self.summary.skipped):
            return "unknown"
        return "passed" if self.summary is not None else "unknown"
