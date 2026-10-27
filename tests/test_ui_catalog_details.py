import unittest
from ft_tui.db.models import Project
from ft_tui.services.project_presentation import catalog_details,expression_label
class DetailTests(unittest.TestCase):
 def test_exam_zero_xp_failed_zero_mark_and_advice_are_distinct(self):
  p=Project(official_project_id=1001,slug='exam',name='Exam')
  p._catalog_data={'kind':'exam','xp':0,'duration':None,'rank':0,'track':'shared','description':'[red]example[/red]','visual_links':[{'parent_id':0}],'clauses':[{'modality':'recommended','status':'recognized','expression':{'op':'at_least','count':2,'children':[{'op':'predicate','target':'project','ref':s,'action':'validated'} for s in ('a','b','c')]}}]}
  p._progress_data={'status':'finished','validated':False,'final_mark':0}
  label=catalog_details(p,{})
  self.assertIn('EXAM',label);self.assertIn('XP: 0',label);self.assertIn('Unknown',label);self.assertIn('Recommendation: 2 of',label);self.assertIn('drawing only',label);self.assertIn('\\[red]',label);self.assertEqual(p.status,'failed');self.assertEqual(p.last_defense_score,0)

class ReadableConditionsTests(unittest.TestCase):
 def test_nested_conditions_use_readable_language_and_keep_negation(self):
  from ft_tui.services.project_presentation import readable_condition
  expression={'op':'not','child':{'op':'all','children':[{'op':'predicate','ref':'42cursus-libft','action':'validated','target':'project'}]}}
  self.assertEqual(readable_condition(expression), 'Must not satisfy: Libft completed')
 def test_unknown_conditions_are_not_presented_as_known_requirements(self):
  from ft_tui.services.project_presentation import readable_condition
  self.assertIsNone(readable_condition({'op':'mystery','text':'opaque rule'}))
