import unittest
from datetime import datetime
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Project,DevNote,TimeLog
from ft_tui.features.catalog.adapters.cache import apply_catalog_page
class MetadataTests(unittest.TestCase):
 def test_refresh_preserves_local_checkout_notes_and_timers(self):
  factory=make_session_factory('sqlite:///:memory:')
  with factory() as session:
   p=Project(official_project_id=1001,slug='before',name='Before',local_path='/work/project',dev_repo_url='git@host:dev.git')
   session.add(p);session.flush();local=p.id
   session.add_all([DevNote(project_id=local,title='Keep',content='Notes'),TimeLog(project_id=local,start_time=datetime.now())]);session.commit()
   page={'items':[{'project_id':1001,'slug':'after','name':'After','kind':'project','xp':100,'rank':1,'track':'new','section':'common-core'}],'snapshot_id':'v2','next_cursor':None,'meta':{'cursus_id':21,'campus_id':31}}
   apply_catalog_page(session,page)
   p=session.get(Project,local)
   self.assertEqual(p.slug,'after');self.assertEqual(p.local_path,'/work/project');self.assertEqual(p.dev_repo_url,'git@host:dev.git')
   self.assertEqual(session.query(DevNote).one().project_id,local);self.assertEqual(session.query(TimeLog).one().project_id,local)
  factory.kw['bind'].dispose()

 def test_team_mode_survives_validation_and_local_cache(self):
  from ft_tui.features.catalog.models import project_summary
  from ft_tui.features.catalog.adapters.cache import load_context_projects
  data={'project_id':1001,'slug':'libft','name':'Libft','kind':'project','xp':None,'rank':None,'track':'new','section':'common-core','project_mode':'solo','team_size':1}
  clean=project_summary(data)
  self.assertEqual(clean.get('project_mode'),'solo')
  self.assertEqual(clean.get('team_size'),1)
  with self.assertRaises(ValueError):project_summary({**data,'team_size':0})
  with self.assertRaises(ValueError):project_summary({**data,'project_mode':'invalid'})
  factory=make_session_factory('sqlite:///:memory:')
  try:
   with factory() as session:
    apply_catalog_page(session,{'items':[clean],'snapshot_id':'v1','meta':{'cursus_id':21,'campus_id':31}})
    self.assertEqual(load_context_projects(session,21,31,None)[0].catalog_data['project_mode'],'solo')
  finally:factory.kw['bind'].dispose()
