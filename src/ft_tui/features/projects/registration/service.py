"""Context-fenced project operations without write retries or generated keys."""
import asyncio
from datetime import datetime, timezone
from .types import registration_state, registration_result
from .team_types import team_state
from .presentation import registration_view
from .ports import RegistrationProvider, TeamProvider

class StaleRegistrationContext(Exception):
    """The captured account, scope or request revision no longer owns the work."""

class RegistrationService:
    async def _dispatch(self, operation, *args, current):
        def dispatch():
            if not current():
                raise StaleRegistrationContext()
            return operation(*args)
        if not current():
            raise StaleRegistrationContext()
        value = await asyncio.to_thread(dispatch)
        if not current():
            raise StaleRegistrationContext()
        return value

    async def registration(self, provider: RegistrationProvider, action, project_id, scope, account_id, *, current, key=None, state=None):
        if action == 'register':
            snapshot = registration_state(state, project_id, scope, account_id)
            view = registration_view(snapshot, now=datetime.now(timezone.utc), language='en')
            if not key or view.action != 'register' or not view.enabled:
                raise ValueError('Registration is unavailable; refresh before trying again')
            value = await self._dispatch(provider.register_project, project_id, scope, account_id, key, current=current)
            return registration_result(value, project_id, scope, account_id)['state']
        operations = {'read': 'get_project_registration', 'refresh': 'refresh_project_registration'}
        if action not in operations:
            raise ValueError('Unknown registration action')
        value = await self._dispatch(getattr(provider, operations[action]), project_id, scope, account_id, current=current)
        return registration_state(value, project_id, scope, account_id)

    def _team_action(self, state, action, project_id, scope, account_id):
        snapshot = team_state(state, project_id, scope, account_id)
        if not snapshot['can_write'] or not isinstance(action, dict):
            raise ValueError('Team editing unavailable')
        team_id = action.get('team_id')
        team = next((item for item in snapshot['teams'] if item['id'] == team_id), None)
        if team_id is not None and team is None:
            raise ValueError('Unknown team')
        me = next((member for member in team['members'] if str(member['id']) == account_id), None) if team else None
        editable = not team or not team['locked'] and not team['closed'] and team['status'] == 'creating_group'
        leader = editable and (not team or me and me['leader'])
        kind = action.get('action')
        if kind == 'save':
            if not leader or not isinstance(action.get('name'), str) or not action['name'].strip():
                raise ValueError('Team leader and name required')
        elif kind == 'accept':
            if not (editable and me and not me['accepted']):
                raise ValueError('No pending invitation')
        elif kind == 'lock':
            capacity = (snapshot.get('session') or {}).get('max_people')
            if not (leader and team and len(team['members']) == capacity and all(member['accepted'] for member in team['members'])):
                raise ValueError('Team is not ready to lock')
        else:
            raise ValueError('Unknown team action')

    async def team(self, provider: TeamProvider, project_id, scope, account_id, *, current, action=None, key=None, state=None):
        if action is not None:
            self._team_action(state, action, project_id, scope, account_id)
            if not key:
                raise ValueError('Missing team operation key')
            value = await self._dispatch(provider.change_project_team, project_id, scope, account_id, action, key, current=current)
        else:
            value = await self._dispatch(provider.get_project_team, project_id, scope, account_id, current=current)
        return team_state(value, project_id, scope, account_id)
