"""Project configuration resets subject state only when its path changes."""
import unittest
from datetime import datetime
from types import SimpleNamespace
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Project
from ft_tui.features.projects.service import ProjectService
from ft_tui.features.projects.adapters.sqlite import SqliteProjectRepository

class ProjectFeatureTests(unittest.TestCase):
    def setUp(self):
        self.factory=make_session_factory('sqlite:///:memory:')
        with self.factory() as s:
            p=Project(slug='one',name='One',setup_status='available',local_path='/old',subject_pdf_path='subject.pdf',subject_pdf_sha256='hash',subject_reference_sha256='ref',subject_checked_at=datetime(2026,1,1))
            s.add(p);s.commit();self.id=p.id
        self.calls=[]
        self.service=ProjectService(SqliteProjectRepository(self.factory),lambda path,**kw:self.calls.append((path,kw)))
    def tearDown(self):self.factory.kw['bind'].dispose()
    def test_path_change_clears_subject_and_preserves_presentation_evidence(self):
        result=self.service.save_settings(self.id,{'local_path':'/new','dev_repo_url':'dev'},catalog={'snapshot_id':'same'},progress={'status':'available'})
        self.assertEqual(result.local_path,'/new')
        self.assertEqual(result.status,'available')
        self.assertEqual(result.catalog_data,{'snapshot_id':'same'})
        with self.factory() as s:
            p=s.get(Project,self.id)
            self.assertEqual(p.setup_status,'in_progress')
            self.assertIsNone(p.subject_pdf_path)
            self.assertIsNone(p.subject_checked_at)
    def test_unchanged_path_keeps_subject_and_missing_project_is_explicit(self):
        self.service.save_settings(self.id,{'local_path':'/old','dev_repo_url':''},catalog={},progress={})
        with self.factory() as s:self.assertEqual(s.get(Project,self.id).subject_pdf_sha256,'hash')
        self.assertIsNone(self.service.save_settings(999,{'local_path':'/x','dev_repo_url':''},catalog={},progress={}))
    def test_checkout_is_a_supplied_capability(self):
        self.service.setup_checkout('/local',dev_remote_url='origin',vogsphere_url=None)
        self.assertEqual(self.calls,[('/local',{'dev_remote_url':'origin','vogsphere_url':None})])
