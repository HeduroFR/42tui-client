"""The SQLite adapter owns atomic publication and closes its own sessions."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from sqlalchemy import select
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Project
from ft_tui.features.catalog.models import CatalogScope
from ft_tui.features.catalog.adapters.sqlite import SqliteCatalogRepository


def page(name='One', snapshot='old'):
    return {'snapshot_id': snapshot, 'items': [{'project_id': 1, 'slug': 'one', 'name': name}],
            'meta': {'cursus_id': 21, 'campus_id': 31}}


class CatalogRepositoryTests(unittest.TestCase):
    def test_complete_snapshot_survives_repository_and_engine_reconstruction(self):
        with TemporaryDirectory() as directory:
            url = f'sqlite:///{Path(directory)/"catalog.sqlite"}'
            factory = make_session_factory(url)
            scope = CatalogScope(21, 31)
            try:
                SqliteCatalogRepository(factory).publish(scope, [(page(), {})], 'old', {1})
            finally:
                factory.kw['bind'].dispose()
            restored = make_session_factory(url)
            try:
                self.assertEqual(SqliteCatalogRepository(restored).cached(scope)['snapshot_id'], 'old')
            finally:
                restored.kw['bind'].dispose()

    def test_failed_publication_rolls_back_all_pages_and_keeps_complete_snapshot(self):
        factory = make_session_factory('sqlite:///:memory:')
        scope = CatalogScope(21, 31)
        try:
            repo = SqliteCatalogRepository(factory)
            repo.publish(scope, [(page(), {})], 'old', {1})
            broken = {**page(snapshot='new'), 'items': [{'project_id': 2}]}
            with self.assertRaises(KeyError):
                repo.publish(scope, [(page('Changed', 'new'), {}), (broken, {})], 'new', {1, 2})
            self.assertEqual(repo.cached(scope)['snapshot_id'], 'old')
            with factory() as session:
                self.assertEqual(session.scalar(select(Project)).name, 'One')
        finally:
            factory.kw['bind'].dispose()
