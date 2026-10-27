import copy
import unittest
from time import monotonic
from textual.app import App
from textual.widgets import Input, Static
from textual.screen import ModalScreen
from ft_tui.api.catalog_types import CatalogScope
from ft_tui.api.team_types import team_state
from ft_tui.ui.button import Button
from ft_tui.ui.friend_suggestions import FriendSuggestions
from ft_tui.ui.project_team import ProjectTeamScreen


def state(members=None):
    return {'account_id': '42', 'project_id': 1001, 'context': {'cursus_id': 21, 'campus_id': 31},
            'session': {'id': 9001, 'project_id': 1001, 'campus_id': 31, 'cursus_id': 21, 'solo': False, 'max_people': 2},
            'can_write': True, 'teams': [{'id': 8, 'project_id': 1001, 'project_session_id': 9001, 'name': 'Our team',
                'status': 'creating_group', 'locked': False, 'closed': False, 'members': members or [
                    {'id': 42, 'login': 'me', 'leader': True, 'accepted': True},
                    {'id': 43, 'login': 'mate', 'leader': False, 'accepted': False}]}]}


class Provider:
    def __init__(self, value): self.value = value; self.calls = []
    def get_project_team(self, *args): return copy.deepcopy(self.value)
    def change_project_team(self, p, scope, account, action, key):
        self.calls.append(action)
        if action['action'] == 'save':
            if action['team_id'] is None:
                created = state()['teams'][0]
                created['name'] = action['name']
                created['members'] = [created['members'][0]] + [
                    {'id': uid, 'login': f'student{uid}', 'leader': False, 'accepted': False}
                    for uid in action['invite_ids']]
                self.value['teams'] = [created]
            else:
                self.value['teams'][0]['name'] = action['name']
                self.value['teams'][0]['members'].extend(
                    {'id': uid, 'login': f'student{uid}', 'leader': False, 'accepted': False}
                    for uid in action['invite_ids'])
        if action['action'] == 'lock': self.value['teams'][0]['locked'] = True
        if action['action'] == 'accept': self.value['teams'][0]['members'][0]['accepted'] = True
        return copy.deepcopy(self.value)


class Harness(App):
    language = 'en'; account_login = 'me'; account_id = '42'; account_generation = 0; account_connected = True
    def __init__(self, value): super().__init__(); self.provider = Provider(value)
    def on_mount(self):
        self.push_screen(ProjectTeamScreen(1001, 'Project', CatalogScope(21, 31), '42', self.provider, 0, 'project'))


