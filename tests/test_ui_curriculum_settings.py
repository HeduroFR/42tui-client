import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from ft_tui.db.database import make_session_factory
from ft_tui.services.user_settings import save_settings
from ft_tui.db.models import Project,Cursus,ProjectCursus
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.ui.components import Select,ListView,ProjectEntry,ProjectRankHeader,Input
class SettingsTests(unittest.IsolatedAsyncioTestCase):
 async def test_unknown_track_has_settings_and_local_work_stays_accessible(self):
  with TemporaryDirectory() as d:
   f=make_session_factory(f'sqlite:///{Path(d)/"ui.sqlite"}')
   with f() as s:
    save_settings(s,{'onboarding_completed':'true'})
    s.add(Project(slug='local',name='Local',local_path=d));s.commit()
   app=FortyTwoTuiApp(f,None)
   async with app.run_test(size=(140,50)) as pilot:
    await pilot.pause()
    self.assertEqual(app.query_one('#cc-default-track',Select).value,'auto')
    app.query_one('#project-view',Select).value='active';await pilot.pause()
    self.assertTrue(app.query_one(ProjectRankHeader).collapsed)
    await app._toggle_project_rank(app.query_one(ProjectRankHeader))
    await pilot.pause()
    self.assertEqual(len(app.query('#project-list-view ProjectEntry')),1)
    app.query_one('#project-list-view',ListView).index=1
    await pilot.pause()
    self.assertEqual(app.selected_project_key,'local:1')
   f.kw['bind'].dispose()

class OnlineCatalogTests(unittest.IsolatedAsyncioTestCase):
 async def test_online_catalog_loads_one_track_and_official_detail(self):
  from ft_tui.api.http_client import HttpProjectProvider
  from datetime import datetime,timezone
  now=datetime.now(timezone.utc).isoformat()
  def row(id,track):return {'project_id':id,'slug':f'p{id}','name':f'Project {id}','kind':'exam','xp':0,'duration':None,'rank':1,'track':track,'section':'common-core','section_source':'rules','evidence_status':'inferred'}
  calls=[]
  class Api:
   def request(self,method,path,params=None):
    calls.append((path,params))
    if path=='/v1/me':return {'account_id':'42','login':'student','campuses':[{'id':31,'name':'Campus','is_primary':True}]}
    if path=='/v1/cursuses':return {'cursuses':[{'id':21,'name':'42','begin_at':'2026-01-01T00:00:00Z','end_at':None}]}
    if path=='/v1/me/curriculum':return {'account_id':'42','cursus_id':21,'campus_id':31,'snapshot_id':'personal','track':{'track':'new','source':'cohort'},'rank':{'rank':None,'source':'unknown'},'registration':{'project_ids':[1001],'status':'available','stale':False,'collected_at':now}}
    if path=='/v1/me/projects':return {'account_id':'42','snapshot_id':'personal','items':[],'next_cursor':None,'meta':{}}
    if path=='/v1/catalog/branches':return {'items':[],'snapshot_id':'graph','next_cursor':None}
    if path=='/v1/catalog/projects':
     rows=[row(1001,'new'),row(1002,'shared')]
     rows=[item for item in rows if item['track'] in (params.get('track'),'shared')] if params.get('track') else []
     return {'items':rows,'snapshot_id':'graph','next_cursor':None,'meta':{'cursus_id':21,'campus_id':31,'collected_at':now,'status':'available'}}
    if path.startswith('/v1/catalog/projects/'):
     id=int(path.rsplit('/',1)[-1]);return {**row(id,'new' if id==1001 else 'shared'),'snapshot_id':'graph','clauses':[],'rules':'','description':'Details','visual_links':[]}
    raise AssertionError(path)
  with TemporaryDirectory() as d:
   f=make_session_factory(f'sqlite:///{Path(d)/"online.sqlite"}')
   with f() as s:save_settings(s,{'onboarding_completed':'true','default_cursus_id':'21','project_view_21':'all'})
   # A different campus's cached projects must not flash as unranked at startup.
   from ft_tui.services.catalog_cache import apply_catalog_page
   with f() as session:
    apply_catalog_page(session,{'items':[row(1001,'new'),row(1002,'shared')],
                              'snapshot_id':'other-campus','meta':{'cursus_id':21,'campus_id':99}})
   app=FortyTwoTuiApp(f,HttpProjectProvider(api=Api()))
   original_refresh=app._refresh_project_list
   seen_unranked=[]
   async def record_refresh(*args,**kwargs):
    result=await original_refresh(*args,**kwargs)
    seen_unranked.extend(p.official_project_id for p in app._visible_projects()
                         if p.official_project_id is not None and not p.catalog_data)
    return result
   app._refresh_project_list=record_refresh
   async with app.run_test(size=(140,50)) as pilot:
    await pilot.pause(1)
    self.assertEqual(app.account_id,'42')
    self.assertEqual(app.query_one('#project-view',Select).value,'relevant')
    app.query_one('#project-view',Select).value='all';await pilot.pause(.5)
    self.assertEqual({p.official_project_id for p in app._visible_projects()},{1001,1002},app.catalog_status)
    self.assertEqual(app.project_curriculum['selected_track']['track'],'new')
    self.assertEqual(seen_unranked,[])
    self.assertEqual({q.get('track') for path,q in calls if path=='/v1/catalog/projects'},{'old','new',None})
    self.assertNotIn('/v1/projects',[path for path,_ in calls])
    await pilot.resize_terminal(80,24);await pilot.pause()
    self.assertGreater(app.query_one('#project-list-view',ListView).size.height,0)
   f.kw['bind'].dispose()

 async def test_failed_second_catalog_page_preserves_the_previous_catalog_cache(self):
  from ft_tui.services.catalog_cache import apply_catalog_page,cache_key
  from ft_tui.db.models import CatalogCache
  class Provider:
   def get_curriculum(self,scope):return {'account_id':'42','cursus_id':21,'campus_id':31,'track':{'track':'new','source':'quest'},'rank':{'rank':1,'source':'quest'},'registration':{'status':'unknown'}}
   def get_account_projects(self,*args):return {'account_id':'42','snapshot_id':'personal','items':[],'next_cursor':None}
   def list_branches(self,*args):return {'snapshot_id':'new','items':[],'next_cursor':None}
   def list_catalog_page(self,scope,**query):
    if query.get('cursor'):raise RuntimeError('second page unavailable')
    return {'items':[{'project_id':2,'slug':'new','name':'New','kind':'project','rank':1,'track':'new','section':'common-core'}],'snapshot_id':'new','meta':{'cursus_id':21,'campus_id':31},'next_cursor':'next'}
  with TemporaryDirectory() as d:
   f=make_session_factory(f'sqlite:///{Path(d)/"atomic.sqlite"}')
   with f() as s:
    save_settings(s,{'onboarding_completed':'true','default_cursus_id':'21'})
    apply_catalog_page(s,{'items':[{'project_id':1,'slug':'saved','name':'Saved','kind':'project','rank':1,'track':'new','section':'common-core'}],'snapshot_id':'saved','meta':{'cursus_id':21,'campus_id':31},'next_cursor':None})
   app=FortyTwoTuiApp(f,None)
   async with app.run_test(size=(140,50)) as pilot:
    await pilot.pause()
    app.account_id='42';app.account_campuses=[{'id':31,'is_primary':True}];app.account_connected=True;app.provider=Provider()
    await app._refresh_catalog_context(app.provider,app.account_generation)
    with f() as s:
     self.assertEqual(s.get(CatalogCache,cache_key('active',[21,31])).payload['snapshot_id'],'saved')
     self.assertIsNone(s.query(Project).filter_by(official_project_id=2).one_or_none())
   f.kw['bind'].dispose()

