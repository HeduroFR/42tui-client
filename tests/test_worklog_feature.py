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
        with patch('ft_tui.features.worklog.adapters.accounting._utc_naive_now',return_value=at):
            self.assertEqual(self.service.toggle_timer(self.a).action,'started')
        with patch('ft_tui.features.worklog.adapters.accounting._utc_naive_now',return_value=at+timedelta(seconds=30)):
            outcome=self.service.toggle_timer(self.b)
            self.assertTrue(outcome.switched)
            self.assertEqual(self.service.timer(self.a).total_seconds,30)
        with patch('ft_tui.features.worklog.adapters.accounting._utc_naive_now',return_value=at+timedelta(seconds=45)):
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

    def test_concurrent_timer_starts_serialize_even_after_session_read(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from sqlalchemy import select
        from ft_tui.db.models import TimeLog
        from ft_tui.features.worklog.adapters import accounting
        for transition in ('start', 'toggle'):
            with self.subTest(transition=transition):
                with TemporaryDirectory() as directory:
                    factory = make_session_factory(f'sqlite:///{Path(directory)/"timers.sqlite"}')
                    try:
                        with factory() as session:
                            session.add_all([Project(slug='one', name='One'), Project(slug='two', name='Two')])
                            session.commit()
                            ids = list(session.scalars(select(Project.id)))
                        first_read, second_read, second_started, release = Event(), Event(), Event(), Event()
                        original = accounting.active_manual_timer
                        def read(session):
                            result = original(session)
                            if not first_read.is_set():
                                first_read.set()
                                self.assertTrue(release.wait(3))
                            else:
                                second_read.set()
                            return result
                        def start(project_id):
                            if transition == 'toggle':
                                if project_id == ids[1]: second_started.set()
                                return SqliteWorklogRepository(factory).toggle_timer(project_id)
                            with factory() as session:
                                session.get(Project, project_id)  # SQLAlchemy autobegin precedes the transition.
                                if project_id == ids[1]: second_started.set()
                                accounting.start_manual_timer(session, project_id)
                        with patch.object(accounting, 'active_manual_timer', side_effect=read):
                            with ThreadPoolExecutor(max_workers=2) as pool:
                                one = pool.submit(start, ids[0])
                                self.assertTrue(first_read.wait(3))
                                two = pool.submit(start, ids[1])
                                try:
                                    self.assertTrue(second_started.wait(3))
                                    self.assertFalse(second_read.wait(.15), 'second transition read before the first committed')
                                finally:
                                    release.set()
                                one.result(5); two.result(5)
                        with factory() as session:
                            self.assertEqual(len(list(session.scalars(select(TimeLog).where(TimeLog.end_time.is_(None))))), 1)
                            accounting.stop_manual_timer(session)
                            self.assertIsNone(accounting.active_manual_timer(session))
                    finally:
                        factory.kw['bind'].dispose()
