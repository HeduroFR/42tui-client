import unittest
from ft_tui.services.curriculum_selection import select_track,select_rank
class SelectionTests(unittest.TestCase):
 def test_empty_evidence_requires_setting_and_never_mixes_tracks(self):
  self.assertIsNone(select_track({},None)['track'])
  self.assertEqual(select_track({},'new'),{'track':'new','source':'manual','conflict':False})
  self.assertEqual(select_track({'track':'new','source':'cohort'},'old')['track'],'old')
  self.assertEqual(select_track({'track':'new','source':'quest'},'old')['track'],'new')
  self.assertIsNone(select_rank({})['rank'])
 def test_automatic_rank_accepts_quests_and_completed_rank_project_evidence(self):
  inferred = {'rank': 0, 'source': 'project', 'completed': False}
  self.assertEqual(select_rank(inferred), inferred)
  quest = {'rank': 1, 'source': 'quest', 'completed': False}
  self.assertEqual(select_rank(quest), quest)
  self.assertEqual(select_rank({'rank': 1, 'source': 'project'}), {'rank':1,'source':'project','completed':False})
  self.assertIsNone(select_rank({'rank': -1, 'source': 'project'})['rank'])
  self.assertIsNone(select_rank({'rank': True, 'source': 'project'})['rank'])