class StartupCursusTests(unittest.IsolatedAsyncioTestCase):
 async def test_startup_keeps_saved_main_cursus_when_piscine_is_first(self):
  from ft_tui.services.user_settings import get_setting
  with TemporaryDirectory() as directory:
   factory=make_session_factory(f'sqlite:///{Path(directory)/"startup.sqlite"}')
   try:
    with factory() as session:
     save_settings(session,{'onboarding_completed':'true','default_cursus_id':'21'})
     session.add_all([Cursus(id=9,name='C Piscine'),Cursus(id=21,name='42cursus')]);session.commit()
    app=FortyTwoTuiApp(factory,None)
    async with app.run_test(size=(140,50)) as pilot:
     await pilot.pause()
     self.assertEqual(app.query_one('#default-cursus',Select).value,'21')
     with factory() as session:
      self.assertEqual(get_setting(session,'default_cursus_id'),'21')
   finally:
    factory.kw['bind'].dispose()

 async def test_legacy_piscine_default_is_repaired_but_manual_choice_is_preserved(self):
  from ft_tui.api.client_interface import CursusSnapshot
  from ft_tui.services.user_settings import get_setting
  for source,expected in [('',21),('auto',21),('manual',9)]:
   with self.subTest(source=source),TemporaryDirectory() as directory:
    factory=make_session_factory(f'sqlite:///{Path(directory)/"legacy.sqlite"}')
    try:
     with factory() as session:
      save_settings(session,{'onboarding_completed':'true','default_cursus_id':'9','default_cursus_source':source})
      session.add_all([Cursus(id=9,name='C Piscine'),Cursus(id=21,name='42cursus')])
      piscine=Project(slug='piscine',name='Piscine project',local_path=directory)
      main=Project(slug='main',name='Main project',local_path=directory)
      session.add_all([piscine,main]);session.flush()
      session.add_all([ProjectCursus(project_id=piscine.id,cursus_id=9),ProjectCursus(project_id=main.id,cursus_id=21)])
      session.commit()
     app=FortyTwoTuiApp(factory,None)
     async with app.run_test(size=(140,50)) as pilot:
      await pilot.pause()
      with factory() as session:
       self.assertEqual(get_setting(session,'default_cursus_id'),str(expected))
      self.assertEqual(app.query_one('#default-cursus',Select).value,str(expected))
      self.assertEqual({project.slug for project in app.projects.values()},{'main' if expected==21 else 'piscine'})
      # A subsequent deliberate choice must survive the next account refresh.
      app.query_one('#default-cursus',Select).value='21' if expected==9 else '9'
      await pilot.pause()
      with factory() as session:
       self.assertEqual(get_setting(session,'default_cursus_source'),'manual')
      self.assertEqual(app._select_default_cursus_if_unset([
       CursusSnapshot(9,'C Piscine'),CursusSnapshot(21,'42cursus')]),21 if expected==9 else 9)
    finally:
     factory.kw['bind'].dispose()
