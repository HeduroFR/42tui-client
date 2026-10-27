"""Registration/team operations remain headless, identity-pinned and single-shot."""
import copy
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from ft_tui.api.catalog_types import CatalogScope
from ft_tui.features.projects.registration.service import RegistrationService, StaleRegistrationContext
from tests.registration_fixtures import registration_state, operation

SCOPE=CatalogScope(21,31)

def team():
    return {'account_id':'42','project_id':1001,'context':SCOPE.params(),'can_write':True,
        'session':{'id':10,'project_id':1001,'solo':False,'max_people':2},
        'teams':[{'id':8,'project_id':1001,'project_session_id':10,'name':'Team','status':'creating_group',
            'locked':False,'closed':False,'members':[{'id':42,'login':'me','leader':True,'accepted':True},
            {'id':43,'login':'mate','leader':False,'accepted':True}]}]}

class RegistrationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_registration_read_refresh_and_exact_mutation_arguments(self):
        calls=[]; key=str(uuid4()); state=registration_state()
        def read(*args): calls.append(args); return copy.deepcopy(state)
        def register(*args):
            calls.append(args); result=copy.deepcopy(state); result['operation']=operation('registered')
            return {'state':result,'operation':result['operation']}
        provider=SimpleNamespace(get_project_registration=read,refresh_project_registration=read,register_project=register)
        service=RegistrationService()
        for action in ('read','refresh','register'):
            result=await service.registration(provider,action,1001,SCOPE,'42',current=lambda:True,key=key,state=state)
            self.assertEqual(result['project_id'],1001)
        self.assertEqual(calls,[(1001,SCOPE,'42'),(1001,SCOPE,'42'),(1001,SCOPE,'42',key)])

    async def test_queued_registration_and_team_writes_are_fenced_inside_executor(self):
        for kind in ('registration','team'):
            live=[True]; calls=[]
            async def queued(function,*args): live[0]=False; return function(*args)
            provider=SimpleNamespace(register_project=lambda *args:calls.append(args),change_project_team=lambda *args:calls.append(args))
            with patch('ft_tui.features.projects.registration.service.asyncio.to_thread',queued):
                with self.assertRaises(StaleRegistrationContext):
                    if kind=='registration':
                        await RegistrationService().registration(provider,'register',1001,SCOPE,'42',current=lambda:live[0],key=str(uuid4()),state=registration_state())
                    else:
                        await RegistrationService().team(provider,1001,SCOPE,'42',current=lambda:live[0],action={'action':'lock','team_id':8},key=str(uuid4()),state=team())
            self.assertEqual(calls,[])

    async def test_result_after_scope_revision_change_is_discarded(self):
        live=[True]
        def read(*args): live[0]=False; return registration_state()
        with self.assertRaises(StaleRegistrationContext):
            await RegistrationService().registration(SimpleNamespace(get_project_registration=read),'read',1001,SCOPE,'42',current=lambda:live[0])

    async def test_registration_identity_and_permission_and_freshness_rejected_before_write(self):
        states=[]
        for key,value in [('account_id','43'),('project_id',1002)]:
            state=registration_state(); state[key]=value; states.append(state)
        state=registration_state();state['capability']['mode']='intra';states.append(state)
        state=registration_state();state['sources']['projects']['collected_at']=(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat();states.append(state)
        state=registration_state();state['operation']=operation('outcome_unknown');states.append(state)
        calls=[];provider=SimpleNamespace(register_project=lambda *args:calls.append(args))
        for state in states:
            with self.assertRaises(ValueError):
                await RegistrationService().registration(provider,'register',1001,SCOPE,'42',current=lambda:True,key=str(uuid4()),state=state)
        self.assertEqual(calls,[])

    async def test_uncertain_registration_write_is_not_retried_or_rekeyed(self):
        calls=[]; key=str(uuid4())
        def register(*args): calls.append(args);raise TimeoutError('uncertain')
        with self.assertRaises(TimeoutError):
            await RegistrationService().registration(SimpleNamespace(register_project=register),'register',1001,SCOPE,'42',current=lambda:True,key=key,state=registration_state())
        self.assertEqual(calls,[(1001,SCOPE,'42',key)])

    async def test_malformed_registration_result_is_rejected(self):
        provider=SimpleNamespace(register_project=lambda *args:{'state':registration_state(),'operation':None})
        with self.assertRaises(ValueError):
            await RegistrationService().registration(provider,'register',1001,SCOPE,'42',current=lambda:True,key=str(uuid4()),state=registration_state())

    async def test_team_permission_and_lock_rules_are_headless(self):
        states=[]
        state=team();state['can_write']=False;states.append(state)
        state=team();state['teams'][0]['members'][0]['leader']=False;states.append(state)
        state=team();state['teams'][0]['members'][1]['accepted']=False;states.append(state)
        state=team();state['teams'][0]['locked']=True;states.append(state)
        calls=[];provider=SimpleNamespace(change_project_team=lambda *args:calls.append(args))
        for state in states:
            with self.assertRaises(ValueError):
                await RegistrationService().team(provider,1001,SCOPE,'42',current=lambda:True,action={'action':'lock','team_id':8},key=str(uuid4()),state=state)
        self.assertEqual(calls,[])

    async def test_team_mutation_keeps_exact_draft_uuid_and_validates_response_identity(self):
        calls=[]; key=str(uuid4()); draft={'action':'lock','team_id':8}
        def change(*args):calls.append(args);return team()
        result=await RegistrationService().team(SimpleNamespace(change_project_team=change),1001,SCOPE,'42',current=lambda:True,action=draft,key=key,state=team())
        self.assertEqual(result,team());self.assertIs(calls[0][3],draft);self.assertEqual(calls[0][-1],key)
        invalid=team();invalid['account_id']='43'
        with self.assertRaises(ValueError):
            await RegistrationService().team(SimpleNamespace(get_project_team=lambda *args:invalid),1001,SCOPE,'42',current=lambda:True)

    async def test_team_uncertain_write_has_one_attempt_with_original_operation(self):
        calls=[];key=str(uuid4());draft={'action':'accept','team_id':8};snapshot=team()
        snapshot['teams'][0]['members'][0]['accepted']=False
        def change(*args):calls.append(args);raise TimeoutError('unknown')
        with self.assertRaises(TimeoutError):
            await RegistrationService().team(SimpleNamespace(change_project_team=change),1001,SCOPE,'42',current=lambda:True,action=draft,key=key,state=snapshot)
        self.assertEqual(len(calls),1);self.assertIs(calls[0][3],draft);self.assertEqual(calls[0][-1],key)

    async def test_obsolete_read_never_dispatches(self):
        provider=SimpleNamespace(get_project_registration=lambda *args:self.fail('obsolete read'),get_project_team=lambda *args:self.fail('obsolete team'))
        with self.assertRaises(StaleRegistrationContext):
            await RegistrationService().registration(provider,'read',1001,SCOPE,'42',current=lambda:False)
        with self.assertRaises(StaleRegistrationContext):
            await RegistrationService().team(provider,1001,SCOPE,'42',current=lambda:False)

    def test_legacy_modules_preserve_canonical_helpers_dataclass_and_patch_identity(self):
        from importlib import import_module
        for old,new in [('ft_tui.ui.project_registration','views.registration'),
                        ('ft_tui.ui.project_team','views.team'),
                        ('ft_tui.services.project_registration','registration.presentation'),
                        ('ft_tui.api.registration_types','registration.types'),
                        ('ft_tui.api.team_types','registration.team_types')]:
            self.assertIs(import_module(old),import_module('ft_tui.features.projects.'+new))
        from ft_tui.services.project_registration import RegistrationView
        from ft_tui.features.projects.registration.presentation import RegistrationView as OwnedView
        self.assertIs(RegistrationView,OwnedView)
        with patch('ft_tui.ui.project_registration.datetime',sentinel := object()):
            self.assertIs(import_module('ft_tui.features.projects.views.registration').datetime,sentinel)

    async def test_queued_registration_uses_reviewed_snapshot_and_original_project_after_selection_switch(self):
        from ft_tui.features.projects.views.registration import ProjectRegistrationMixin
        from unittest.mock import Mock
        original=('42',21,31,1001); other=('42',21,31,1002); calls=[]; workers=[]
        reviewed=registration_state()
        cached=registration_state();cached['capability']['mode']='intra'
        def register(project,scope,account,key):
            calls.append((project,scope,account,key));value=registration_state();value['operation']=operation('registered')
            return {'state':value,'operation':value['operation']}
        class Harness(ProjectRegistrationMixin):
            def _registration_context(self):return self.context
        app=Harness();app.context=original;app.account_id='42';app.account_generation=0
        app.provider=SimpleNamespace(register_project=register)
        app.language='en';app._registration_state=reviewed
        app._registration_states={original:cached};app._registration_busy={};app._registration_keys={}
        app._registration_uncertain=set();app._registration_errors={};app._registration_epochs={}
        app._registration_storage=Mock();app._render_project_registration=Mock();app._request_catalog_refresh=Mock()
        app.run_worker=lambda worker,**kwargs:workers.append(worker)
        await app._handle_registration_button('registration-action')
        key=app._registration_keys[original]
        # Later in-place UI data and project selection must not replace authorization.
        reviewed['capability']['mode']='intra';app.context=other;app._registration_state=registration_state()
        app._registration_state['project_id']=1002
        await workers[0]()
        self.assertEqual(calls,[(1001,SCOPE,'42',key)])
        self.assertEqual(app._registration_states[original]['operation']['outcome'],'registered')
        self.assertEqual(app._registration_state['project_id'],1002)
        self.assertNotIn(original,app._registration_busy)
