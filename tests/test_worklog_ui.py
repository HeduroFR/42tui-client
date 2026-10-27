"""Notes remain selected after save and obsolete sidebar loads cannot overwrite."""
import asyncio
import unittest
from unittest.mock import patch
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Project
from ft_tui.services.user_settings import save_settings
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.ui.components import Input,Select,TextArea,ListView,TabbedContent

class WorklogUiTests(unittest.IsolatedAsyncioTestCase):
    async def test_saving_a_new_note_keeps_it_selected_for_the_next_edit(self):
        factory=make_session_factory('sqlite:///:memory:')
        try:
            with factory() as s:
                save_settings(s,{'onboarding_completed':'true'})
                p=Project(slug='one',name='One');s.add(p);s.commit()
            app=FortyTwoTuiApp(factory,None)
            async with app.run_test(size=(140,42)) as pilot:
                await pilot.pause()
                key=next(iter(app.projects))
                app.query_one(TabbedContent).active='dev-log'
                app.query_one('#dev-log-project',Select).value=key
                await pilot.pause()
                app._begin_new_dev_note()
                app.query_one('#dev-log-title',Input).value='Draft'
                app.query_one('#dev-log-editor',TextArea).text='# Body'
                await app._save_dev_note()
                self.assertIsNotNone(app.selected_note_id)
                first=app.selected_note_id
                self.assertEqual(app.query_one('#dev-log-editor',TextArea).text,'# Body')
                app.query_one('#dev-log-title',Input).value='Updated'
                await app._save_dev_note()
                self.assertEqual(app.selected_note_id,first)
                self.assertEqual(len(app.worklog_service.notes(app.projects[key].id)),1)
        finally:factory.kw['bind'].dispose()

    async def test_older_sidebar_load_cannot_replace_the_new_selected_project(self):
        factory=make_session_factory('sqlite:///:memory:')
        try:
            with factory() as s:
                save_settings(s,{'onboarding_completed':'true'})
                s.add_all([Project(slug='one',name='One'),Project(slug='two',name='Two')]);s.commit()
            app=FortyTwoTuiApp(factory,None)
            async with app.run_test(size=(140,42)) as pilot:
                await pilot.pause()
                one,two=list(app.projects.values())
                app.worklog_service.save_note(one.id,None,'First','one')
                app.worklog_service.save_note(two.id,None,'Second','two')
                listing=app.query_one('#dev-log-note-list',ListView)
                clear=listing.clear;started=asyncio.Event();release=asyncio.Event();first=[True]
                async def delay():
                    await clear()
                    if first[0]:first[0]=False;started.set();await release.wait()
                with patch.object(listing,'clear',side_effect=delay):
                    old=asyncio.create_task(app._load_dev_log_notes(one.ui_key))
                    try:
                        await asyncio.wait_for(started.wait(),3)
                        new=asyncio.create_task(app._load_dev_log_notes(two.ui_key))
                        await asyncio.sleep(.02)
                    finally:release.set()
                    await asyncio.gather(old,new)
                self.assertEqual(len(listing.children),1)
                self.assertIn('Two',str(app.query_one('#dev-log-status').render()))
        finally:factory.kw['bind'].dispose()
