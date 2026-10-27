import unittest
from ft_tui.api.goals_types import goals_response


class GoalsTypesTests(unittest.TestCase):
    def test_scope_dates_and_flags_are_validated(self):
        value = dict(account_id='42', cursus_id=21, status='available', stale=False,
                     collected_at='2026-10-22T12:00:00Z', cc_validated=False, probationary_period=False,
                     next_milestone='2026-10-31', cc_eta='2027-10-18',
                     edtrax_weeks=[dict(name='W-1', hours=32, text='Medium')])
        self.assertEqual(goals_response(value, '42', 21), value)
        for update in [dict(account_id='9'), dict(cursus_id=9), dict(stale='false'),
                       dict(cc_validated=0), dict(next_milestone='2026-02-31'),
                       dict(edtrax_weeks=[dict(name='W-1', hours=float('nan'), text='bad')])]:
            with self.assertRaises(ValueError):
                goals_response({**value, **update}, '42', 21)
