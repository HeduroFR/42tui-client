import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import datetime,timezone,timedelta
from ft_tui.db.database import make_session_factory
from ft_tui.db.models import Project
from ft_tui.features.settings.adapters.storage import save_settings
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.features.catalog.models import CatalogScope
from ft_tui.ui.components import Static,TabbedContent,Button
from registration_fixtures import registration_state,operation

class RegistrationUITests(unittest.IsolatedAsyncioTestCase):
 async def test_registration_section_actions_and_personal_heading_are_independent_of_setup(self):
  with TemporaryDirectory() as d:
   f=make_session_factory(f'sqlite:///{Path(d)/"ui.sqlite"}')
   with f() as s:
    save_settings(s,{'onboarding_completed':'true'});s.add(Project(slug='libft',name='Libft',official_project_id=1001,setup_status='completed'));s.commit()
   app=FortyTwoTuiApp(f,None)
   try:
    async with app.run_test(size=(160,50)) as pilot:
     app.query_one(TabbedContent).active='projects-tab';await pilot.pause()
     project=next(iter(app.projects.values()));app.selected_project_key=project.ui_key
     app._render_project_details(project)
     state=registration_state();app._render_project_registration(state);await pilot.pause()
     self.assertFalse(app.query('#registration-eligibility'))
     relationship=app.query_one('#registration-relationship',Static)
     self.assertEqual(app.query_one('#registration-refresh',Button).region.y-relationship.region.bottom,1)
     button=app.query_one('#registration-action',Button)
     self.assertEqual(str(button.label),'Register');self.assertFalse(button.disabled)
     refresh=app.query_one('#registration-refresh',Button)
     self.assertEqual(button.region.y,refresh.region.y)
     self.assertGreaterEqual(refresh.region.x-button.region.right,2)
     self.assertIn('Solo',str(app.query_one('#project-summary',Static).render()))
     project._catalog_data={'project_mode':'group','team_size':3}
     app._render_project_summary(project)
     self.assertIn('Group · 3 members',str(app.query_one('#project-summary',Static).render()))
     state['project_mode']='group';app._render_project_registration(state)
     self.assertIn('Group · 3 members',str(app.query_one('#project-summary',Static).render()))
     self.assertEqual(str(button.label),'Register')
     state['project_mode']='unknown';app._render_project_registration(state)
     self.assertIn('Group · 3 members',str(app.query_one('#project-summary',Static).render()))
     state['project_mode']='solo';app._render_project_registration(state)
     self.assertNotIn('DONE',str(app.query_one('#project-heading',Static).render()))
     state['capability']['mode']='intra';app._render_project_registration(state)
     self.assertEqual(str(button.label),'Register')
     state['operation']=operation('outcome_unknown');app._render_project_registration(state)
     self.assertEqual(str(button.label),'Refresh status')
     state['relationship']['state']='in_progress';state['operation']=operation('registered');app._render_project_registration(state)
     self.assertFalse(button.display)
     await pilot.resize_terminal(80,40);await pilot.pause()
     self.assertLessEqual(app.query_one('#project-registration').region.right,app.query_one('#project-details').region.right)
   finally:f.kw['bind'].dispose()
 async def test_duplicate_clicks_and_selection_changes_do_not_apply_an_old_result(self):
  import threading
  with TemporaryDirectory() as d:
   f=make_session_factory(f'sqlite:///{Path(d)/"workers.sqlite"}')
   with f() as s:
    save_settings(s,{'onboarding_completed':'true'})
    s.add_all([Project(slug='libft',name='Libft',official_project_id=1001,setup_status='unknown'),Project(slug='next',name='Next',official_project_id=1002,setup_status='unknown')]);s.commit()
   gate=threading.Event()
   class Provider:
    calls=0
    def get_project_registration(self,p,scope,account):
     state=registration_state();state['project_id']=p;return state
    def register_project(self,p,scope,account,key):
     self.calls+=1;gate.wait(5);state=registration_state();state['operation']=operation('registered');state['relationship']['state']='in_progress';return {'state':state,'operation':state['operation']}
   provider=Provider();app=FortyTwoTuiApp(f,None)
   try:
    async with app.run_test(size=(160,50)) as pilot:
     app.query_one(TabbedContent).active='projects-tab';await pilot.pause()
     app.account_id='42';app.provider=provider
     projects={p.official_project_id:p for p in app.projects.values()}
     with patch.object(app,'_catalog_scope',return_value=CatalogScope(21,31)),patch.object(app,'_request_catalog_refresh'):
      app.selected_project_key=projects[1001].ui_key;app._render_project_details(projects[1001]);state=registration_state();state['project_mode']='unknown';app._render_project_registration(state)
      await app._handle_registration_action();await app._handle_registration_action();await pilot.pause()
      self.assertEqual(provider.calls,1);self.assertTrue(app.query_one('#registration-action',Button).disabled)
      app.selected_project_key=projects[1002].ui_key;app._render_project_details(projects[1002]);app._load_project_registration(projects[1002].ui_key)
      gate.set();await pilot.pause();await pilot.pause()
      self.assertEqual(app._registration_state['project_id'],1002)
      self.assertNotIn('Libft',str(app.query_one('#project-heading',Static).render()))
   finally:gate.set();f.kw['bind'].dispose()

 async def test_personal_status_expires_while_the_screen_remains_open(self):
  with TemporaryDirectory() as d:
   f=make_session_factory(f'sqlite:///{Path(d)/"expiry.sqlite"}')
   with f() as s:
    save_settings(s,{'onboarding_completed':'true'});s.add(Project(slug='libft',name='Libft',official_project_id=1001,setup_status='unknown'));s.commit()
   app=FortyTwoTuiApp(f,None)
   try:
    async with app.run_test(size=(160,50)) as pilot:
     app.query_one(TabbedContent).active='projects-tab';await pilot.pause()
     project=next(iter(app.projects.values()));app.selected_project_key=project.ui_key
     state=registration_state();state['sources']['projects']['collected_at']=(datetime.now(timezone.utc)-timedelta(seconds=899.8)).isoformat()
     app._render_project_registration(state)
     self.assertEqual(str(app.query_one('#registration-action',Button).label),'Register')
     await pilot.pause(.35)
     self.assertEqual(str(app.query_one('#registration-action',Button).label),'Refresh status')
   finally:f.kw['bind'].dispose()
 async def test_older_read_cannot_erase_a_newer_confirmed_registration(self):
  import asyncio
  import threading
  with TemporaryDirectory() as d:
   f=make_session_factory(f'sqlite:///{Path(d)/"ordering.sqlite"}')
   with f() as s:
    save_settings(s,{'onboarding_completed':'true'});s.add(Project(slug='libft',name='Libft',official_project_id=1001,setup_status='unknown'));s.commit()
   gate=threading.Event();started=threading.Event()
   class Provider:
    def get_project_registration(self,*args):started.set();gate.wait(5);return registration_state()
    def register_project(self,*args):
     state=registration_state();state['relationship']['state']='in_progress';state['operation']=operation('registered');return {'state':state,'operation':state['operation']}
   provider=Provider();app=FortyTwoTuiApp(f,None)
   try:
    async with app.run_test(size=(160,50)) as pilot:
     app.query_one(TabbedContent).active='projects-tab';await pilot.pause();app.account_id='42';app.provider=provider
     project=next(iter(app.projects.values()));app.selected_project_key=project.ui_key
     with patch.object(app,'_catalog_scope',return_value=CatalogScope(21,31)),patch.object(app,'_request_catalog_refresh'):
      app._render_project_registration(registration_state())
      read=asyncio.create_task(app._registration_request('read',app._registration_context(),provider,app.account_generation))
      await asyncio.to_thread(started.wait,2)
      await app._handle_registration_action();await pilot.pause();await pilot.pause()
      gate.set();await read;await pilot.pause()
      self.assertEqual(app._registration_state['relationship']['state'],'in_progress')
   finally:gate.set();f.kw['bind'].dispose()

 async def test_reconnect_same_account_does_not_reuse_the_previous_loading_guard(self):
  with TemporaryDirectory() as d:
   f=make_session_factory(f'sqlite:///{Path(d)/"reconnect.sqlite"}')
   with f() as s:
    save_settings(s,{'onboarding_completed':'true'});s.add(Project(slug='libft',name='Libft',official_project_id=1001,setup_status='unknown'));s.commit()
   class Provider:
    calls=0
    def get_project_registration(self,*args):self.calls+=1;return registration_state()
   provider=Provider();app=FortyTwoTuiApp(f,None)
   try:
    async with app.run_test(size=(160,50)) as pilot:
     app.query_one(TabbedContent).active='projects-tab';await pilot.pause();app.account_id='42';app.provider=Provider()
     project=next(iter(app.projects.values()));app.selected_project_key=project.ui_key
     with patch.object(app,'_catalog_scope',return_value=CatalogScope(21,31)):
      app._registration_storage();ctx=app._registration_context()
      if isinstance(app._registration_busy,set):app._registration_busy.add(ctx)
      else:app._registration_busy[ctx]='old'
      app.provider=provider;app.account_generation+=1;app._load_project_registration(project.ui_key)
      await pilot.pause();await pilot.pause()
      self.assertEqual(provider.calls,1);self.assertFalse(app.query_one('#registration-action',Button).disabled)
   finally:f.kw['bind'].dispose()

 async def test_manage_team_replaces_register_only_for_registered_group_projects(self):
  with TemporaryDirectory() as d:
   f=make_session_factory(f'sqlite:///{Path(d)/"team-action.sqlite"}')
   with f() as s:
    save_settings(s,{'onboarding_completed':'true'})
    s.add(Project(slug='group-project',name='Group project',official_project_id=1001,setup_status='unknown'));s.commit()
   app=FortyTwoTuiApp(f,None)
   try:
    async with app.run_test(size=(160,50)) as pilot:
     app.query_one(TabbedContent).active='projects-tab';await pilot.pause()
     app.account_id='42'
     app.provider=type('Provider',(),{'get_project_team':lambda *args: None})()
     project=next(iter(app.projects.values()));app.selected_project_key=project.ui_key
     with patch.object(app,'_catalog_scope',return_value=CatalogScope(21,31)):
      app._registration_storage()
      button=app.query_one('#registration-action',Button)
      self.assertEqual(button.parent.id,'registration-actions')
      self.assertFalse(app.query('#manage-project-team'))
      for mode in ('solo','group','unknown'):
       state=registration_state();state['project_mode']=mode
       app._render_project_registration(state)
       self.assertEqual(str(button.label),'Register')
       self.assertTrue(button.display)
       self.assertFalse(app._can_manage_project_team())
       state['relationship'].update(state='in_progress',phase='creating_group',attempt={'id':71})
       app._render_project_registration(state)
       if mode=='group':
        self.assertEqual(str(button.label),'Manage team')
        self.assertTrue(button.display);self.assertFalse(button.disabled)
        with patch.object(app,'action_project_team') as manage:
         await app._handle_registration_button('registration-action')
         manage.assert_called_once_with()
       else:
        self.assertFalse(button.display)
        self.assertFalse(app._can_manage_project_team())
      state['project_mode']='group';state['operation']=operation('outcome_unknown')
      app._render_project_registration(state)
      self.assertEqual(str(button.label),'Refresh status')
      self.assertFalse(app._can_manage_project_team())
      app._clear_project_registration()
      self.assertFalse(button.display)
   finally:f.kw['bind'].dispose()
