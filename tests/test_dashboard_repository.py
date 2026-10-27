"""Dashboard local reads return portable values and do not mutate the database."""
import unittest
from datetime import datetime, timedelta
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Project, DevNote, ActivityHeartbeat
from ft_tui.features.dashboard.adapters.sqlite import SqliteDashboardReader


class DashboardRepositoryTests(unittest.TestCase):
    def test_notes_and_activity_projection_preserve_order_and_cutoff(self):
        factory = make_session_factory('sqlite:///:memory:')
        at = datetime(2026, 10, 26, 12)
        try:
            with factory() as session:
                project = Project(slug='one', name='One')
                session.add(project); session.flush(); id = project.id
                for index in range(4):
                    session.add(DevNote(project_id=id, title=f'Note {index}', updated_at=at+timedelta(minutes=index)))
                session.add_all([ActivityHeartbeat(project_id=id, occurred_at=at-timedelta(days=60), credited_project_id=id, credited_seconds=20),
                                 ActivityHeartbeat(project_id=id, occurred_at=at, credited_project_id=id, credited_seconds=60)])
                session.commit()
            reader = SqliteDashboardReader(factory)
            notes = reader.recent_notes()
            self.assertEqual([row[3] for row in notes], ['Note 3', 'Note 2', 'Note 1'])
            self.assertTrue(all(isinstance(row, tuple) for row in notes))
            self.assertEqual(reader.heartbeats_since(at-timedelta(days=1)), [(at, 60)])
            latest, heartbeat = reader.activity()
            self.assertEqual(heartbeat, (id, at))
            self.assertEqual(latest[id], at+timedelta(minutes=3))
            self.assertEqual(reader.tracked(id), 80)
        finally:
            factory.kw['bind'].dispose()
