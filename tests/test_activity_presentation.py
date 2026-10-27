import unittest
from datetime import datetime, timezone
from ft_tui.services.project_activity import format_mark, correction_phase, team_summary
from activity_fixtures import TEAM, PEER

class ActivityPresentationTests(unittest.TestCase):
    def test_missing_zero_and_bonus_marks(self):
        self.assertEqual(format_mark(None), '—')
        self.assertEqual(format_mark(0), '0%')
        self.assertEqual(format_mark(125), '125%')
    def test_pending_past_corrections_are_not_completed(self):
        now = datetime(2026, 10, 22, tzinfo=timezone.utc)
        self.assertEqual(correction_phase(PEER, now=now), 'Scheduled')
        self.assertEqual(correction_phase({**PEER, 'begin_at': '2026-01-01T00:00:00Z'}, now=now), 'Overdue · not filled')
        self.assertEqual(correction_phase({**PEER, 'begin_at': None}, now=now), 'Pending')
        self.assertEqual(correction_phase({**PEER, 'filled_at': '2026-01-01T00:00:00Z'}, now=now), 'Completed')
    def test_summary_preserves_literal_names_and_unknown_dates(self):
        value = team_summary({**TEAM, 'name': '[red]literal'}, current=True)
        self.assertIn('[red]literal', value)
        self.assertIn('125%', value)
        self.assertIn('Locked: —', value)
    def test_permission_denial_is_not_a_generic_outage(self):
        from ft_tui.services.project_activity import source_text
        text = source_text('Automated evaluations', {'status': 'unavailable', 'stale': True, 'collected_at': None, 'reason_code': 'permission_denied'})
        self.assertIn('Access denied by 42', text)
    def test_cached_observations_invite_manual_refresh(self):
        from ft_tui.services.project_activity import source_text
        value = source_text('Peer evaluations', {'status': 'available', 'stale': True, 'collected_at': '2026-01-01T00:00:00Z'})
        self.assertIn('Cached · Refresh to update', value)
        self.assertIn('2026-01-01', value)
