"""Local note/timer/heartbeat operations are usable without a Textual app."""
import unittest
from datetime import datetime,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Project
from ft_tui.features.worklog.service import WorklogService
from ft_tui.features.worklog.adapters.sqlite import SqliteWorklogRepository


class WorklogTests(unittest.TestCase):
    def setUp(self):
        self.factory=make_session_factory('sqlite:///:memory:')
        with self.factory() as s:
            a=Project(slug='a',name='A');b=Project(slug='b',name='B');s.add_all([a,b]);s.commit();self.a,self.b=a.id,b.id
        self.service=WorklogService(SqliteWorklogRepository(self.factory))
    def tearDown(self):self.factory.kw['bind'].dispose()

    def test_notes_remain_project_owned_and_crud_returns_portable_snapshots(self):
        note=self.service.save_note(self.a,None,' First ','# Content')
        self.assertEqual(note.title,'First')
        self.assertEqual(self.service.note(note.id).content,'# Content')
        self.assertIsNone(self.service.save_note(self.b,note.id,'wrong','no'))
        self.assertEqual(self.service.note(note.id).title,'First')
        updated=self.service.save_note(self.a,note.id,'Updated','new')
        self.assertEqual(updated.id,note.id)
        self.assertEqual(self.service.notes(self.a)[0].title,'Updated')
        self.service.delete_note(note.id)
        self.assertIsNone(self.service.note(note.id))
        self.assertIsNone(self.service.save_note(self.a,note.id,'missing','no'))
        with self.assertRaises(ValueError):self.service.save_note(self.a,None,'  ','content')

    def test_timer_switch_and_stop_keep_one_running_timer_and_credited_totals(self):
        at=datetime(2026,10,27,12)
        with patch('ft_tui.services.time_tracking._utc_naive_now',return_value=at):
            self.assertEqual(self.service.toggle_timer(self.a).action,'started')
        with patch('ft_tui.services.time_tracking._utc_naive_now',return_value=at+timedelta(seconds=30)):
            outcome=self.service.toggle_timer(self.b)
            self.assertTrue(outcome.switched)
            self.assertEqual(self.service.timer(self.a).total_seconds,30)
        with patch('ft_tui.services.time_tracking._utc_naive_now',return_value=at+timedelta(seconds=45)):
            self.assertEqual(self.service.toggle_timer(self.b).action,'stopped')
            self.assertIsNone(self.service.timer(self.b).active)
            self.assertEqual(self.service.timer(self.b).total_seconds,15)

    def test_heartbeat_path_resolution_and_idle_cutoff_are_unchanged(self):
        with TemporaryDirectory() as directory:
            with self.factory() as s:s.get(Project,self.a).local_path=directory;s.commit()
            at=datetime(2026,10,27,12)
            result=self.service.heartbeat(Path(directory)/'main.c',editor='test',occurred_at=at)
            self.assertEqual(result.project_name,'A')
            self.assertEqual(result.credited_seconds,0)
            self.assertEqual(self.service.heartbeat(Path(directory)/'main.c',occurred_at=at+timedelta(seconds=120)).credited_seconds,120)
            self.assertEqual(self.service.heartbeat(Path(directory)/'main.c',occurred_at=at+timedelta(seconds=241)).credited_seconds,0)

    def test_accounting_and_view_legacy_imports_have_single_canonical_identity(self):
        from ft_tui.services import time_tracking
        from ft_tui.features.worklog.adapters import accounting
        from ft_tui.ui import dev_log
        from ft_tui.features.worklog.views import notes
        self.assertIs(time_tracking,accounting)
        self.assertIs(dev_log,notes)
