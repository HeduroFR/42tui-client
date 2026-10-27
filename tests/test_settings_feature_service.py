"""Headless settings drafts preserve saved keys and account-scoped choices."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from ft_tui.features.settings.service import SettingsService
from ft_tui.services.curriculum_selection import preference_key

class Repository:
    def __init__(self): self.values={}; self.writes=[]
    def get(self,key,default=''): return self.values.get(key,default)
    def save(self,values): self.writes.append(dict(values)); self.values.update(values)

class SettingsServiceTests(unittest.TestCase):
    def test_relative_root_is_rejected_before_persistence(self):
        repository=Repository()
        with self.assertRaisesRegex(ValueError,'absolute projects folder'):
            SettingsService(repository).save({'projects_root':'relative/path'},account_id='42')
        self.assertEqual(repository.writes,[])

    def test_preparation_is_pure_and_does_not_create_projects_directory(self):
        repository=Repository()
        with TemporaryDirectory() as directory:
            root=Path(directory)/'not-created'
            values=SettingsService(repository).prepare({'projects_root':str(root),'favorite_editor':'zed','default_cursus_id':'21'})
            self.assertFalse(root.exists())
            self.assertEqual(repository.writes,[])
            self.assertEqual(values['favorite_editor'],'zed')
            self.assertEqual(values['default_cursus_source'],'manual')

    def test_save_uses_single_atomic_write_and_exact_account_keys(self):
        repository=Repository(); service=SettingsService(repository)
        values=service.save({'projects_root':'/tmp/projects','default_cursus_id':'21','campus_id':44,'track':'new',
                            'username_gradient':'off','image_mode':'auto','automatic_updates':'false'},account_id='42',campus_id=31)
        self.assertEqual(repository.writes,[values])
        self.assertEqual(values[preference_key('42',21,None,'campus')],'44')
        self.assertEqual(values[preference_key('42',21,44,'track')],'new')
        self.assertNotIn('campus_id',values); self.assertNotIn('track',values)
        self.assertEqual(service.track('42',21,44),'new')
        self.assertEqual(service.track('other',21,44),'')

    def test_automatic_cursus_clears_source_and_avoids_account_preferences(self):
        values=SettingsService(Repository()).prepare({'projects_root':'/tmp/p','default_cursus_id':None,'track':'auto'},account_id='42',campus_id=31)
        self.assertEqual(values['default_cursus_id'],'')
        self.assertEqual(values['default_cursus_source'],'')
        self.assertFalse(any(key.startswith('catalog_') for key in values))

    def test_blank_root_defaults_to_home_and_fallback_campus_is_preserved(self):
        values=SettingsService(Repository()).prepare({'projects_root':' ','default_cursus_id':'21','track':'auto'},account_id='42',campus_id=31)
        self.assertEqual(values['projects_root'],str(Path.home()/'42'))
        self.assertEqual(values[preference_key('42',21,None,'campus')],'31')
        self.assertEqual(values[preference_key('42',21,31,'track')],'')

    def test_campus_options_deduplicate_validate_sort_and_retain_missing_saved_choice(self):
        service=SettingsService(Repository())
        options,selected=service.campus_choices([
            {'id':2,'country':'Spain','city':'Barcelona'}, {'id':1,'name':'Paris'},
            {'id':True,'name':'Bad'}, {'id':2,'name':'Duplicate'}, {'id':0}],[],campus_id=44,fallback_label='Saved campus')
        self.assertEqual(options,[('Paris','1'),('Spain - Barcelona','2'),('Saved campus','44')])
        self.assertEqual(selected,'44')

    def test_account_primary_choice_uses_directory_without_mutating_account_list(self):
        service=SettingsService(Repository()); accounts=[{'id':2,'is_primary':True}]
        options,selected=service.campus_choices([{'id':1,'name':'Paris'},{'id':2,'name':'Barcelona'}],accounts)
        self.assertEqual(options,[('Barcelona','2'),('Paris','1')]); self.assertEqual(selected,'2')
        self.assertEqual(accounts,[{'id':2,'is_primary':True}])
        self.assertEqual(service.campus_choices([],[]),([],None))

class SettingsPersistenceTests(unittest.TestCase):
    def test_sqlite_adapter_commits_all_keys_and_rolls_back_failed_transaction(self):
        from ft_tui.db.database import make_session_factory
        from ft_tui.features.settings.adapters.sqlite import SqliteSettingsRepository
        from sqlalchemy.exc import IntegrityError
        factory=make_session_factory('sqlite:///:memory:')
        try:
            repository=SqliteSettingsRepository(factory)
            service=SettingsService(repository)
            service.save_values({'first':'original','second':'second'})
            self.assertEqual(service.get('first'),'original')
            self.assertEqual(service.get('absent','fallback'),'fallback')
            with self.assertRaises(IntegrityError):
                service.save_values({'first':'updated','broken':None})
            self.assertEqual(service.get('first'),'original')
            self.assertEqual(service.get('broken','absent'),'absent')
        finally:
            factory.kw['bind'].dispose()

    def test_legacy_modules_preserve_shared_helper_and_view_patch_identity(self):
        from importlib import import_module
        from unittest.mock import patch
        for old,new in [('ft_tui.ui.settings','ft_tui.features.settings.views.workspace'),
                        ('ft_tui.services.user_settings','ft_tui.features.settings.adapters.storage')]:
            self.assertIs(import_module(old),import_module(new))
        with patch('ft_tui.services.user_settings.UserConfig', sentinel := object()):
            self.assertIs(import_module('ft_tui.features.settings.adapters.storage').UserConfig,sentinel)
