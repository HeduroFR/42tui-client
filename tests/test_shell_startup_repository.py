"""Startup persistence keeps transactional preferences and hydrated snapshots."""
from datetime import datetime
import unittest
from sqlalchemy.exc import IntegrityError
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Cursus,Project,ProjectCursus,DevNote,TimeLog
from ft_tui.infrastructure.startup import SqliteStartupRepository
from ft_tui.app.startup import StartupService
from ft_tui.features.catalog.adapters.cache import save_cache,save_account_data


class StartupRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.factory=make_session_factory('sqlite:///:memory:')
        self.addCleanup(self.factory.kw['bind'].dispose)
        self.repository=SqliteStartupRepository(self.factory)

    def test_presence_and_atomic_rollback_preserve_earlier_preferences(self):
        self.repository.save({'language':'','first':'original'})
        self.assertEqual(self.repository.preferences(('language','missing')),{'language':''})
        with self.assertRaises(IntegrityError):self.repository.save({'first':'changed','broken':None})
        self.assertEqual(self.repository.preferences(('first','broken')),{'first':'original'})

    def test_cached_cursus_snapshots_are_sorted_and_detached_primitives(self):
        begin=datetime(2026,1,2)
        with self.factory() as session:
            session.add_all([Cursus(id=21,name='42cursus',begin_at=begin),Cursus(id=9,name='Piscine')]);session.commit()
        rows=self.repository.cached_cursuses()
        self.assertEqual([row.id for row in rows],[9,21]);self.assertEqual(rows[1].begin_at,begin)
        self.assertFalse(hasattr(rows[0],'_sa_instance_state'))

    def test_catalog_eager_notes_logs_and_scoped_hydration_survive_session_close(self):
        with self.factory() as session:
            session.add(Cursus(id=21,name='42cursus'));session.flush()
            project=Project(official_project_id=1001,slug='libft',name='Libft')
            session.add(project);session.flush()
            session.add(ProjectCursus(project_id=project.id,cursus_id=21))
            session.add(DevNote(project_id=project.id,title='Notes',content='body'))
            session.add(TimeLog(project_id=project.id,start_time=datetime(2026,1,1),end_time=datetime(2026,1,1,1)))
            save_cache(session,'project',21,31,[21,31,1001],{'project_id':1001,'name':'Scoped','snapshot_id':'s1'})
            save_cache(session,'active',21,31,[21,31],{'snapshot_id':'s1'})
            save_account_data(session,'42',21,31,{'account_id':'42','cursus_id':21,'campus_id':31,
                'rank':{'rank':2},'track':{'track':'new'}},[])
            session.commit()
        projects,curriculum=self.repository.catalog(21,'42',31,allow_cached_owner=False)
        self.assertEqual(len(projects),1);self.assertEqual(projects[0].notes[0].title,'Notes')
        self.assertEqual(len(projects[0].time_logs),1);self.assertEqual(projects[0].catalog_data['name'],'Scoped')
        self.assertEqual(curriculum['rank']['rank'],2)
        other,_=self.repository.catalog(21,'other',99,allow_cached_owner=False)
        self.assertEqual(other[0].catalog_data,{})

    def test_cached_owner_fallback_is_explicit_and_branches_match_active_snapshot(self):
        with self.factory() as session:
            save_account_data(session,'42',21,31,{'account_id':'42','cursus_id':21,'campus_id':31,
                'rank':{'rank':2},'track':{'track':'new'}},[])
            save_cache(session,'active',21,31,[21,31],{'snapshot_id':'s1'})
            save_cache(session,'branches',21,31,[21,31,'new'],{'snapshot_id':'s1','items':[{'id':'branch'}]})
            session.commit()
        service=StartupService(self.repository)
        self.assertEqual(service.catalog(21,None,31,allow_cached_owner=False)[1],{})
        self.assertEqual(service.catalog(21,None,31,allow_cached_owner=True)[1]['rank']['rank'],2)
        self.assertEqual(service.branches(21,31,'new'),[{'id':'branch'}])
        self.assertEqual(service.branches(21,31,'old'),[])
