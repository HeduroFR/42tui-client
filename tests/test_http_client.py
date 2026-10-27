import unittest
from pathlib import Path
from ft_tui.api.http_client import HttpProjectProvider
class ProviderMetadataTests(unittest.TestCase):
 def test_profile_cursus_and_subject_contract(self):
  class Api:
   def request(self,method,path,**kwargs):
    if path=='/v1/me/subjects/slug':return {'sha256':None,'pdf_base64':None}
    if path=='/v1/me':return {'account_id':'42','login':'student','campuses':[]}
    return {'cursuses':[{'id':21,'name':'42','begin_at':'2026-01-01T00:00:00Z','end_at':None}]}
  p=HttpProjectProvider(api=Api())
  self.assertEqual(p.get_profile()['account_id'],'42');self.assertEqual(p.list_cursuses()[0].begin_at.year,2026)
  self.assertIsNone(p.get_subject_reference_sha256('slug'));self.assertFalse(p.download_subject_pdf('slug',Path('unused')))

 def test_goals_uses_account_scope_and_rejects_another_accounts_response(self):
  class Api:
   def request(self,method,path,**kwargs):
    self_call=(method,path,kwargs)
    if self_call!=('GET','/v1/me/goals',{'params':{'cursus_id':21}}):raise AssertionError(self_call)
    return {'account_id':'42','cursus_id':21,'status':'pending','collected_at':None,'stale':True}
  p=HttpProjectProvider(api=Api())
  self.assertEqual(p.get_goals(21,'42')['status'],'pending')
  with self.assertRaises(ValueError):p.get_goals(21,'other')

 def test_campus_directory_uses_full_list_endpoint_and_rejects_invalid_ids(self):
  class Api:
   def request(self,method,path,**kwargs):
    if (method,path,kwargs)!=('GET','/v1/campuses',{}):raise AssertionError((method,path,kwargs))
    return {'campuses':[{'id':44,'name':'Barcelona','country':'Spain','city':'Barcelona','active':True}]}
  self.assertEqual(HttpProjectProvider(api=Api()).list_campuses()[0]['id'],44)

 def test_campus_directory_rejects_invalid_or_duplicate_records(self):
  from ft_tui.api.campus_types import campus_directory
  valid={'id':1,'name':'Paris','country':'France','city':'Paris','active':True}
  for rows in [[{**valid,'id':0}],[valid,valid],[{**valid,'country':42}],[{**valid,'active':'yes'}]]:
   with self.subTest(rows=rows),self.assertRaises(ValueError):
    campus_directory({'campuses':rows})
