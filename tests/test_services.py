from datetime import date, datetime, timedelta
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Cursus, DevNote, Project, ProjectCursus, TimeLog
from ft_tui.features.projects.adapters.git import inspect_repository
from ft_tui.features.projects.adapters.checkout import CheckoutSetupError, setup_project_checkout
from ft_tui.features.catalog.adapters.cursuses import load_cursus_projects, sync_cursuses
from ft_tui.features.worklog.adapters.accounting import record_heartbeat, tracked_seconds
from ft_tui.api.client_interface import CursusSnapshot


class CheckoutTests(unittest.TestCase):
    def test_relative_path_is_rejected_before_git_runs(self):
        with patch("ft_tui.features.projects.adapters.git.subprocess.run") as run:
            with self.assertRaisesRegex(CheckoutSetupError, "must be absolute"):
                setup_project_checkout("relative-project")
            run.assert_not_called()

    def test_empty_checkout_can_be_configured_twice(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            first = setup_project_checkout(root)
            second = setup_project_checkout(root)
            self.assertTrue(first.created_repository)
            self.assertFalse(second.created_repository)
            self.assertEqual((root / ".gitignore").read_text().count("*.pdf"), 1)
            self.assertIsNone(inspect_repository(root).error)

    def test_nonempty_directory_is_preserved(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "main.c"
            source.write_text("int main(void) { return 0; }\n")
            with self.assertRaisesRegex(CheckoutSetupError, "not empty"):
                setup_project_checkout(root)
            self.assertFalse((root / ".git").exists())
            self.assertEqual(source.read_text(), "int main(void) { return 0; }\n")

    def test_inspection_reports_permission_errors(self):
        with TemporaryDirectory() as directory:
            setup_project_checkout(directory)
            with patch.object(Path, "iterdir", side_effect=PermissionError):
                snapshot = inspect_repository(directory)
            self.assertEqual(snapshot.error, "Could not access the project repository")


class ActivityTests(unittest.TestCase):
    def test_activity_is_credited_across_editors_with_idle_cutoff(self):
        factory = make_session_factory("sqlite:///:memory:")
        with TemporaryDirectory() as directory, factory() as session:
            project = Project(slug="demo", name="Demo", local_path=directory)
            session.add(project)
            session.commit()
            file = Path(directory) / "main.c"
            start = datetime(2026, 1, 1)
            record_heartbeat(session, file, editor="vscode", occurred_at=start)
            _, credited = record_heartbeat(
                session, file, editor="zed", occurred_at=start + timedelta(seconds=30)
            )
            self.assertEqual(credited, 30)
            _, credited = record_heartbeat(
                session, file, occurred_at=start + timedelta(seconds=300)
            )
            self.assertEqual(credited, 0)
            self.assertEqual(tracked_seconds(session, project.id), 30)


class ProjectSyncPreservationTests(unittest.TestCase):
    def test_load_cursus_projects_filters_associations_and_keeps_legacy_rows_for_no_filter(self):
        factory = make_session_factory("sqlite:///:memory:")
        with factory() as session:
            sync_cursuses(session, [CursusSnapshot(id=21, name="42cursus"), CursusSnapshot(id=7, name="Piscine")])
            shared = Project(slug="shared", name="Shared")
            selected = Project(slug="selected", name="Selected")
            legacy = Project(slug="legacy", name="Legacy")
            session.add_all([shared, selected, legacy])
            session.flush()
            session.add_all([
                ProjectCursus(project_id=shared.id, cursus_id=21),
                ProjectCursus(project_id=shared.id, cursus_id=7),
                ProjectCursus(project_id=selected.id, cursus_id=21),
            ])
            session.commit()

            self.assertEqual(
                {project.slug for project in load_cursus_projects(session, 21)},
                {"shared", "selected"},
            )
            self.assertEqual(
                {project.slug for project in load_cursus_projects(session, 7)},
                {"shared"},
            )
            self.assertEqual(
                {project.slug for project in load_cursus_projects(session, None)},
                {"shared", "selected", "legacy"},
            )

    def test_sync_cursuses_upserts_metadata_without_removing_unreturned_cursus(self):
        factory = make_session_factory("sqlite:///:memory:")
        with factory() as session:
            sync_cursuses(session, [CursusSnapshot(id=21, name="42cursus")])
            sync_cursuses(session, [CursusSnapshot(id=21, name="42cursus updated")])

            session.add(Cursus(id=7, name="Piscine"))
            session.commit()

            self.assertEqual(
                [(item.id, item.name) for item in session.query(Cursus).order_by(Cursus.id)],
                [(7, "Piscine"), (21, "42cursus updated")],
            )






class DefaultCursusSelectionTests(unittest.TestCase):
    def test_prefers_the_active_membership_with_the_latest_begin_date(self):
        from ft_tui.features.accounts.cursus import select_default_cursus

        result = select_default_cursus(
            [
                CursusSnapshot(21, "old", datetime(2022, 1, 1), datetime(2025, 1, 1)),
                CursusSnapshot(7, "active", datetime(2024, 1, 1), None),
                CursusSnapshot(9, "future end", datetime(2025, 1, 1), datetime(2027, 1, 1)),
            ],
            today=date(2026, 10, 20),
        )
        self.assertEqual(result.id, 9)

    def test_falls_back_to_latest_membership_when_all_memberships_ended(self):
        from ft_tui.features.accounts.cursus import select_default_cursus

        result = select_default_cursus(
            [
                CursusSnapshot(21, "older", datetime(2022, 1, 1), datetime(2023, 1, 1)),
                CursusSnapshot(7, "latest", datetime(2024, 1, 1), datetime(2025, 1, 1)),
            ],
            today=date(2026, 10, 20),
        )
        self.assertEqual(result.id, 7)

    def test_breaks_equal_and_null_begin_date_ties_by_lowest_numeric_id(self):
        from ft_tui.features.accounts.cursus import select_default_cursus

        tied = select_default_cursus(
            [
                CursusSnapshot(21, "higher", datetime(2024, 1, 1), None),
                CursusSnapshot(7, "lower", datetime(2024, 1, 1), None),
            ],
            today=date(2026, 10, 20),
        )
        null_dates = select_default_cursus(
            [CursusSnapshot(21, "higher", None), CursusSnapshot(7, "lower", None)],
            today=date(2026, 10, 20),
        )
        self.assertEqual(tied.id, 7)
        self.assertEqual(null_dates.id, 7)

    def test_null_begin_date_sorts_before_a_real_date(self):
        from ft_tui.features.accounts.cursus import select_default_cursus

        result = select_default_cursus(
            [
                CursusSnapshot(7, "undated", None),
                CursusSnapshot(21, "dated", datetime(2020, 1, 1)),
            ],
            today=date(2026, 10, 20),
        )
        self.assertEqual(result.id, 21)

    def test_active_main_cursus_wins_over_piscine_with_missing_or_later_dates(self):
        from ft_tui.features.accounts.cursus import select_default_cursus

        for main_name in ("42cursus", "42 Cursus", "42"):
            for piscine_begin in (None, datetime(2026, 10, 1)):
                with self.subTest(main=main_name, piscine_begin=piscine_begin):
                    result = select_default_cursus(
                        [CursusSnapshot(9, "C Piscine", piscine_begin),
                         CursusSnapshot(21, main_name, None)],
                        today=date(2026, 10, 23),
                    )
                    self.assertEqual(result.id, 21)

    def test_returns_none_for_empty_membership_list(self):
        from ft_tui.features.accounts.cursus import select_default_cursus

        self.assertIsNone(select_default_cursus([], today=date(2026, 10, 20)))


if __name__ == "__main__":
    unittest.main()
