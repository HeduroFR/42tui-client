"""Dashboard view models compose portable values without Textual or SQLite."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from ft_tui.features.dashboard.models import DashboardProject
from ft_tui.features.dashboard.service import DashboardService


class Reader:
    def tracked(self, project_id): return 3660
    def recent_notes(self): return [(7, 99, 'Outside', 'Latest note', datetime(2026, 10, 26))]
    def heartbeats_since(self, start): return [(datetime(2026, 10, 26, 10), 120), (datetime(2026, 10, 26, 11), 180)]
    def activity(self): return {1: datetime(2026, 10, 26, 12)}, (1, datetime(2026, 10, 26, 12))


def project(id, status='available', track='new', section='common-core'):
    return DashboardProject(id=id, ui_key=f'api:{id}', name=f'Project {id}', status=status,
                            local_path=None, official_project_id=id,
                            catalog_data={'track': track, 'section': section, 'rank': 0})


class DashboardServiceTests(unittest.TestCase):
    def setUp(self):
        self.service = DashboardService(Reader(), folder_exists=lambda path: bool(path))
        self.now = datetime(2026, 10, 27, 12, tzinfo=timezone.utc)
        self.curriculum = {'selected_track': {'track': 'new'}, 'selected_rank': {'rank': 0, 'source': 'quest'}}

    def compose(self, rows, **overrides):
        values = dict(projects=rows, profile={}, goals={}, curriculum=self.curriculum,
                      activity={}, active_project_id=None, selected_project_key=None, now=self.now)
        values.update(overrides)
        return self.service.compose(**values)

    def test_completed_active_project_is_never_resumed_and_selected_pending_can_be(self):
        model = self.compose([project(1, 'completed'), project(2, 'in_progress')], active_project_id=1, selected_project_key='api:1')
        self.assertEqual(model.resume.ui_key, 'api:2')
        self.assertEqual(model.resume_seconds, 3660)
        self.assertEqual(model.activity_label, 'READY TO RESUME')
        self.assertIsNone(self.compose([project(1, 'done')]).resume)

    def test_active_then_recent_activity_take_priority_over_selection(self):
        rows = [project(1), project(2, 'in_progress'), project(3)]
        model = self.compose(rows, active_project_id=2, selected_project_key='api:3')
        self.assertEqual((model.resume.id, model.activity_label), (2, 'ACTIVE NOW'))
        model = self.compose(rows, activity={1: self.now.replace(tzinfo=None)}, selected_project_key='api:3')
        self.assertEqual((model.resume.id, model.activity_label), (1, 'RECENT ACTIVITY'))

    def test_exams_are_never_resumed_even_when_active_recent_or_selected(self):
        for data in ({'kind': 'exam', 'slug': 'exam-rank-02'},
                     {'kind': 'project', 'slug': 'exam-rank-02'}):
            exam = replace(project(1, 'in_progress'), catalog_data=data)
            normal = project(2)
            for overrides in ({'active_project_id': 1},
                              {'activity': {1: self.now.replace(tzinfo=None)}},
                              {'selected_project_key': 'api:1'}, {}):
                with self.subTest(data=data, overrides=overrides):
                    self.assertEqual(self.compose([exam, normal], **overrides).resume.id, 2)
                    self.assertIsNone(self.compose([exam], **overrides).resume)
            # Exams still contribute to the curriculum; only resumption is filtered.
            exam = replace(exam, catalog_data={**normal.catalog_data, **data})
            self.assertEqual(self.compose([exam, normal]).journey.total, 2)

    def test_wallet_zero_is_preserved_and_invalid_stats_are_absent(self):
        model = self.compose([], profile={'wallet': 0, 'correction_point': True, 'location': ' host '})
        self.assertEqual(model.stats.wallet, 0)
        self.assertIsNone(model.stats.correction_points)
        self.assertEqual(model.stats.location, ' host ')

    def test_journey_uses_track_and_current_goals_completion(self):
        rows = [project(1, 'completed'), project(2, 'in_progress'), project(3, track='old'),
                project(4, 'available', section='specialization')]
        model = self.compose(rows)
        self.assertEqual((model.journey.total, model.journey.completed, model.journey.next_name), (2, 1, 'Project 2'))
        model = self.compose(rows, goals={'status': 'available', 'cc_validated': True})
        self.assertEqual((model.journey.total, model.journey.next_name), (1, 'Project 4'))

    def test_notes_resolve_local_fallback_and_activity_covers_four_weeks(self):
        model = self.compose([project(1)])
        self.assertEqual(model.recent_notes[0][1], 'local:99')
        self.assertEqual(len(model.week_starts), 4)
        self.assertEqual(len(model.day_seconds), 28)
        self.assertEqual(model.week_seconds[model.week_starts[-1]], 300)
        self.assertEqual(model.day_seconds[self.now.date()-timedelta(days=1)], 300)

    def test_deadline_uses_current_rank_and_in_progress_over_available(self):
        model = self.compose([project(1), project(2, 'in_progress')])
        self.assertEqual(model.deadline.milestone, 'Rank 00')
        self.assertEqual(model.deadline.next_label, 'Project 2 · In progress')
        self.assertEqual(len(model.setup_candidates), 2)

    def test_active_heartbeat_timeout_includes_boundary_and_rejects_future(self):
        at = datetime(2026, 10, 26, 12, tzinfo=timezone.utc)
        self.assertEqual(self.service.activity(at+timedelta(seconds=120)).active_project_id, 1)
        self.assertIsNone(self.service.activity(at+timedelta(seconds=121)).active_project_id)
        self.assertIsNone(self.service.activity(at-timedelta(seconds=1)).active_project_id)
