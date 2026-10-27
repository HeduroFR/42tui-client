import unittest
from ft_tui.db.database import make_session_factory
from ft_tui.features.catalog.adapters.cache import save_account_data, load_context_projects

class RegistrationCacheTests(unittest.TestCase):
 def test_complete_refresh_removes_only_refreshed_cursus_membership(self):
  f=make_session_factory('sqlite:///:memory:')
  fresh={'status':'available','stale':False,'collected_at':'2099-01-01T00:00:00Z'}
  def curriculum(account,cursus,meta=fresh):return {'account_id':account,'cursus_id':cursus,'campus_id':31,'sources':{'projects':meta},'registration':{'project_ids':[]}}
  a={'id':71,'project_id':1001,'slug':'libft','name':'Libft','cursus_ids':[21,7],'status':'in_progress','validated':None,'final_mark':0,'vogsphere_url':None}
  try:
   with f() as s:
    save_account_data(s,'42',21,31,curriculum('42',21),[a])
    save_account_data(s,'42',7,31,curriculum('42',7),[a])
    save_account_data(s,'43',21,31,curriculum('43',21),[a])
    save_account_data(s,'42',21,31,curriculum('42',21),[])
    self.assertEqual(load_context_projects(s,21,31,'42')[0].progress_data,{})
    self.assertEqual(load_context_projects(s,7,31,'42')[0].progress_data['id'],71)
    self.assertEqual(load_context_projects(s,21,31,'43')[0].progress_data['id'],71)
  finally:f.kw['bind'].dispose()
 def test_different_cursus_attempts_do_not_overwrite_each_other(self):
  f=make_session_factory('sqlite:///:memory:')
  try:
   with f() as s:
    for cursus,attempt_id in [(21,71),(7,72)]:
     a={'id':attempt_id,'project_id':1001,'slug':'libft','name':'Libft','cursus_ids':[cursus],'status':'in_progress','validated':None,'final_mark':0,'vogsphere_url':None}
     c={'account_id':'42','cursus_id':cursus,'campus_id':31,'sources':{'projects':{'status':'available','stale':False}}}
     save_account_data(s,'42',cursus,31,c,[a])
    self.assertEqual(load_context_projects(s,21,31,'42')[0].progress_data['id'],71)
    self.assertEqual(load_context_projects(s,7,31,'42')[0].progress_data['id'],72)
  finally:f.kw['bind'].dispose()
