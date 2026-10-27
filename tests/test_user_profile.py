import unittest
from copy import deepcopy
from datetime import date
from ft_tui.api.user_profile_types import student_profile, student_attendance, student_goals, student_portrait
from ft_tui.services.user_profile import weekly_attendance, latest_attempts


def profile():
    return {'user_id':'50','login':'alice','display_name':'Alice Example','email':None,'image_url':None,
            'wallet':0,'correction_point':0,'campuses':[],'titles':[],'coalitions':[],
            'achievements':[],'cursus_users':[{'cursus_id':21,'name':'42cursus','slug':'42cursus','grade':'Cadet','level':4.61}],
            'main_cursus_id':21,'meta':{'cache':'fresh','stale':False,'cached_at':'2026-10-23T12:00:00Z'}}


def attendance():
    return {'user_id':'50','status':'available','begin':'2026-07-01','end':'2026-10-23',
            'days':{'2026-10-12':0,'2026-10-13':3600},'stale':False,'collected_at':'2026-10-23T12:00:00Z'}


class ProfileTests(unittest.TestCase):
    def test_scope_optional_fields_and_memberships(self):
        value=profile();self.assertIs(student_profile(value,'50'),value)
        for mutate in [lambda p:p.update(user_id='99'),lambda p:p['cursus_users'].append(p['cursus_users'][0]),
                       lambda p:p.update(wallet=True),lambda p:p['cursus_users'][0].update(level=float('nan')),
                       lambda p:p.update(image_url='https://example.test/private')]:
            bad=deepcopy(value);mutate(bad)
            with self.assertRaises(ValueError):student_profile(bad,'50')
        value['cursus_users']=[];value['main_cursus_id']=None
        self.assertEqual(student_profile(value,'50')['wallet'],0)

    def test_attendance_bounds_unknown_zero_and_week_totals(self):
        data=attendance();student_attendance(data,'50')
        weeks=weekly_attendance(data,date(2026,10,23))
        self.assertEqual(len(weeks),4)
        self.assertEqual(weeks[-1]['seconds'],3600)
        self.assertEqual(weeks[-1]['known_days'],2)
        self.assertEqual(weeks[0]['known_days'],0)
        for mutate in [lambda p:p['days'].update({'2026-06-30':1}),lambda p:p['days'].update({'2026-10-14':True}),
                       lambda p:p.update(end='2026-02-30'),lambda p:p.update(user_id='99')]:
            bad=deepcopy(data);mutate(bad)
            with self.assertRaises(ValueError):student_attendance(bad,'50')

    def test_goals_match_viewed_identity_and_cursus(self):
        value={'user_id':'50','cursus_id':21,'status':'available','stale':False,'collected_at':'2026-10-23T12:00:00Z',
               'cc_validated':False,'probationary_period':False,'next_milestone':'2026-11-03','cc_eta':'2027-08-13','edtrax_weeks':[]}
        self.assertIs(student_goals(value,'50',21),value)
        with self.assertRaises(ValueError):student_goals(value,'42',21)
        with self.assertRaises(ValueError):student_goals(value,'50',9)

    def test_latest_attempt_uses_stable_attempt_id_and_preserves_marks(self):
        values=[{'id':2,'project_id':1,'name':'Libft','final_mark':125}, {'id':1,'project_id':1,'name':'Libft','final_mark':0},
                {'id':3,'project_id':2,'name':'Exam','final_mark':0}]
        self.assertEqual([(p['name'],p['final_mark']) for p in latest_attempts(values)],[('Exam',0),('Libft',125)])

    def test_portrait_transport_validates_identity_url_and_payload(self):
        from ft_tui.api.http_client import HttpProjectProvider
        from types import SimpleNamespace
        calls = []
        value = {'user_id': '50', 'status': 'ready',
                 'image_url': 'https://cdn.intra.42.fr/users/alice.jpg', 'image_base64': 'aW1hZ2U='}

        def request(method, path):
            calls.append((method, path))
            return value

        provider = HttpProjectProvider(api=SimpleNamespace(request=request))
        self.assertIs(provider.get_student_portrait('50'), value)
        self.assertEqual(calls, [('GET', '/v1/users/50/profile/portrait')])
        for changes in ({'user_id': '99'}, {'image_url': 'https://example.test/private'},
                        {'image_base64': None}, {'status': 'pending'}, {'status': 'unknown'}):
            with self.assertRaises(ValueError):
                student_portrait({**value, **changes}, '50')
        for status in ('pending', 'unavailable'):
            self.assertEqual(student_portrait({**value, 'status': status, 'image_base64': None}, '50')['status'], status)
