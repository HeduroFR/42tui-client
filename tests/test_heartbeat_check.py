"""Heartbeat dry-run must resolve projects without recording activity."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ft_tui.db.database import make_session_factory
from ft_tui.db.models import ActivityHeartbeat, Project
from ft_tui.features.worklog.adapters.accounting import record_heartbeat


class HeartbeatCheckTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.factory = make_session_factory("sqlite:///:memory:")
        self.addCleanup(lambda: self.factory.kw["bind"].dispose())
        with self.factory() as session:
            session.add(Project(slug="ft_tui", name="ft_tui", local_path=str(self.root)))
            session.commit()

    def test_dry_run_resolves_without_writing(self):
        with self.factory() as session:
            before = session.query(ActivityHeartbeat).count()
            project, credited = record_heartbeat(session, self.root / "check", dry_run=True)
            self.assertEqual(project.name, "ft_tui")
            self.assertEqual(credited, 0.0)
            self.assertEqual(session.query(ActivityHeartbeat).count(), before)

    def test_dry_run_outside_project_still_errors(self):
        with self.factory() as session, self.assertRaisesRegex(
            ValueError, "outside every configured project"
        ):
            record_heartbeat(session, Path("/tmp/not-a-project/file"), dry_run=True)


if __name__ == "__main__":
    unittest.main()
