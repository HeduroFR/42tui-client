"""Startup snapshots preserve preference presence and first-run sequencing."""
import unittest
from ft_tui.app.startup import StartupService


class Repository:
    def __init__(self,values=None):self.values=dict(values or {});self.writes=[]
    def preferences(self,keys):return {key:self.values[key] for key in keys if key in self.values}
    def save(self,values):self.writes.append(dict(values));self.values.update(values)


class StartupServiceTests(unittest.TestCase):
    def test_first_launch_detects_language_only_when_no_legacy_preference_exists(self):
        service=StartupService(Repository())
        self.assertTrue(service.initial_preferences('fr')['first_launch'])
        self.assertEqual(service.initial_preferences('fr')['language'],'fr')
        for key in ('projects_root','favorite_editor','favorite_theme','language'):
            values=StartupService(Repository({key:''})).initial_preferences('fr')
            self.assertFalse(values['first_launch'])
            self.assertEqual(values['language'],'' if key=='language' else 'en')

    def test_invalid_campus_directory_and_offline_campuses_fallbacks(self):
        service=StartupService(Repository({'campus_directory':'not-json','catalog_last_campuses':'{','catalog_last_account':'42'}))
        values=service.initial_preferences('en')
        self.assertEqual(values['campus_directory'],[])
        self.assertEqual(values['offline_account_campuses'],[])
        self.assertEqual(values['offline_account_id'],'42')

    def test_initial_raw_modes_and_gradient_preserve_presentation_validation(self):
        values=StartupService(Repository({'image_mode':'bad','icon_mode':'none','username_gradient':'blue',
                                         'club_notification_sound':'other'})).initial_preferences('en')
        self.assertEqual(values['image_mode'],'bad');self.assertEqual(values['icon_mode'],'none')
        self.assertEqual(values['username_gradient'],'blue');self.assertFalse(values['club_notification_sound'])

    def test_mount_repairs_legacy_onboarding_once_and_retains_empty_values(self):
        repository=Repository({'favorite_editor':'','projects_root':''});service=StartupService(repository)
        values=service.mount_preferences('fr','/tmp/projects','nvim','textual-dark',21600)
        self.assertFalse(values['onboarding_pending']);self.assertEqual(values['language'],'en')
        self.assertEqual(values['favorite_editor'],'');self.assertEqual(values['projects_root'],'')
        self.assertEqual(repository.writes,[{'onboarding_completed':'true'}])
        service.mount_preferences('fr','/tmp/projects','nvim','textual-dark',21600)
        self.assertEqual(len(repository.writes),1)

    def test_pending_mount_keeps_detected_language_and_defaults(self):
        values=StartupService(Repository()).mount_preferences('fr','/tmp/projects','vim','theme',3600)
        self.assertTrue(values['onboarding_pending']);self.assertEqual(values['language'],'fr')
        self.assertEqual(values['projects_root'],'/tmp/projects');self.assertEqual(values['subject_interval'],'3600')
        self.assertEqual(values['favorite_theme'],'theme');self.assertEqual(values['favorite_subject_viewer'],'system')

    def test_finish_skip_and_values_use_single_explicit_write(self):
        repository=Repository();service=StartupService(repository)
        service.finish_onboarding('fr',None)
        self.assertEqual(repository.writes,[{'onboarding_completed':'true','language':'fr'}])
        service.finish_onboarding('fr',{'language':'en','projects_root':'/tmp/p'})
        self.assertEqual(repository.writes[-1],{'onboarding_completed':'true','language':'en','projects_root':'/tmp/p'})

    def test_saved_cursus_selection_uses_existing_truthiness(self):
        for value,expected in [('',False),('0',True),('invalid',True),('21',True)]:
            self.assertEqual(StartupService(Repository({'default_cursus_id':value})).has_saved_cursus_selection(),expected)
