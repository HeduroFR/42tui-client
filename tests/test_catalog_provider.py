import unittest
from ft_tui.api.http_client import HttpProjectProvider
from ft_tui.api.catalog_types import CatalogScope
class ProviderTests(unittest.TestCase):
 def test_one_page_and_mixed_track_rejected(self):
  calls=[]
  class Api:
   def request(self,method,path,params):
    calls.append(path)
    return {'snapshot_id':'a','next_cursor':'next','meta':{'cursus_id':21,'campus_id':31},'items':[{'project_id':1,'name':'Exam','slug':'exam','kind':'exam','xp':0,'rank':0,'duration':None,'track':'old','section':'common-core'}]}
  p=HttpProjectProvider(api=Api())
  self.assertEqual(p.list_catalog_page(CatalogScope(21,31),track='old')['items'][0]['xp'],0)
  self.assertEqual(len(calls),1)
  with self.assertRaises(ValueError):p.list_catalog_page(CatalogScope(21,31),track='new')

 def test_malformed_personal_fields_are_rejected_before_persistence(self):
  class Api:
   def __init__(self,value):self.value=value
   def request(self,*args,**kwargs):return self.value
  base={'account_id':'42','snapshot_id':'s','items':[{'id':1,'project_id':2,'slug':'p','name':'P','cursus_ids':[21],'status':'finished','validated':False,'final_mark':0,'vogsphere_url':None}],'next_cursor':None}
  for field,value in [('cursus_ids',['21']),('validated','true'),('final_mark',True),('status',None),('vogsphere_url',42)]:
   payload={**base,'items':[{**base['items'][0],field:value}]}
   with self.subTest(field=field),self.assertRaises(ValueError):HttpProjectProvider(api=Api(payload)).get_account_projects(21)
  with self.assertRaises(ValueError):HttpProjectProvider(api=Api({**base,'next_cursor':42})).get_account_projects(21)
  with self.assertRaises(ValueError):HttpProjectProvider(api=Api({**base,'items':base['items']*2})).get_account_projects(21)

 def test_public_project_projection_discards_personal_and_unknown_fields(self):
  from ft_tui.api.catalog_types import project_summary
  clean=project_summary({'project_id':1,'name':'P','slug':'p','kind':'exam','track':'new','section':'common-core','final_mark':100,'state':'done','cookie':'synthetic-secret','xp':0,'duration':None})
  for key in ('final_mark','state','cookie'):self.assertNotIn(key,clean)
