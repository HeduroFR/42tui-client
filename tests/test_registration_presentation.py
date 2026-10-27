import unittest
from datetime import datetime,timezone,timedelta
from registration_fixtures import registration_state,operation
from ft_tui.features.projects.registration.presentation import registration_view

class RegistrationPresentationTests(unittest.TestCase):
 def test_completed_projects_hide_registration_eligibility(self):
  for eligibility in ('available','unavailable','unknown'):
   for stale in (False,True):
    with self.subTest(eligibility=eligibility,stale=stale):
     state=registration_state();state['relationship']['state']='completed'
     state['eligibility']['state']=eligibility
     state['sources']['registration']['stale']=stale
     view=registration_view(state,now=datetime.now(timezone.utc),language='en')
     self.assertEqual(view.relationship,'Completed')
     self.assertEqual(view.eligibility,'')
     self.assertEqual(view.action,'none')

 def test_unknown_grant_disables_native_registration(self):
  state=registration_state();now=datetime.now(timezone.utc)
  self.assertEqual(registration_view(state,now=now,language='en').action,'register')
  state['capability']={'mode':'intra','reason_code':'scope_unknown'}
  self.assertEqual(registration_view(state,now=now,language='en').action,'register')
  state['intra_url']=None
  self.assertFalse(registration_view(state,now=now,language='en').enabled)
 def test_expiry_stale_absence_and_existing_attempt_never_enable_register(self):
  state=registration_state();later=datetime.now(timezone.utc)+timedelta(minutes=6)
  self.assertEqual(registration_view(state,now=later,language='en').action,'register')
  state['relationship']['state']='registered'
  self.assertEqual(registration_view(state,now=datetime.now(timezone.utc),language='en').action,'none')
 def test_uncertain_operation_blocks_writes_but_confirmed_success_remains_visible(self):
  state=registration_state();state['operation']=operation('outcome_unknown')
  view=registration_view(state,now=datetime.now(timezone.utc),language='en')
  self.assertEqual(view.action,'refresh');self.assertIn('unknown',view.feedback.lower())
  state['operation']=operation('registered');state['relationship']['state']='in_progress'
  self.assertEqual(registration_view(state,now=datetime.now(timezone.utc),language='en').action,'none')
 def test_current_registration_takes_precedence_over_a_rejected_request_notice(self):
  state=registration_state();state['relationship']['state']='in_progress';state['operation']=operation('rejected');state['operation']['reason_code']='validation_rejected'
  view=registration_view(state,now=datetime.now(timezone.utc),language='en')
  self.assertEqual(view.action,'none');self.assertEqual(view.feedback,'')

 def test_unconfirmed_eligibility_allows_solo_registration(self):
  state=registration_state();state['project_mode']='solo';state['eligibility']['state']='unknown'
  view=registration_view(state,now=datetime.now(timezone.utc),language='en')
  self.assertEqual(view.action,'register');self.assertTrue(view.enabled)
  self.assertIn('unconfirmed',view.eligibility.lower())
 def test_group_and_unknown_modes_allow_native_registration(self):
  for mode in ('group','unknown'):
   state=registration_state();state['project_mode']=mode
   self.assertEqual(registration_view(state,now=datetime.now(timezone.utc),language='en').action,'register')

 def test_missing_permissions_disable_register_with_feedback(self):
  state=registration_state();state['capability']={'mode':'intra','reason_code':'scope_missing'}
  view=registration_view(state,now=datetime.now(timezone.utc),language='en')
  self.assertEqual(view.action,'register');self.assertFalse(view.enabled)
  self.assertTrue(view.feedback)
