"""Automatic personal ranks and curriculum-scoped catalogue browsing."""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ft_tui.db.database import make_session_factory
from ft_tui.services.curriculum_selection import preference_key
from ft_tui.services.user_settings import get_setting, save_settings
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.ui.components import Input, ListView, ProjectEntry, ProjectRankHeader, Select, TabbedContent


FULL_CATALOG_QUERIES = [
    {'track': 'old', 'limit': 100, 'cursor': None},
    {'track': 'new', 'limit': 100, 'cursor': None},
    {'section': 'other', 'limit': 100, 'cursor': None},
]


def project(project_id, rank, track):
    return {'project_id': project_id, 'slug': f'p{project_id}', 'name': f'P{project_id}',
            'kind': 'project', 'xp': 100, 'duration': None, 'rank': rank,
            'track': track, 'section': 'common-core', 'section_source': 'rules',
            'evidence_status': 'inferred'}


class RankProvider:
    rows = [project(1, 0, 'shared'), project(2, 1, 'new'), project(3, 1, 'shared'),
            project(4, 1, 'old'), project(5, 2, 'new'),
            {**project(6, None, 'new'), 'section': 'specialization'},
            {**project(7, None, 'shared'), 'section': 'specialization'},
            {**project(8, None, 'old'), 'section': 'specialization'}]

    def __init__(self, rank=None):
        self.queries = []
        self.rank = rank or {'rank': None, 'source': 'unknown'}

    def get_curriculum(self, scope):
        return {'account_id': '42', 'cursus_id': 21, 'campus_id': 31,
                'track': {'track': 'new', 'source': 'quest'},
                'rank': self.rank,
                'registration': {'status': 'unknown', 'project_ids': [], 'stale': True}}

    def get_account_projects(self, *args):
        return {'account_id': '42', 'snapshot_id': 'personal', 'next_cursor': None,
                'items': [{'id': 10, 'project_id': 1, 'slug': 'p1', 'name': 'P1',
                           'cursus_ids': [21], 'status': 'in_progress'}]}

    def list_branches(self, *args):
        return {'snapshot_id': 'graph', 'items': [], 'next_cursor': None}

    def list_catalog_page(self, scope, **query):
        self.queries.append(query)
        rows = [row for row in self.rows if query.get('track') is None or row['track'] in (query['track'], 'shared')]
        if query.get('project_ids'):
            ids={int(value) for value in query['project_ids'].split(',')}
            rows=[row for row in rows if row['project_id'] in ids]
        if query.get('kind'):
            rows = [row for row in rows if row['kind'] == query['kind']]
        if query.get('q'):
            rows = [row for row in rows if query['q'].casefold() in row['name'].casefold()]
        if query.get('section'):
            rows = [row for row in rows if row['section'] == query['section']]
        if query.get('rank') is not None:
            rows = [row for row in rows if row['rank'] == query['rank']]
        return {'snapshot_id': 'graph', 'items': rows, 'next_cursor': None,
                'meta': {'cursus_id': 21, 'campus_id': 31}}

    def get_catalog_project(self, project_id, *args):
        return {**next(row for row in self.rows if row['project_id'] == project_id),
                'snapshot_id': 'graph', 'clauses': [], 'rules': '', 'description': ''}


class ProjectRankUiTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_rank_loads_inactive_projects_from_the_full_common_core(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "unknown.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21'})
            app = FortyTwoTuiApp(factory, None)
            provider = RankProvider()
            try:
                async with app.run_test(size=(100, 40)):
                    app.account_id = '42'
                    app.account_campuses = [{'id': 31, 'is_primary': True}]
                    app.account_connected = True
                    app.provider = provider
                    await app._refresh_catalog_context(provider, app.account_generation)
                    self.assertIsNone(app.project_curriculum['selected_rank']['rank'])
                    self.assertEqual({p.official_project_id for p in app._visible_projects()}, {1, 2, 3, 5})
                    inactive = next(p for p in app._visible_projects() if p.official_project_id == 3)
                    self.assertFalse(inactive.progress_data)
                    self.assertEqual(provider.queries, FULL_CATALOG_QUERIES)
                    self.assertEqual(len(app.projects), len(provider.rows))
            finally:
                factory.kw['bind'].dispose()

    async def test_type_filters_browse_the_track_beyond_current_rank_and_section(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "types.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21'})
            app = FortyTwoTuiApp(factory, None)
            provider = RankProvider()
            provider.rows = provider.rows + [
                {**project(9, 2, 'new'), 'kind': 'exam'},
                {**project(10, 2, 'old'), 'kind': 'exam'},
                {**project(11, None, 'shared'), 'kind': 'piscine', 'section': 'specialization'},
                {**project(12, None, 'new'), 'kind': 'rush', 'section': 'specialization'},
                {**project(13, None, 'shared'), 'kind': 'big_project', 'section': 'specialization'},
            ]
            try:
                async with app.run_test(size=(80, 24)) as pilot:
                    await pilot.pause()
                    app.account_id = '42'
                    app.account_campuses = [{'id': 31, 'is_primary': True}]
                    app.account_connected = True
                    app.provider = provider
                    await app._refresh_catalog_context(provider, app.account_generation)
                    self.assertIsNone(app.project_curriculum['selected_rank']['rank'])
                    for kind, ids in [('exam', {9}), ('piscine', {11}), ('rush', {12}),
                                      ('big_project', {13}), ('project', {1, 2, 3, 5, 6, 7})]:
                        provider.queries.clear()
                        app.query_one('#project-kind', Select).value = kind
                        await pilot.pause(.5)
                        self.assertEqual({p.official_project_id for p in app._visible_projects()}, ids)
                        self.assertEqual(provider.queries, [])
                    app.query_one('#project-kind', Select).value = 'exam'
                    app.query_one('#project-view', Select).value = 'all'
                    await pilot.pause(.5)
                    self.assertEqual({p.official_project_id for p in app._visible_projects()}, {9})
                    app.query_one('#project-kind', Select).value = 'piscine'
                    await pilot.pause(.5)
                    self.assertEqual(app._visible_projects(), [])
                    app.query_one('#project-view', Select).value = 'relevant'
                    await pilot.pause(.5)
                    self.assertEqual({p.official_project_id for p in app._visible_projects()}, {11})
                    app.query_one('#project-search', Input).value = 'nothing-matches'
                    await pilot.pause(.5)
                    self.assertEqual(app._visible_projects(), [])
            finally:
                factory.kw['bind'].dispose()

    async def test_inferred_first_rank_automatically_loads_current_and_next_projects(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "inferred.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21'})
            app = FortyTwoTuiApp(factory, None)
            provider = RankProvider({'rank': 0, 'source': 'project', 'completed': False})
            try:
                async with app.run_test(size=(80, 24)) as pilot:
                    await pilot.pause()
                    app.account_id = '42'
                    app.account_campuses = [{'id': 31, 'is_primary': True}]
                    app.account_connected = True
                    app.provider = provider
                    await app._refresh_catalog_context(provider, app.account_generation)
                    self.assertEqual(app.project_curriculum['selected_rank']['source'], 'project')
                    self.assertEqual({p.official_project_id for p in app._visible_projects()}, {1, 2, 3})
                    self.assertEqual(provider.queries, FULL_CATALOG_QUERIES)
                    self.assertEqual([p.official_project_id for p in app._visible_projects()], [1, 2, 3])
                    self.assertEqual([header.rank for header in app.query(ProjectRankHeader)], [0, 1])
                    self.assertTrue(all(header.collapsed for header in app.query(ProjectRankHeader)))
                    self.assertEqual(list(app.query(ProjectEntry)), [])
                    self.assertFalse(app.query('#project-api-status'))
                    self.assertFalse(app.query('#project-list-hint'))
                    app.query_one(TabbedContent).active = 'projects-tab'
                    await pilot.pause()
                    listing = app.query_one('#project-list-view', ListView)
                    listing.focus()
                    listing.index = 0
                    await pilot.press('enter')
                    await pilot.pause()
                    self.assertEqual([row.project.official_project_id for row in listing.children
                                      if isinstance(row, ProjectEntry)], [1])
                    self.assertIsInstance(listing.highlighted_child, ProjectRankHeader)
                    self.assertFalse(listing.highlighted_child.collapsed)
                    await app._refresh_activity_order()
                    self.assertFalse(listing.highlighted_child.collapsed)
                    await pilot.press('enter')
                    await pilot.pause()
                    self.assertEqual([row.project.official_project_id for row in listing.children
                                      if isinstance(row, ProjectEntry)], [])
                    await pilot.press('enter')
                    await pilot.pause()
                    listing.index = 1
                    await pilot.pause()
                    self.assertEqual(app.selected_project_key, listing.highlighted_child.key)

                    self.assertFalse(app.query('#project-rank'))
                    self.assertFalse(app.query('#cc-current-rank'))
                    self.assertGreater(app.query_one('#project-list-view', ListView).size.height, 0)
                    with factory() as session:
                        self.assertEqual(get_setting(session, preference_key('42', 21, 31, 'rank')), '')
            finally:
                factory.kw['bind'].dispose()

    async def test_all_projects_follows_curriculum_stage_and_ignores_saved_manual_rank(self):
        with TemporaryDirectory() as directory:
            factory = make_session_factory(f'sqlite:///{Path(directory) / "stage.sqlite"}')
            with factory() as session:
                save_settings(session, {'onboarding_completed': 'true', 'default_cursus_id': '21',
                    'project_view_21': 'history', preference_key('42', 21, 31, 'rank'): '5'})
            app = FortyTwoTuiApp(factory, None)
            provider = RankProvider()
            try:
                async with app.run_test(size=(80, 24)) as pilot:
                    await pilot.pause()
                    app.account_id = '42'
                    app.account_campuses = [{'id': 31, 'is_primary': True}]
                    app.account_connected = True
                    app.provider = provider
                    await app._refresh_catalog_context(provider, app.account_generation)
                    self.assertEqual(app.query_one('#project-view', Select).value, 'relevant')
                    app.query_one('#project-view', Select).value = 'all'
                    await pilot.pause(.5)
                    self.assertIsNone(app.project_curriculum['selected_rank']['rank'])
                    self.assertEqual({p.official_project_id for p in app._visible_projects()}, {1, 2, 3, 5})
                    self.assertEqual(provider.queries, FULL_CATALOG_QUERIES)
                    self.assertNotIn('history', {value for _, value in app._project_view_options(21)})
                    provider.queries.clear()
                    provider.rank = {'rank': 6, 'source': 'quest', 'completed': True}
                    await app._refresh_catalog_context(provider, app.account_generation)
                    self.assertEqual({p.official_project_id for p in app._visible_projects()}, {6, 7})
                    self.assertEqual(provider.queries, [])
                    self.assertGreater(app.query_one('#project-list-view', ListView).size.height, 0)
                    app.query_one('#project-view', Select).value = 'relevant'
                    await pilot.pause(.5)
                    self.assertEqual(app.project_curriculum['selected_rank']['rank'], 6)
            finally:
                factory.kw['bind'].dispose()

    async def test_completing_a_rank_keeps_history_and_loads_the_next_rank(self):
        class CompletedRankProvider(RankProvider):
            def get_account_projects(self,*args):
                ids=[1] if self.rank['rank']==1 else [1,2,3]
                return {'account_id':'42','snapshot_id':'personal','next_cursor':None,
                        'items':[{'id':100+id,'project_id':id,'slug':f'p{id}','name':f'P{id}',
                                  'cursus_ids':[21],'status':'finished','validated':True,
                                  'final_mark':100,'vogsphere_url':None} for id in ids]}
        with TemporaryDirectory() as directory:
            factory=make_session_factory(f'sqlite:///{Path(directory)/"completed.sqlite"}')
            with factory() as session:
                save_settings(session,{'onboarding_completed':'true','default_cursus_id':'21'})
            app=FortyTwoTuiApp(factory,None)
            provider=CompletedRankProvider({'rank':1,'source':'project','completed':False})
            provider.rows=RankProvider.rows+[project(9,3,'new')]
            try:
                async with app.run_test(size=(100,35)) as pilot:
                    await pilot.pause()
                    app.account_id='42';app.account_campuses=[{'id':31,'is_primary':True}]
                    app.account_connected=True;app.provider=provider
                    await app._refresh_catalog_context(provider,app.account_generation)
                    self.assertEqual(provider.queries,FULL_CATALOG_QUERIES)
                    self.assertEqual({p.official_project_id for p in app._visible_projects()},{1,2,3,5})
                    provider.rank={'rank':2,'source':'project','completed':False};provider.queries.clear()
                    await app._refresh_catalog_context(provider,app.account_generation)
                    self.assertEqual(provider.queries,[])
                    self.assertEqual({p.official_project_id for p in app._visible_projects()},{1,2,3,5,9})
                    # Historical projects retain their published rank in the fresh snapshot.
                    self.assertEqual([h.rank for h in app.query(ProjectRankHeader)],[0,1,2,3])
            finally:
                factory.kw['bind'].dispose()

    async def test_completed_rank_zero_project_is_enriched_after_snapshot_refresh(self):
        class Provider(RankProvider):
            def get_account_projects(self,*args):
                page=super().get_account_projects(*args)
                page['items'][0].update(status='finished',validated=True,final_mark=100)
                return page
            def list_catalog_page(self,scope,**query):
                if query.get('project_ids'):
                    self.queries.append(query)
                    ids={int(x) for x in query['project_ids'].split(',')}
                    return {'snapshot_id':'graph','items':[row for row in self.rows if row['project_id'] in ids],
                            'next_cursor':None,'meta':{'cursus_id':21,'campus_id':31}}
                return super().list_catalog_page(scope,**query)
        with TemporaryDirectory() as directory:
            factory=make_session_factory(f'sqlite:///{Path(directory)/"completed.sqlite"}')
            with factory() as session:
                save_settings(session,{'onboarding_completed':'true','default_cursus_id':'21'})
            app=FortyTwoTuiApp(factory,None)
            provider=Provider({'rank':1,'source':'project','completed':False})
            try:
                async with app.run_test(size=(80,24)) as pilot:
                    await pilot.pause()
                    app.account_id='42';app.account_campuses=[{'id':31,'is_primary':True}]
                    app.account_connected=True;app.provider=provider
                    await app._refresh_catalog_context(provider,app.account_generation)
                    libft=next(p for p in app._visible_projects() if p.official_project_id==1)
                    self.assertEqual(libft.catalog_data.get('rank'),0)
                    self.assertIn(0,[header.rank for header in app.query(ProjectRankHeader)])
                    with factory() as session:
                        from ft_tui.services.catalog_cache import load_context_projects
                        saved=next(p for p in load_context_projects(session,21,31,'42') if p.official_project_id==1)
                        self.assertEqual(saved.catalog_data.get('rank'),0)
            finally:factory.kw['bind'].dispose()
