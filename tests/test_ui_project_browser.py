import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from ft_tui.db.database import make_session_factory
from ft_tui.features.settings.adapters.storage import save_settings
from ft_tui.ui.app import FortyTwoTuiApp
from ft_tui.ui.components import Button, Input, ListView, ProjectEntry, ProjectRankHeader, Select, Static, TabbedContent
from ft_tui.db.models import Project
class BrowserTests(unittest.IsolatedAsyncioTestCase):
 async def test_filtering_collapsed_groups_clears_excluded_project_actions(self):
  with TemporaryDirectory() as directory:
   factory=make_session_factory(f'sqlite:///{Path(directory)/"selection.sqlite"}')
   try:
    with factory() as session:
     save_settings(session,{'onboarding_completed':'true'})
     session.add_all([Project(slug=name.lower(),name=name,local_path=directory) for name in ('Alpha','Beta')])
     session.commit()
    app=FortyTwoTuiApp(factory,None)
    async with app.run_test(size=(120,40)) as pilot:
     app.query_one('#project-view',Select).value='active'
     await pilot.pause()
     alpha=next(project for project in app.projects.values() if project.name=='Alpha')
     app._show_project(alpha)
     self.assertEqual(app.selected_project_key,alpha.ui_key)
     app.query_one('#project-search',Input).value='Beta'
     await pilot.pause()
     self.assertEqual([project.name for project in app._visible_projects()],['Beta'])
     self.assertIsNone(app.selected_project_key)
     for selector in ('#open-project-editor','#project-timer-toggle','#new-project-note','#configure-project'):
      self.assertTrue(app.query_one(selector,Button).disabled)
   finally:
    factory.kw['bind'].dispose()

 async def test_legacy_exam_metadata_still_sorts_first_and_displays_exam_badge(self):
  with TemporaryDirectory() as d:
   f=make_session_factory(f'sqlite:///{Path(d)/"legacy-exam.sqlite"}')
   with f() as s:
    save_settings(s,{'onboarding_completed':'true'})
    s.add_all([Project(slug=slug,name=name,local_path=d,setup_status='unknown') for slug,name in
               [('a-maze-ing','A-Maze-ing'),('42next-exam-rank-02','Exam Rank 02'),('born2beroot','Born2beroot')]])
    s.commit()
   app=FortyTwoTuiApp(f,None)
   try:
    async with app.run_test(size=(80,24)) as pilot:
     await pilot.pause()
     for project in app.projects.values():project._catalog_data={'rank':2,'kind':'project'}
     app.query_one('#project-view',Select).value='active'
     app.query_one(TabbedContent).active='projects-tab'
     await pilot.pause()
     self.assertEqual([p.slug for p in app._visible_projects()],['42next-exam-rank-02','a-maze-ing','born2beroot'])
     for header in list(app.query(ProjectRankHeader)):
      await app._toggle_project_rank(header)
     await pilot.pause()
     exam=next(row for row in app.query(ProjectEntry) if row.project.slug=='42next-exam-rank-02')
     self.assertTrue(exam.query_one('.project-exam-badge').display)
     self.assertEqual(exam.project._catalog_data['kind'],'project')
     self.assertEqual(exam.project.catalog_data['kind'],'exam')
   finally:
    f.kw['bind'].dispose()

 async def test_exams_lead_their_rank_and_stand_out_without_losing_status_colors(self):
  with TemporaryDirectory() as d:
   f=make_session_factory(f'sqlite:///{Path(d)/"exams.sqlite"}')
   with f() as s:
    save_settings(s,{'onboarding_completed':'true'})
    s.add_all([Project(slug=slug,name=name,local_path=d,setup_status='completed') for slug,name in
               [('first','First'),('ordinary','Alpha'),('exam-z','Zulu'),('exam-b','Beta'),('last','Last')]])
    s.commit()
   app=FortyTwoTuiApp(f,None)
   try:
    async with app.run_test(size=(80,24)) as pilot:
     await pilot.pause()
     projects={p.slug:p for p in app.projects.values()}
     for slug,project in projects.items():
      project._catalog_data={'rank':0 if slug=='first' else 2 if slug=='last' else 1,
                             'kind':'exam' if slug.startswith('exam-') else 'project'}
     app.query_one('#project-view',Select).value='active'
     app.query_one(TabbedContent).active='projects-tab'
     await pilot.pause()
     self.assertEqual([p.slug for p in app._visible_projects()],['first','exam-b','exam-z','ordinary','last'])
     for header in list(app.query(ProjectRankHeader)):
      await app._toggle_project_rank(header)
     await pilot.pause()
     rows={row.project.slug:row for row in app.query(ProjectEntry)}
     exam=rows['exam-b']
     self.assertTrue(exam.query_one('.project-exam-badge').display)
     self.assertEqual(str(exam.query_one('.project-exam-badge',Static).render()),'★ EXAM')
     self.assertEqual(exam.size.height,4)
     content=exam.query_one('.project-entry-content')
     self.assertEqual(content.size.height,3)
     self.assertEqual(content.region.bottom,exam.query_one('.project-entry-meta').region.bottom)
     self.assertEqual(exam.region.bottom-content.region.bottom,1)
     self.assertEqual(exam.styles.border_left[0],'')
     self.assertEqual(content.styles.border_left[0],'wide')
     self.assertEqual(exam.query_one('.project-name').styles.color,exam.query_one('.project-state').styles.color)
     self.assertTrue(exam.query_one('.project-name').has_class('state-done'))
     self.assertFalse(rows['ordinary'].query_one('.project-exam-badge').display)
     projects['ordinary']._catalog_data['kind']='exam'
     await app._refresh_activity_order()
     await pilot.pause()
     self.assertEqual([p.slug for p in app._visible_projects()],['first','ordinary','exam-b','exam-z','last'])
     ordinary=next(row for row in app.query(ProjectEntry) if row.project.slug=='ordinary')
     self.assertTrue(ordinary.has_class('exam-entry'))
     self.assertTrue(ordinary.query_one('.project-exam-badge').display)
   finally:
    f.kw['bind'].dispose()

 async def test_rank_progress_counts_completion_and_refreshes_status_colors_when_collapsed(self):
  with TemporaryDirectory() as d:
   f=make_session_factory(f'sqlite:///{Path(d)/"progress.sqlite"}')
   with f() as s:
    save_settings(s,{'onboarding_completed':'true'})
    s.add_all([Project(slug=slug,name=slug,local_path=d,setup_status=status)
               for slug,status in [('done','completed'),('active','in_progress'),('idle','unknown')]])
    s.commit()
   app=FortyTwoTuiApp(f,None)
   try:
    async with app.run_test(size=(80,24)) as pilot:
     await pilot.pause()
     projects={p.slug:p for p in app.projects.values()}
     for project in projects.values():project._catalog_data={'rank':1}
     app.query_one('#project-view',Select).value='active'
     app.query_one(TabbedContent).active='projects-tab'
     await pilot.pause()
     header=app.query_one(ProjectRankHeader)
     self.assertTrue(header.collapsed)
     await app._toggle_project_rank(header)
     await pilot.pause()
     header=app.query_one(ProjectRankHeader)
     self.assertEqual(str(header.query_one('.rank-header-progress',Static).render()),'1/3')
     self.assertEqual(header.query_one('.rank-header-progress').region.right,header.content_region.right)
     self.assertTrue(header.has_class('state-active'))
     idle=next(row for row in app.query(ProjectEntry) if row.project.slug=='idle')
     self.assertEqual(str(idle.query_one('.project-state',Static).render()),'INACTIVE')
     self.assertEqual(projects['idle'].status,'unknown')
     self.assertTrue(idle.query_one('.project-name').has_class('state-inactive'))
     active=next(row for row in app.query(ProjectEntry) if row.project.slug=='active')
     self.assertEqual(header.styles.color,active.query_one('.project-state').styles.color)
     projects['active'].status='unknown'
     await app._refresh_activity_order()
     self.assertTrue(header.has_class('state-available'))
     self.assertTrue(active.query_one('.project-name').has_class('state-inactive'))
     self.assertFalse(active.query_one('.project-name').has_class('state-active'))
     await app._toggle_project_rank(header)
     header=app.query_one(ProjectRankHeader)
     projects['active'].status=projects['idle'].status='completed'
     await app._refresh_activity_order()
     self.assertTrue(header.collapsed)
     self.assertEqual(str(header.query_one('.rank-header-progress',Static).render()),'3/3')
     self.assertTrue(header.has_class('state-done'))
     projects['idle']._progress_data={'status':'finished','validated':False,'final_mark':100}
     await app._refresh_activity_order()
     self.assertEqual(str(header.query_one('.rank-header-progress',Static).render()),'2/3')
     self.assertTrue(header.has_class('state-failed'))
     await app._toggle_project_rank(header)
     header=app.query_one(ProjectRankHeader)
     failed=next(row for row in app.query(ProjectEntry) if row.project.slug=='idle')
     self.assertEqual(str(failed.query_one('.project-score',Static).render()),'100')
     self.assertEqual(failed.query_one('.project-score').styles.color,failed.query_one('.project-state').styles.color)
     for project in projects.values():
      project._progress_data={};project.status='unknown'
     await app._refresh_activity_order()
     self.assertEqual(str(header.query_one('.rank-header-progress',Static).render()),'0/3')
     self.assertTrue(header.has_class('state-inactive'))
   finally:
    f.kw['bind'].dispose()

 async def test_rank_groups_sort_numerically_and_unranked_groups_can_collapse(self):
  with TemporaryDirectory() as d:
   f=make_session_factory(f'sqlite:///{Path(d)/"groups.sqlite"}')
   with f() as s:
    save_settings(s,{'onboarding_completed':'true','project_view_None':'all'})
    s.add_all([Project(slug=slug,name=name,local_path=d) for slug,name in
               [('late','Alpha'),('first','Zulu'),('unknown','Middle'),('same','Beta')]])
    s.commit()
   app=FortyTwoTuiApp(f,None)
   try:
    async with app.run_test(size=(140,50)) as pilot:
     await pilot.pause()
     self.assertEqual(app.query_one('#project-view',Select).value,'relevant')
     for project in app.projects.values():
      project._catalog_data={'rank':{'late':2,'first':0,'unknown':None,'same':2}[project.slug]}
     app.query_one('#project-view',Select).value='active'
     app.query_one(TabbedContent).active='projects-tab'
     await pilot.pause()
     self.assertEqual([p.slug for p in app._visible_projects()],['first','late','same','unknown'])
     headers=list(app.query(ProjectRankHeader))
     self.assertEqual([h.rank for h in headers],[0,2,None])
     self.assertTrue(all(header.collapsed for header in headers))
     for header in headers:
      await app._toggle_project_rank(header)
     await pilot.pause()
     headers=list(app.query(ProjectRankHeader))
     await pilot.click(headers[-1])
     await pilot.pause()
     self.assertEqual([row.project.slug for row in app.query(ProjectEntry)],['first','late','same'])
     self.assertIsInstance(app.query_one('#project-list-view',ListView).highlighted_child,ProjectRankHeader)
     for header in list(app.query(ProjectRankHeader))[:2]:
      await app._toggle_project_rank(header)
     self.assertEqual(len(app.query(ProjectEntry)),0)
     self.assertEqual(len(app.query(ProjectRankHeader)),3)
     self.assertFalse(app.query_one('#project-empty').display)
   finally:
    f.kw['bind'].dispose()

 async def test_unchanged_rows_are_updated_without_clearing_the_list(self):
  with TemporaryDirectory() as directory:
   factory=make_session_factory(f'sqlite:///{Path(directory)/"stable.sqlite"}')
   with factory() as session:
    save_settings(session,{'onboarding_completed':'true'})
    session.add(Project(slug='local',name='Before',local_path=directory));session.commit()
   app=FortyTwoTuiApp(factory,None)
   try:
    async with app.run_test(size=(100,35)) as pilot:
     await pilot.pause()
     app.query_one('#project-view',Select).value='active'
     await pilot.pause()
     await app._toggle_project_rank(app.query_one(ProjectRankHeader))
     listing=app.query_one('#project-list-view',ListView)
     before=list(listing.children)
     with factory() as session:
      session.query(Project).one().name='After';session.commit()
     with patch.object(listing,'clear',wraps=listing.clear) as clear:
      await app._reload_project_catalog()
      clear.assert_not_called()
     self.assertEqual(list(listing.children),before)
     self.assertEqual(app.query_one(ProjectEntry).project.name,'After')
   finally:
    factory.kw['bind'].dispose()

 async def test_refresh_stops_when_list_detaches(self):
  with TemporaryDirectory() as d:
   f=make_session_factory(f'sqlite:///{Path(d)/"test.sqlite"}')
   with f() as s:save_settings(s,{'onboarding_completed':'true'})
   app=FortyTwoTuiApp(f,None)
   async with app.run_test() as pilot:
    await pilot.pause();view=app.query_one('#project-list-view',ListView);clear=view.clear
    async def detach():await clear();await view.remove()
    with patch.object(view,'clear',detach):self.assertEqual(await app._refresh_project_list(),[])
   f.kw['bind'].dispose()
