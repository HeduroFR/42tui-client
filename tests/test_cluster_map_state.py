import unittest
from ft_tui.cluster_map.state import SeatState, seat_states, matching_hosts, session_label, status_label
from datetime import datetime, timezone
from ft_tui.api.cluster_map_types import cluster_map_snapshot


class StateTests(unittest.TestCase):
    def test_offline_machine_does_not_count_a_retained_login_as_connected_friend(self):
        states=seat_states({'machines':[{'hostname':'1a1.42angouleme.fr','status':'down','login':'abcdefgh'}]},frozenset({'abcdefgh'}))
        self.assertFalse(states['1A1'].friend)

    def test_missing_unknown_locked_and_friend_matching(self):
        states=seat_states({'machines':[{'hostname':'1a1.42angouleme.fr','status':'up','login':'abcdefgh',
            'is_locked':True,'person':{'login':'abcdefgh','display_name':'Alex Example'},
            'issues':{'availability':'unavailable','open_count':None}}]},frozenset({'abcdefgh'}))
        self.assertEqual(len(states),147)
        self.assertEqual(states['1A1'].session,'locked')
        self.assertTrue(states['1A1'].friend)
        self.assertEqual(states['1A2'].machine,'unknown')
        self.assertEqual(matching_hosts(states,'alex','all',True),('1A1',))
        self.assertEqual(matching_hosts(states,'1a2','healthy',False),())

    def test_free_with_unknown_reports_is_not_healthy(self):
        states=seat_states({'machines':[{'hostname':'1a1.42angouleme.fr','status':'up','login':None}]},frozenset())
        self.assertEqual(matching_hosts(states,'','free',False),('1A1',))
        self.assertEqual(matching_hosts(states,'','healthy',False),())

    def test_invalid_snapshot_rejected_instead_of_becoming_empty_map(self):
        for value in ({}, {'campus_id':55,'machines':'bad'}, {'campus_id':55,'machines':[{'hostname':'evil.example'}]}):
            with self.assertRaises(ValueError):cluster_map_snapshot(value)


class LockTimeTests(unittest.TestCase):
    def test_duration_offsets_fallback_and_unlocked_state(self):
        from dataclasses import replace
        seat=SeatState('1A1',session='locked',lock_time='2026-10-23T12:00:00+02:00')
        now=datetime(2026,10,23,11,2,3,tzinfo=timezone.utc)
        self.assertEqual(session_label(seat,str,now),'Locked for 1h 02m 03s')
        self.assertEqual(session_label(replace(seat,lock_time='2026-10-23T12:00:00Z'),str,now),'Locked for 0m 00s')
        for value in ('14:30','invalid','2026-10-23T10:00:00'):
            self.assertEqual(session_label(replace(seat,lock_time=value),str,now),'Locked since '+value)
        for value in (None,'N/A',''):
            self.assertEqual(session_label(replace(seat,lock_time=value),str,now),'Locked')
        self.assertEqual(session_label(replace(seat,session='signed in'),str,now),'Signed in')

    def test_projection_carries_lock_time_only_for_locked_unique_occupant(self):
        machine={'hostname':'1a1.42angouleme.fr','status':'up','login':'abcdefgh','is_locked':True,'lock_time':'2026-10-23T10:00:00Z'}
        snapshot={'machines':[machine,dict(machine,hostname='1a2.42angouleme.fr')]}
        states=seat_states(snapshot,frozenset())
        self.assertEqual(states['1A1'].lock_time,machine['lock_time'])
        self.assertIsNone(states['1A2'].lock_time)
        machine['is_locked']=False
        self.assertIsNone(seat_states(snapshot,frozenset())['1A1'].lock_time)


    def test_status_display_is_capitalized_in_each_language(self):
        from ft_tui.i18n import translate
        for language,expected in (('en','Online'),('fr','En ligne'),('es','En línea')):
            self.assertEqual(status_label('online',lambda text:translate(text,language)),expected)
        for status in ('offline','unknown','locked','signed in','no active session'):
            self.assertEqual(status_label(status,str),status[0].upper()+status[1:])


    def test_elapsed_lock_time_uses_snapshot_age_and_survives_reprojection(self):
        machine={'hostname':'1a1.42angouleme.fr','status':'up','login':'abcdefgh','is_locked':True,'lock_time':'00:00:12'}
        snapshot={'machines':[machine],'meta':{'cached_at':'2026-10-23T10:00:00Z'}}
        now=datetime(2026,10,23,10,0,3,tzinfo=timezone.utc)
        for _ in range(2):
            seat=seat_states(snapshot,frozenset())['1A1']
            self.assertEqual(session_label(seat,str,now),'Locked for 0m 15s')
        snapshot['meta']['cached_at']='2026-10-23T10:00:03Z'
        machine['lock_time']='00:00:15'
        self.assertEqual(session_label(seat_states(snapshot,frozenset())['1A1'],str,now),'Locked for 0m 15s')
        machine['lock_time']='25:59:59'
        self.assertEqual(session_label(seat_states(snapshot,frozenset())['1A1'],str,datetime(2026,10,23,10,0,4,tzinfo=timezone.utc)),'Locked for 26h 00m 00s')
