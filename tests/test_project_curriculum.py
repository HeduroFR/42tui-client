import unittest
from ft_tui.db.models import Project
from ft_tui.services.project_curriculum import curriculum_projects
class CurriculumTests(unittest.TestCase):
 def test_exclusive_track_and_current_next_are_independent_from_registration(self):
  rows=[]
  for id,track,rank in [(1,'new',1),(2,'shared',2),(3,'old',1),(4,'new',4)]:
   p=Project(official_project_id=id,slug=str(id),name=str(id));p._catalog_data={'track':track,'rank':rank,'section':'common-core'};rows.append(p)
  evidence={'selected_track':{'track':'new'},'selected_rank':{'rank':1},'registration':{'status':'available','stale':False,'project_ids':[4]}}
  self.assertEqual([p.official_project_id for p in curriculum_projects(rows,curriculum=evidence)],[1,2])
  self.assertEqual([p.official_project_id for p in curriculum_projects(rows,curriculum=evidence,scope='eligible')],[4])
  self.assertEqual(curriculum_projects(rows,curriculum={}),[])

 def test_id_only_registration_is_not_an_active_local_checkout(self):
  p=Project(official_project_id=999,slug='',name='Unknown',setup_status='unknown')
  self.assertEqual(curriculum_projects([p],scope='active'),[])

 def test_all_projects_uses_completed_common_core_to_choose_section(self):
  rows=[]
  for id,track,section in [(1,'new','common-core'),(2,'shared','common-core'),
                           (3,'old','common-core'),(4,'new','specialization'),
                           (5,'shared','specialization'),(6,'old','specialization'),(7,None,'other')]:
   p=Project(official_project_id=id,slug=str(id),name=str(id))
   p._catalog_data={'track':track,'section':section};rows.append(p)
  evidence={'selected_track':{'track':'new'},'selected_rank':{'rank':6,'source':'quest','completed':False}}
  self.assertEqual([p.official_project_id for p in curriculum_projects(rows,curriculum=evidence,scope='all')],[1,2])
  evidence['selected_rank']['completed']=True
  self.assertEqual([p.official_project_id for p in curriculum_projects(rows,curriculum=evidence,scope='all')],[4,5])
  evidence['selected_track']['track']='old'
  self.assertEqual([p.official_project_id for p in curriculum_projects(rows,curriculum=evidence,scope='all')],[5,6])
  self.assertEqual(curriculum_projects(rows,curriculum={},scope='all'),[])

 def test_unknown_rank_keeps_inactive_common_core_projects_visible(self):
  rows=[]
  for id,track,rank,section in [(1,'shared',0,'common-core'),(2,'new',1,'common-core'),
                              (3,'shared',1,'common-core'),(4,'old',1,'common-core'),
                              (5,'new',None,'specialization')]:
   p=Project(official_project_id=id,slug=str(id),name=str(id))
   p._catalog_data={'track':track,'rank':rank,'section':section};rows.append(p)
  evidence={'selected_track':{'track':'new'},'selected_rank':{'rank':None,'source':'unknown'}}
  self.assertEqual([p.official_project_id for p in curriculum_projects(rows,curriculum=evidence)],[1,2,3])
