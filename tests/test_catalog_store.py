import unittest
from ft_tui.db.database import make_session_factory,DatabaseResetRequired
from ft_tui.db.models import Project,DevNote,TimeLog
from ft_tui.features.catalog.adapters.cache import apply_catalog_page, save_account_data, load_context_projects
class CatalogStoreTests(unittest.TestCase):
 def test_offline_exam_projection_corrects_old_cache_without_changing_snapshot_or_payload(self):
  from ft_tui.db.models import CatalogCache
  from ft_tui.features.catalog.adapters.cache import cache_key
  f=make_session_factory('sqlite:///:memory:')
  try:
   with f() as s:
    item={'project_id':1001,'slug':'42next-exam-rank-02','name':'Exam Rank 02',
          'kind':'project','rank':2,'track':'new','section':'common-core'}
    apply_catalog_page(s,{'items':[item],'snapshot_id':'existing','next_cursor':None,
                          'meta':{'cursus_id':21,'campus_id':31}})
   with f() as s:
    project=load_context_projects(s,21,31,None)[0]
    self.assertEqual(project.catalog_data['kind'],'exam')
    self.assertEqual(project.catalog_data['snapshot_id'],'existing')
    self.assertEqual(s.get(CatalogCache,cache_key('project',[21,31,1001])).payload['kind'],'project')
  finally:
   f.kw['bind'].dispose()

 def test_identity_context_and_account_are_separate(self):
  f=make_session_factory('sqlite:///:memory:')
  def page(campus,slug,xp):return {'items':[{'project_id':1001,'slug':slug,'name':'Exam','kind':'exam','xp':xp,'rank':0,'track':'shared','section':'common-core','section_source':'rules','duration':None}], 'snapshot_id':str(campus),'next_cursor':None,'meta':{'cursus_id':21,'campus_id':campus,'collected_at':'2026-01-01','status':'available'}}
  with f() as s:
   apply_catalog_page(s,page(31,'old-name',0));local=s.query(Project).one().id
   apply_catalog_page(s,page(1,'renamed',500))
   save_account_data(s,'a',21,31,{'account_id':'a','cursus_id':21,'campus_id':31},[{'id':1,'project_id':1001,'slug':'renamed','name':'Exam','cursus_ids':[21],'status':'finished','validated':False,'final_mark':0,'vogsphere_url':'private'}])
   a=load_context_projects(s,21,31,'a')[0];self.assertEqual(a.id,local);self.assertEqual(a.catalog_data['xp'],0);self.assertEqual(a.last_defense_score,0);self.assertEqual(a.status,'failed')
   b=load_context_projects(s,21,1,'b')[0];self.assertIsNone(b.last_defense_score);self.assertIsNone(b.vogsphere_url);self.assertEqual(b.catalog_data['xp'],500)
   self.assertNotIn('last_defense_score',Project.__table__.columns.keys())
  f.kw['bind'].dispose()

 def test_registration_ids_without_catalog_metadata_stay_representable(self):
  from ft_tui.features.catalog.read_models import curriculum_projects
  f=make_session_factory('sqlite:///:memory:')
  with f() as s:
   c={'account_id':'42','cursus_id':21,'campus_id':31,'registration':{'project_ids':[999],'status':'available','stale':False}}
   save_account_data(s,'42',21,31,c,[])
   projects=load_context_projects(s,21,31,'42')
   self.assertEqual([p.official_project_id for p in curriculum_projects(projects,curriculum=c,scope='eligible')],[999])
   self.assertEqual(projects[0].slug,'')
  f.kw['bind'].dispose()

 def test_branches_restore_only_for_the_selected_campus_and_track(self):
  from ft_tui.features.catalog.adapters.cache import save_cache, load_branches
  f=make_session_factory('sqlite:///:memory:')
  with f() as s:
   payload={'items':[{'branch_id':'branch','track':'old','project_ids':[1]}],'snapshot_id':'v','next_cursor':'next'}
   save_cache(s,'branches',21,31,[21,31,'old'],payload);s.commit()
   self.assertEqual(load_branches(s,21,31,'old'),payload['items'])
   self.assertEqual(load_branches(s,21,31,'new'),[])
   self.assertEqual(load_branches(s,21,1,'old'),[])
  f.kw['bind'].dispose()

 def test_offline_personal_sources_expire_without_an_online_refresh(self):
  from ft_tui.features.catalog.adapters.cache import load_curriculum
  f=make_session_factory('sqlite:///:memory:')
  with f() as s:
   source={'status':'available','stale':False,'collected_at':'2000-01-01T00:00:00Z'}
   save_account_data(s,'42',21,31,{'account_id':'42','cursus_id':21,'campus_id':31,'registration':{**source,'project_ids':[999]},'sources':{'projects':source}},[])
   cached=load_curriculum(s,'42',21,31)
   self.assertTrue(cached['registration']['stale']);self.assertTrue(cached['sources']['projects']['stale'])
  f.kw['bind'].dispose()
