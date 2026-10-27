"""Update policy is headless and persists cooldown before external reads."""
import unittest
from ft_tui.features.installation.service import InstallationService


class Preferences:
    def __init__(self,values=None):self.values=dict(values or {});self.writes=[]
    def get(self,key,default=''):return self.values.get(key,default)
    def save(self,values):self.values.update(values);self.writes.append(dict(values))


class InstallationPolicyTests(unittest.TestCase):
    def test_first_launch_baselines_and_upgrades_require_acknowledgement(self):
        prefs=Preferences();service=InstallationService(prefs)
        self.assertIsNone(service.startup('0.3.0'))
        self.assertEqual(prefs.values['updates:last_seen_version'],'0.3.0')
        self.assertEqual(service.startup('0.4.0'),'0.3.0')
        self.assertEqual(prefs.values['updates:last_seen_version'],'0.3.0')
        service.acknowledge('0.4.0')
        self.assertIsNone(service.startup('0.4.0'))

    def test_downgrade_resets_baseline_without_changelog(self):
        prefs=Preferences({'updates:last_seen_version':'0.4.0'})
        self.assertIsNone(InstallationService(prefs).startup('0.3.0'))
        self.assertEqual(prefs.values['updates:last_seen_version'],'0.3.0')

    def test_cooldown_is_written_once_before_network_even_on_failed_check(self):
        prefs=Preferences();service=InstallationService(prefs)
        self.assertTrue(service.begin_check(100000))
        self.assertEqual(prefs.values['updates:last_check'],'100000')
        self.assertFalse(service.begin_check(100001))
        self.assertEqual(len(prefs.writes),1)
        self.assertTrue(service.begin_check(100000+12*60*60))

    def test_malformed_or_future_clock_does_not_block_checks(self):
        for value in ('invalid','9999999999'):
            self.assertTrue(InstallationService(Preferences({'updates:last_check':value})).begin_check(100000))

    def test_enabled_and_strict_stable_newer_policy(self):
        prefs=Preferences();service=InstallationService(prefs)
        self.assertTrue(service.enabled())
        prefs.values['automatic_updates']='false'
        self.assertFalse(service.enabled())
        for value in ('0.3.0','0.2.0','0.4.0rc1',None):self.assertFalse(service.newer(value,'0.3.0'))
        self.assertTrue(service.newer('0.4.0','0.3.0'))
