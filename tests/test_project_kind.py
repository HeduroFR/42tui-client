import unittest
from ft_tui.services.project_kind import project_kind
from ft_tui.db.models import Project


class ProjectKindTests(unittest.TestCase):
    def test_legacy_types_are_normalized_without_guessing_from_display_names(self):
        for kind, slug, expected in [
            ('project', '42next-exam-rank-02', 'exam'),
            ('piscine', 'exam-rank-05', 'exam'),
            ('project', 'c-piscine-final-exam', 'exam'),
            ('project', 'c-piscine-rush-00', 'rush'),
            ('pool', 'piscine-python', 'piscine'),
            ('project', 'exam-preparation', 'project'),
            ('project', 'c-piscine-c-00', 'project'),
        ]:
            with self.subTest(slug=slug):
                self.assertEqual(project_kind(kind, slug), expected)
        project = Project(slug='exam-preparation', name='Exam Rank 02')
        project._catalog_data = {'kind': 'project'}
        self.assertEqual(project.catalog_data['kind'], 'project')
        project._catalog_data = {}
        self.assertEqual(project.catalog_data, {})
