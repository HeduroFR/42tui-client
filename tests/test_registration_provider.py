import copy
import unittest
from uuid import uuid4
from ft_tui.api.http_client import HttpProjectProvider
from ft_tui.features.catalog.models import CatalogScope
from registration_fixtures import registration_state,operation

class RegistrationProviderTests(unittest.TestCase):
 def test_provider_sends_fixed_context_and_preserves_idempotency_header(self):
  class API:
   def request(self,method,path,**kwargs):
    self.call=(method,path,kwargs)
    state=registration_state()
    if method=='POST' and not path.endswith('refresh'):
     op=operation();state['operation']=op;return {'state':state,'operation':op}
    return state
  api=API();provider=HttpProjectProvider(api=api);key=str(uuid4());scope=CatalogScope(21,31)
  provider.get_project_registration(1001,scope,'42')
  self.assertEqual(api.call[0],'GET')
  self.assertEqual(provider.get_project_registration(1001,scope,'42')['project_mode'],'solo')
  provider.register_project(1001,scope,'42',key)
  self.assertEqual(api.call,('POST','/v1/me/projects/1001/registration',{'json':scope.params(),'headers':{'Idempotency-Key':key}}))
 def test_invalid_identity_context_url_enum_and_bool_are_rejected(self):
  from ft_tui.features.projects.registration.types import registration_state as validate
  base=registration_state();scope=CatalogScope(21,31)
  for section,key,value in [(None,'project_mode','invalid'),(None,'project_id',True),(None,'account_id','43'),('context','cursus_id',7),('capability','mode','unsafe'),(None,'intra_url','https://evil.example'),('eligibility','reason_code','arbitrary raw error')]:
   state=copy.deepcopy(base)
   if section:state[section][key]=value
   else:state[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):validate(state,1001,scope,'42')
 def test_replayed_operation_and_latest_state_can_have_different_operation_ids(self):
  from ft_tui.features.projects.registration.types import registration_result
  state=registration_state();state['operation']=operation('registered')
  replay=operation('rejected')
  result=registration_result({'state':state,'operation':replay},1001,CatalogScope(21,31),'42')
  self.assertEqual(result['operation']['id'],replay['id'])
  self.assertEqual(result['state']['operation']['id'],state['operation']['id'])