class TeamTests(unittest.IsolatedAsyncioTestCase):
    async def test_lock_requires_every_acceptance_and_refreshes_after_success(self):
        app = Harness(state())
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause(); await pilot.pause()
            screen = app.screen
            self.assertTrue(screen.query_one('#team-lock', Button).disabled)
            self.assertIn('Invitation pending', str(screen.query_one('#team-roster', Static).render()))
            app.provider.value['teams'][0]['members'][1]['accepted'] = True
            screen.action_refresh(); await pilot.pause(); await pilot.pause()
            self.assertFalse(screen.query_one('#team-lock', Button).disabled)
            await pilot.click('#team-lock'); await pilot.pause(); await pilot.pause()
            self.assertEqual(app.provider.calls, [{'action': 'lock', 'team_id': 8}])
            self.assertTrue(screen.query_one('#team-save', Button).disabled)

    async def test_invitee_can_accept_but_cannot_edit_and_account_change_clears(self):
        value = state(); value['teams'][0]['members'][0].update(leader=False, accepted=False)
        value['teams'][0]['members'][1].update(leader=True, accepted=True)
        app = Harness(value)
        async with app.run_test(size=(80, 35)) as pilot:
            await pilot.pause(); await pilot.pause()
            screen = app.screen
            self.assertTrue(screen.query_one('#team-save', Button).disabled)
            self.assertFalse(screen.query_one('#team-accept', Button).disabled)
            await pilot.click('#team-accept'); await pilot.pause(); await pilot.pause()
            self.assertEqual(app.provider.calls[0], {'action': 'accept', 'team_id': 8})
            app.account_generation += 1
            screen._check_identity()
            self.assertEqual(screen.query_one('#team-name', Input).value, '')
            self.assertEqual(str(screen.query_one('#team-roster', Static).render()), '')
            self.assertTrue(screen.query_one('#team-save', Button).disabled)

    async def test_existing_team_uses_shared_fuzzy_selection_and_queues_unique_invites(self):
        value = state(); value['teams'][0]['members'] = value['teams'][0]['members'][:1]
        app = Harness(value)
        async with app.run_test(size=(80, 35)) as pilot:
            await pilot.pause(); await pilot.pause()
            screen = app.screen
            self.assertEqual(screen.selected, 8)
            self.assertIsInstance(screen, ModalScreen)
            dialog = screen.query_one('#team-dialog').region
            self.assertLessEqual(abs(dialog.center[0] - screen.size.width / 2), 1)
            self.assertLessEqual(abs(dialog.center[1] - screen.size.height / 2), 1)
            self.assertEqual(str(screen.query_one('#team-save', Button).label), 'Save team')
            screen.choose(FriendSuggestions.Chosen({'user_id': '43', 'login': 'mate'}))
            await pilot.pause()
            await pilot.press('enter'); await pilot.pause()
            self.assertEqual(screen.pending, {43: 'mate'})
            self.assertIsInstance(screen.query_one(FriendSuggestions), FriendSuggestions)
            await pilot.resize_terminal(60, 24); await pilot.pause()
            self.assertLessEqual(screen.query_one('#team-content').region.right, 60)

    async def test_modal_creates_named_team_and_keeps_actions_visible_on_small_terminal(self):
        value = state(); value['teams'] = []
        app = Harness(value)
        async with app.run_test(size=(80, 35)) as pilot:
            await pilot.pause(); await pilot.pause()
            screen = app.screen
            save = screen.query_one('#team-save', Button)

            async def click_save():
                # Textual ignores clicks while its active-feedback timer is
                # running. UI idleness alone does not wait for that timer.
                deadline = monotonic() + 10
                while save.has_class('-active') or screen.busy:
                    self.assertLess(monotonic(), deadline, 'Team save never became interactive')
                    await pilot.pause(.01)
                self.assertFalse(save.disabled)
                self.assertTrue(await pilot.click(save))
                await screen.workers.wait_for_complete()
                await pilot.pause()

            self.assertIsNone(screen.selected)
            self.assertFalse(screen.query_one('#team-invitations').display)
            self.assertEqual(screen.query_one('#team-name', Input).value, "me's team")
            screen.query_one('#team-name', Input).value = ''
            await click_save()
            self.assertFalse(app.provider.calls)
            self.assertTrue(screen.query_one('#team-form-error', Static).display)
            screen.query_one('#team-name', Input).value = 'Our new team'
            await click_save()
            self.assertEqual(app.provider.calls, [{'action': 'save', 'team_id': None,
                                                   'name': 'Our new team', 'invite_ids': []}])
            self.assertTrue(screen.query_one('#team-invitations').display)
            screen.choose(FriendSuggestions.Chosen({'user_id': '43', 'login': 'mate'}))
            await pilot.press('enter'); await pilot.pause()
            await click_save()
            self.assertEqual(app.provider.calls[-1], {'action': 'save', 'team_id': 8,
                                                     'name': 'Our new team', 'invite_ids': [43]})
            self.assertEqual(screen.selected, 8)
            self.assertEqual(screen.query_one('#team-name', Input).value, 'Our new team')
            self.assertEqual(str(screen.query_one('#team-save', Button).label), 'Save team')
            await pilot.resize_terminal(60, 24); await pilot.pause()
            dialog = screen.query_one('#team-dialog').region
            for selector in ('#team-save', '#team-close'):
                button = screen.query_one(selector).region
                self.assertGreaterEqual(button.y, dialog.y)
                self.assertLessEqual(button.bottom, dialog.bottom)
            await pilot.press('escape'); await pilot.pause()
            self.assertNotIsInstance(app.screen, ProjectTeamScreen)

    def test_response_rejects_unrelated_team_and_unknown_acceptance(self):
        value = state(); value['teams'][0]['members'][0]['id'] = 99
        with self.assertRaises(ValueError): team_state(value, 1001, CatalogScope(21, 31), '42')
        value = state(); value['teams'][0]['members'][1]['accepted'] = None
        with self.assertRaises(ValueError): team_state(value, 1001, CatalogScope(21, 31), '42')

    async def test_loading_failure_does_not_offer_a_fake_empty_team_and_recovers(self):
        import httpx
        app = Harness(state())
        def unavailable(*args):
            request = httpx.Request('GET', 'https://synthetic.example/v1/me/projects/1001/team')
            response = httpx.Response(404, request=request, text='private upstream body')
            raise httpx.HTTPStatusError('not found', request=request, response=response)
        app.provider.get_project_team = unavailable
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause(); await pilot.pause()
            screen = app.screen
            message = str(screen.query_one('#team-status', Static).render())
            self.assertIn('Update the backend', message)
            self.assertIn('HTTP 404', message)
            self.assertNotIn('private upstream body', message)
            self.assertFalse(screen.query_one('#team-choice').display)
            self.assertFalse(screen.query_one('#team-name', Input).display)
            self.assertFalse(screen.query_one('#team-primary-actions').display)
            self.assertFalse(screen.query_one('#team-refresh', Button).disabled)
            app.provider.value['teams'] = []
            app.provider.get_project_team = lambda *args: copy.deepcopy(app.provider.value)
            screen.action_refresh(); await pilot.pause(); await pilot.pause()
            self.assertTrue(screen.query_one('#team-name', Input).display)
            self.assertTrue(screen.query_one('#team-primary-actions').display)
            self.assertEqual(str(screen.query_one('#team-save', Button).label), 'Create team')
            self.assertFalse(screen.query_one('#team-save', Button).disabled)

    async def test_disabled_creation_explains_missing_oauth_scope(self):
        value = state(); value.update(can_write=False, reason_code='scope_missing'); value['teams'] = []
        app = Harness(value)
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause(); await pilot.pause()
            screen = app.screen
            self.assertIn('projects permission', str(screen.query_one('#team-status', Static).render()))
            self.assertTrue(screen.query_one('#team-save', Button).disabled)

    async def test_unknown_capacity_still_allows_name_only_creation(self):
        value = state(); value['teams'] = []; value['session']['max_people'] = None
        app = Harness(value)
        async with app.run_test(size=(100, 40)) as pilot:
            await pilot.pause(); await pilot.pause()
            screen = app.screen
            self.assertFalse(screen.query_one('#team-save', Button).disabled)
            await pilot.click('#team-save'); await pilot.pause(); await pilot.pause()
            self.assertEqual(app.provider.calls[0]['invite_ids'], [])
            self.assertEqual(screen.selected, 8)
            self.assertIn('capacity is unavailable', str(screen.query_one('#team-status', Static).render()))
            self.assertTrue(screen.query_one('#team-invite', Button).disabled)
            self.assertTrue(screen.query_one('#team-lock', Button).disabled)
