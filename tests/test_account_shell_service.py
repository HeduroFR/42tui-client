"""Account shell storage and queued reads preserve session ownership."""
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch
from ft_tui.features.accounts.shell_service import AccountShellService

class Repository:
    def __init__(self):self.calls=[]
    def select_default(self,cursuses,today):self.calls.append(('select',cursuses,today));return (21,True)
    def configured_cursus(self,session=None):self.calls.append(('configured',session));return 21
    def remember_account(self,account,campuses):self.calls.append(('account',account,campuses))
    def save_cursuses(self,values):self.calls.append(('cursuses',values))
    def save_campuses(self,values):self.calls.append(('campuses',values))

class AccountShellTests(unittest.IsolatedAsyncioTestCase):
    async def test_queued_expired_context_never_dispatches(self):
        active=[True];calls=[]
        async def queued(operation):active[0]=False;return operation()
        with patch('ft_tui.features.accounts.shell_service.asyncio.to_thread',queued):
            result=await AccountShellService(Repository()).read(lambda:calls.append('read'),lambda:active[0])
        self.assertIsNone(result);self.assertEqual(calls,[])

    async def test_obsolete_result_is_discarded_after_request(self):
        active=[True]
        def operation():active[0]=False;return {'account_id':'42'}
        self.assertIsNone(await AccountShellService(Repository()).read(operation,lambda:active[0]))

    def test_explicit_storage_capabilities_preserve_call_arguments(self):
        repository=Repository();service=AccountShellService(repository);today=date(2026,10,27);cursuses=[object()];campuses=[{'id':31}];session=object()
        self.assertEqual(service.select_default(cursuses,today),(21,True));self.assertEqual(service.configured_cursus(session),21)
        service.remember_account('42',campuses);service.save_cursuses(cursuses);service.save_campuses(campuses)
        self.assertEqual(repository.calls,[('select',cursuses,today),('configured',session),('account','42',campuses),('cursuses',cursuses),('campuses',campuses)])

class AccountShellStorageTests(unittest.TestCase):
    def test_configured_selection_retains_legacy_session_callable_and_invalid_values(self):
        from ft_tui.db.database import make_session_factory
        from ft_tui.features.accounts.adapters.shell import SqliteAccountShellRepository
        from ft_tui.features.settings.adapters.storage import save_settings
        factory=make_session_factory('sqlite:///:memory:')
        try:
            repository=SqliteAccountShellRepository(factory)
            for value,expected in [('21',21),('broken',None),('-3',None),('',None)]:
                with factory() as session:
                    save_settings(session,{'default_cursus_id':value})
                    self.assertEqual(repository.configured_cursus(session),expected)
                self.assertEqual(repository.configured_cursus(),expected)
        finally:factory.kw['bind'].dispose()

    def test_automatic_piscine_repair_preserves_manual_missing_and_malformed_choices(self):
        from ft_tui.db.database import make_session_factory
        from ft_tui.features.accounts.adapters.shell import SqliteAccountShellRepository
        from ft_tui.features.settings.adapters.storage import save_settings,get_setting
        from ft_tui.api.client_interface import CursusSnapshot
        factory=make_session_factory('sqlite:///:memory:')
        try:
            repository=SqliteAccountShellRepository(factory)
            cursuses=[CursusSnapshot(id=9,name='Piscine C'),CursusSnapshot(id=21,name='42cursus')]
            for value,source,expected in [('9','manual',(9,False)),('unknown','auto',(None,False)),('77','auto',(77,False)),('9','auto',(21,True))]:
                with factory() as session:save_settings(session,{'default_cursus_id':value,'default_cursus_source':source})
                self.assertEqual(repository.select_default(cursuses,date(2026,10,27)),expected)
                with factory() as session:
                    self.assertEqual(get_setting(session,'default_cursus_id'),str(expected[0]) if expected[1] else value)
        finally:factory.kw['bind'].dispose()

    def test_account_and_directory_cache_keys_do_not_mix_memberships(self):
        import json
        from ft_tui.db.database import make_session_factory
        from ft_tui.features.accounts.adapters.shell import SqliteAccountShellRepository
        from ft_tui.features.settings.adapters.storage import get_setting
        factory=make_session_factory('sqlite:///:memory:')
        try:
            repository=SqliteAccountShellRepository(factory)
            memberships=[{'id':31,'is_primary':True}];directory=[{'id':55,'name':'Porto'}]
            repository.remember_account('42',memberships);repository.save_campuses(directory)
            with factory() as session:
                self.assertEqual(get_setting(session,'catalog_last_account'),'42')
                self.assertEqual(json.loads(get_setting(session,'catalog_last_campuses')),memberships)
                self.assertEqual(json.loads(get_setting(session,'campus_directory')),directory)
        finally:factory.kw['bind'].dispose()

class AccountShellControllerTests(unittest.IsolatedAsyncioTestCase):
    async def test_session_check_does_not_persist_after_reconnect_same_account(self):
        from ft_tui.features.accounts.views.controller import AccountControllerMixin
        from unittest.mock import Mock
        class Harness(AccountControllerMixin): pass
        app=Harness();app.account_generation=0;app.account_id='42';app.account_shell_service=AccountShellService(Repository());app.profile_service=SimpleNamespace(persist_profile=Mock())
        def request(*args,**kwargs):
            app.account_generation+=1
            return {'account_id':'42','login':'me'}
        app.oauth_client=SimpleNamespace(request=request)
        await app._check_session()
        app.profile_service.persist_profile.assert_not_called()

    async def test_stale_online_sync_never_calls_override_or_updates_ui(self):
        from ft_tui.features.accounts.views.controller import AccountControllerMixin
        from unittest.mock import Mock
        class Harness(AccountControllerMixin): pass
        app=Harness();app.account_generation=2;app.provider=object();app.account_shell_service=AccountShellService(Repository());app._sync_online_data=Mock()
        await app._sync_online_provider(object(),1)
        app._sync_online_data.assert_not_called()

    async def test_current_session_profile_persists_once_with_captured_client(self):
        from ft_tui.features.accounts.views.controller import AccountControllerMixin
        from unittest.mock import Mock
        class Harness(AccountControllerMixin): pass
        app=Harness();app.account_generation=0;app.account_id='42';app.account_shell_service=AccountShellService(Repository());app.profile_service=SimpleNamespace(persist_profile=Mock())
        profile={'account_id':'42','login':'me'};app.oauth_client=SimpleNamespace(request=Mock(return_value=profile))
        await app._check_session()
        app.oauth_client.request.assert_called_once_with('GET','/v1/me',timeout=10.0)
        app.profile_service.persist_profile.assert_called_once_with(app.oauth_client,profile)
