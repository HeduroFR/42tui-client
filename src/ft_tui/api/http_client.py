"""HTTP provider for paged official catalog and isolated personal observations."""
from urllib.parse import quote
import math
import base64
import re
from hashlib import sha256
from datetime import datetime
from pathlib import Path
from typing import Any
from ft_tui.features.catalog.models import CatalogScope,catalog_page,project_summary,positive
from .client_interface import CursusSnapshot
from .oauth_client import OAuthClient

from ft_tui.features.projects.subjects.models import SubjectPendingError


class HttpProjectProvider:
    def get_correction_slots(self, begin, end):
        from ft_tui.features.corrections.types import slot_snapshot
        return slot_snapshot(self.api.request('GET', '/v1/me/slots', params={
            'begin_at': begin.isoformat(), 'end_at': end.isoformat()}))

    def _change_correction_slot(self, draft):
        from uuid import uuid4
        value = self.api.request('POST', '/v1/me/slots', json=draft,
                                 headers={'Idempotency-Key': str(uuid4())})
        if not isinstance(value, dict) or value.get('status') != 'saved':
            raise ValueError('Slot outcome unknown; refresh before trying again')
        return value

    def save_correction_slot(self, slot, begin, end):
        if slot is not None and slot.booked:
            raise ValueError('Booked slots cannot be changed')
        return self._change_correction_slot({'action': 'save',
            'ids': [int(i) for i in slot.ids] if slot else [],
            'begin_at': begin.isoformat(), 'end_at': end.isoformat()})

    def delete_correction_slot(self, slot):
        if slot.booked:
            raise ValueError('Booked slots cannot be changed')
        return self._change_correction_slot({'action': 'delete', 'ids': [int(i) for i in slot.ids]})

    def event_stream(self, stop):
        return self.api.event_stream(stop)

    def get_social(self):
        from ft_tui.features.social.models import overview
        return overview(self.api.request('GET', '/v1/social'))

    def get_poke_neighbours(self):
        from ft_tui.features.social.models import identity
        value = self.api.request('GET', '/v1/social/neighbours')
        if not isinstance(value, dict) or not isinstance(value.get('items'), list):
            raise ValueError('Invalid poke neighbours')
        return [identity(item) for item in value['items']]

    def social_action(self, draft):
        return self.api.request('POST', '/v1/social/actions', json=draft)

    def get_clubs(self, campus_id):
        from ft_tui.features.clubs.models import overview
        if type(campus_id) is not int or campus_id < 1:
            raise ValueError('Invalid club campus')
        return overview(self.api.request('GET', '/v1/clubs', params={'campus_id': campus_id}))

    def create_club(self, draft):
        from ft_tui.features.clubs.models import club
        return club(self.api.request('POST', '/v1/clubs', json=draft))

    def club_action(self, selected_club, draft):
        from ft_tui.features.clubs.models import club, club_id
        return club(self.api.request('POST', f'/v1/clubs/{quote(club_id(selected_club), safe="")}/actions', json=draft))

    def set_club_preferences(self, draft):
        from ft_tui.features.clubs.models import preferences
        return preferences(self.api.request('POST', '/v1/clubs/preferences', json=draft))

    def poll_clubs(self):
        from ft_tui.features.clubs.models import poll
        return poll(self.api.request('POST', '/v1/clubs/poll', json={}))

    def get_cluster_issue_options(self):
        value=self.api.request('GET','/v1/cluster-map/issue-options')
        options=value.get('options') if isinstance(value,dict) else None
        if (not isinstance(options,dict) or not 1<=len(options)<=10
            or type(value.get('can_submit')) is not bool or value.get('max_description_length')!=2000
            or not isinstance(value.get('reporter_login'),str) or not value['reporter_login']):
            raise ValueError('Invalid report options')
        for category,components in options.items():
            if not isinstance(category,str) or not category or len(category)>128 or not isinstance(components,dict) or not 1<=len(components)<=20:
                raise ValueError('Invalid report category')
            for component,problems in components.items():
                if (not isinstance(component,str) or not component or len(component)>128 or not isinstance(problems,list)
                    or not 1<=len(problems)<=30 or any(not isinstance(p,str) or not p or len(p)>128 for p in problems)
                    or len(set(problems))!=len(problems)):
                    raise ValueError('Invalid report component')
        return value

    def submit_cluster_issue(self,hostname,draft,idempotency_key):
        from uuid import UUID
        from ft_tui.features.cluster_map.geometry import positions
        if hostname not in positions('all') or UUID(idempotency_key).version!=4:raise ValueError('Invalid report request')
        if (not isinstance(draft,dict) or set(draft)!={'category','component','problem','description'}
            or any(not isinstance(v,str) or not v.strip() for v in draft.values())
            or len(draft['description'].encode('utf-16-le'))//2>2000):raise ValueError('Invalid report draft')
        value=self.api.request('POST',f'/v1/cluster-map/hosts/{hostname}/issues',json=draft,headers={'Idempotency-Key':idempotency_key})
        if not isinstance(value,dict) or value.get('hostname')!=hostname or value.get('status')!='submitted':
            raise ValueError('Report outcome unknown')
        return value

    def get_cluster_portrait(self,hostname):
        from ft_tui.features.cluster_map.models import cluster_portrait
        from ft_tui.features.cluster_map.geometry import positions
        if hostname not in positions('all'):raise ValueError('Invalid cluster workstation')
        return cluster_portrait(self.api.request('GET',f'/v1/cluster-map/hosts/{hostname}/portrait'),hostname)

    def get_cluster_map(self):
        from ft_tui.features.cluster_map.models import cluster_map_snapshot
        return cluster_map_snapshot(self.api.request('GET','/v1/cluster-map'))

    def get_cluster_issues(self, hostname, *, include_resolved=False, cursor=None):
        from ft_tui.features.cluster_map.models import cluster_issue_page
        from ft_tui.features.cluster_map.geometry import positions
        if hostname not in positions('all') or type(include_resolved) is not bool:
            raise ValueError('Invalid cluster report query')
        if cursor is not None and (not isinstance(cursor,str) or not re.fullmatch(r'[1-9]\d{0,2}',cursor) or int(cursor)>200):
            raise ValueError('Invalid cluster report cursor')
        params={'include_resolved':'true' if include_resolved else 'false'}
        if cursor is not None:params['cursor']=cursor
        value=self.api.request('GET',f'/v1/cluster-map/hosts/{quote(hostname,safe="")}/issues',params=params)
        return cluster_issue_page(value,hostname,include_resolved)

    def list_campuses(self):
        from .campus_types import campus_directory
        return campus_directory(self.api.request('GET', '/v1/campuses'))

    def __init__(self,api=None,*,base_url="https://api.42tui.app",oauth_client=None):
        self._subject_documents = {}
        self.api=api if api is not None else oauth_client if oauth_client is not None else OAuthClient(base_url)

    def list_cursuses(self):
        value=self.api.request('GET','/v1/cursuses')
        if not isinstance(value,dict) or not isinstance(value.get('cursuses'),list):raise ValueError('Invalid cursus response')
        return [self._cursus(x) for x in value['cursuses']]

    def get_profile(self):
        value=self.api.request('GET','/v1/me')
        if not isinstance(value,dict) or not isinstance(value.get('account_id'),str) or not value['account_id'].isdigit() or not isinstance(value.get('login'),str):raise ValueError('Invalid account profile')
        return value

    def search_students(self, query, *, limit=20, exclude_ids=()):
        from ft_tui.features.friends.models import student_search_result
        if not isinstance(query, str) or len(query) > 128 or sum(c.isalnum() for c in query) < 2 or type(limit) is not int or not 1 <= limit <= 20:
            raise ValueError('Invalid student search query')
        if len(exclude_ids) > 200 or any(not isinstance(i, str) or not re.fullmatch(r'[1-9]\d{0,15}', i) or int(i) > 9007199254740991 for i in exclude_ids):
            raise ValueError('Invalid student exclusions')
        params = {'q': query, 'limit': limit}
        if exclude_ids:
            params['exclude_ids'] = ','.join(exclude_ids)
        return student_search_result(self.api.request('GET', '/v1/users/search', params=params), limit)

    def list_friend_directory_page(self, campus_id, page=1):
        from ft_tui.features.friends.models import friend_directory_page
        if not positive(campus_id) or not positive(page) or page > 100:
            raise ValueError('Invalid friend directory query')
        value = self.api.request('GET', '/v1/friends/directory/users', params={'campus_id': campus_id, 'page': page})
        return friend_directory_page(value, campus_id, page)

    def get_friend_core(self, login, cursus_id, *, refresh=False, user_id=None):
        return self.get_friend(login,cursus_id,refresh=refresh,user_id=user_id,include_xp=False)

    def get_friend_summary(self, login, cursus_id, *, refresh=False):
        from ft_tui.features.friends.models import LOGIN, friend_snapshot
        if not isinstance(login, str) or not LOGIN.fullmatch(login) or not positive(cursus_id):
            raise ValueError('Invalid friend query')
        params = {'cursus_id': cursus_id, 'view': 'summary', 'include_xp': 'false'}
        if refresh:
            params['refresh'] = 'true'
        value = self.api.request('GET', f'/v1/friends/{quote(login, safe="")}', params=params, timeout=30.0)
        return friend_snapshot(value, login, cursus_id)

    def get_friend_summaries(self, logins, cursus_id):
        import json
        from ft_tui.features.friends.models import LOGIN, friend_snapshot
        if not isinstance(logins, list) or not 1 <= len(logins) <= 50 or any(not isinstance(login, str) or not LOGIN.fullmatch(login) for login in logins) or len(set(logins)) != len(logins) or not positive(cursus_id):
            raise ValueError('Invalid friend batch')
        result = self.api.request('GET', '/v1/friends/summaries', params={
            'cursus_id': cursus_id, 'logins': json.dumps(logins, ensure_ascii=False)}, timeout=15.0)
        if not isinstance(result, dict) or not isinstance(result.get('items'), list) or not isinstance(result.get('missing'), list):
            raise ValueError('Invalid friend summaries')
        seen = set()
        for value in result['items']:
            login = value.get('login') if isinstance(value, dict) else None
            if login not in logins or login in seen or value.get('details_complete') is not False:
                raise ValueError('Invalid friend summary identity')
            friend_snapshot(value, login, cursus_id)
            seen.add(login)
        if any(not isinstance(login, str) or login not in logins or login in seen for login in result['missing']) or len(set(result['missing'])) != len(result['missing']) or seen | set(result['missing']) != set(logins):
            raise ValueError('Invalid friend summary coverage')
        return result['items']

    def get_friend(self, login, cursus_id, *, refresh=False, user_id=None, include_xp=True):
        from ft_tui.features.friends.models import LOGIN, friend_snapshot
        if not isinstance(login, str) or not LOGIN.fullmatch(login) or not positive(cursus_id):
            raise ValueError('Invalid friend query')
        params = {'cursus_id': cursus_id}
        if not include_xp:
            params['include_xp'] = 'false'
        if refresh:
            params['refresh'] = 'true'
        if user_id is not None:
            if not isinstance(user_id, str) or not re.fullmatch(r'[1-9]\d{0,15}', user_id) or int(user_id) > 9007199254740991:
                raise ValueError('Invalid selected user ID')
            params['user_id'] = user_id
        value = self.api.request('GET', f'/v1/friends/{quote(login, safe="")}', params=params, timeout=180.0)
        return friend_snapshot(value, login, cursus_id, user_id=user_id)

    def get_student_portrait(self, user_id):
        from ft_tui.features.profiles.models import student_id, student_portrait
        student_id(user_id)
        return student_portrait(
            self.api.request('GET', f'/v1/users/{user_id}/profile/portrait'), user_id,
        )

    def get_student_profile(self, user_id, *, refresh=False):
        from ft_tui.features.profiles.models import student_id, student_profile
        student_id(user_id)
        params = {'refresh': 'true'} if refresh else {}
        value = self.api.request('GET', f'/v1/users/{user_id}/profile', params=params, timeout=180.0)
        return student_profile(value, user_id)

    def get_student_attendance(self, user_id, *, refresh=False):
        from ft_tui.features.profiles.models import student_id, student_attendance
        student_id(user_id)
        params = {'refresh': 'true'} if refresh else {}
        return student_attendance(self.api.request('GET', f'/v1/users/{user_id}/profile/attendance', params=params), user_id)

    def get_student_goals(self, user_id, cursus_id):
        from ft_tui.features.profiles.models import student_id, student_goals
        student_id(user_id)
        if not positive(cursus_id):
            raise ValueError('Invalid profile cursus')
        value = self.api.request('GET', f'/v1/users/{user_id}/profile/goals', params={'cursus_id': cursus_id}, timeout=180.0)
        return student_goals(value, user_id, cursus_id)

    def get_goals(self, cursus_id, account_id):
        from ft_tui.features.profiles.goals import goals_response
        if not positive(cursus_id): raise ValueError('Invalid goals cursus')
        return goals_response(self.api.request('GET', '/v1/me/goals', params={'cursus_id': cursus_id}), account_id, cursus_id)

    def list_catalog_page(self,scope,**filters):
        params={**scope.params(),**{k:v for k,v in filters.items() if v is not None}}
        value=catalog_page(self.api.request('GET','/v1/catalog/projects',params=params),scope)
        track=filters.get('track')
        if track and any(x['track'] not in (track,'shared') for x in value['items']):raise ValueError('Mixed catalog tracks')
        return value

    def get_catalog_project(self,project_id,scope,snapshot_id=None):
        if not positive(project_id):raise ValueError('Invalid official project ID')
        params=scope.params()
        if snapshot_id:params['snapshot_id']=snapshot_id
        value=self.api.request('GET',f'/v1/catalog/projects/{project_id}',params=params)
        clean=project_summary(value)
        if clean['project_id']!=project_id or snapshot_id and clean.get('snapshot_id')!=snapshot_id:raise ValueError('Catalog detail identity mismatch')
        return clean

    def get_project_activity(self, project_id, scope, account_id, *, refresh=False):
        from ft_tui.features.projects.activity.models import project_activity
        if not positive(project_id): raise ValueError('Invalid official project ID')
        params = scope.params()
        if refresh: params['refresh'] = 'true'
        value = self.api.request('GET', f'/v1/me/projects/{project_id}/activity', params=params)
        return project_activity(value, project_id, scope, account_id)

    def get_team_evaluations(self, project_id, team_id, scope, account_id, *, refresh=False):
        from ft_tui.features.projects.activity.models import team_evaluations
        if not positive(project_id) or not positive(team_id): raise ValueError('Invalid project or team ID')
        params = scope.params()
        if refresh: params['refresh'] = 'true'
        value = self.api.request('GET', f'/v1/me/projects/{project_id}/teams/{team_id}/evaluations', params=params)
        return team_evaluations(value, project_id, team_id, scope, account_id)

    def get_friend_project_activity(self, project_id, attempt_id, user_id, scope, account_id, *, refresh=False):
        from ft_tui.features.projects.activity.models import friend_activity
        if not positive(project_id) or not positive(attempt_id) or not isinstance(user_id,str) or not re.fullmatch(r'[1-9][0-9]{0,15}',user_id) or int(user_id)>9007199254740991:
            raise ValueError('Invalid friend project identity')
        params=scope.params()
        if refresh:params['refresh']='true'
        value=self.api.request('GET',f'/v1/users/{user_id}/projects/{project_id}/attempts/{attempt_id}/activity',params=params)
        return friend_activity(value,project_id,attempt_id,user_id,scope,account_id)

    def get_friend_project_evaluations(self, project_id, attempt_id, user_id, team_id, scope, account_id, *, refresh=False):
        from ft_tui.features.projects.activity.models import friend_evaluations
        if not positive(project_id) or not positive(attempt_id) or not positive(team_id) or not isinstance(user_id,str) or not re.fullmatch(r'[1-9][0-9]{0,15}',user_id) or int(user_id)>9007199254740991:
            raise ValueError('Invalid friend project identity')
        params=scope.params()
        if refresh:params['refresh']='true'
        value=self.api.request('GET',f'/v1/users/{user_id}/projects/{project_id}/attempts/{attempt_id}/teams/{team_id}/evaluations',params=params)
        return friend_evaluations(value,project_id,attempt_id,user_id,team_id,scope,account_id)

    def get_project_team(self, project_id, scope, account_id):
        from ft_tui.features.projects.registration.team_types import team_state
        if not positive(project_id): raise ValueError('Invalid project ID')
        return team_state(self.api.request('GET', f'/v1/me/projects/{project_id}/team', params=scope.params()), project_id, scope, account_id)

    def change_project_team(self, project_id, scope, account_id, action, idempotency_key):
        from uuid import UUID
        from ft_tui.features.projects.registration.team_types import team_state
        if not positive(project_id): raise ValueError('Invalid project ID')
        UUID(idempotency_key)
        value = self.api.request('POST', f'/v1/me/projects/{project_id}/team', json={**action, **scope.params()}, headers={'Idempotency-Key': idempotency_key})
        return team_state(value, project_id, scope, account_id)

    def get_project_registration(self, project_id, scope, account_id):
        from ft_tui.features.projects.registration.types import registration_state
        if not positive(project_id):raise ValueError('Invalid official project ID')
        value=self.api.request('GET',f'/v1/me/projects/{project_id}/registration',params=scope.params())
        return registration_state(value,project_id,scope,account_id)

    def refresh_project_registration(self, project_id, scope, account_id):
        from ft_tui.features.projects.registration.types import registration_state
        if not positive(project_id):raise ValueError('Invalid official project ID')
        value=self.api.request('POST',f'/v1/me/projects/{project_id}/registration/refresh',json=scope.params())
        return registration_state(value,project_id,scope,account_id)

    def register_project(self, project_id, scope, account_id, idempotency_key):
        from uuid import UUID
        from ft_tui.features.projects.registration.types import registration_result
        if not positive(project_id):raise ValueError('Invalid official project ID')
        UUID(idempotency_key)
        value=self.api.request('POST',f'/v1/me/projects/{project_id}/registration',json=scope.params(),headers={'Idempotency-Key':idempotency_key})
        return registration_result(value,project_id,scope,account_id)

    def list_branches(self,scope,track,cursor=None):
        if track not in ('old','new'):raise ValueError('Choose a Common Core track')
        params={**scope.params(),'track':track,'limit':100}
        if cursor:params['cursor']=cursor
        value=self.api.request('GET','/v1/catalog/branches',params=params)
        if not isinstance(value,dict) or not isinstance(value.get('items'),list) or len(value['items'])>100 or any(x.get('track')!=track for x in value['items']):raise ValueError('Invalid branch page')
        return value

    def get_branch(self,scope,track,branch_id,snapshot_id=None):
        params={**scope.params(),'track':track}
        if snapshot_id:params['snapshot_id']=snapshot_id
        value=self.api.request('GET',f'/v1/catalog/branches/{branch_id}',params=params)
        if not isinstance(value,dict) or value.get('branch_id')!=branch_id or value.get('track')!=track:raise ValueError('Branch identity mismatch')
        return value

    def get_account_projects(self,cursus_id,cursor=None):
        params={'cursus_id':cursus_id,'limit':100}
        if cursor:params['cursor']=cursor
        value=self.api.request('GET','/v1/me/projects',params=params)
        if not isinstance(value,dict) or not isinstance(value.get('account_id'),str) or not isinstance(value.get('items'),list) or len(value['items'])>100 or not isinstance(value.get('snapshot_id'),str):raise ValueError('Invalid personal project page')
        if value.get('next_cursor') is not None and not isinstance(value['next_cursor'],str):raise ValueError('Invalid personal cursor')
        seen=set()
        for p in value['items']:
            if not isinstance(p,dict) or not positive(p.get('id')) or not positive(p.get('project_id')) or not isinstance(p.get('slug'),str) or not p['slug'] or not isinstance(p.get('name'),str) or not p['name']:raise ValueError('Invalid personal project identity')
            if p['id'] in seen:raise ValueError('Duplicate attempt')
            seen.add(p['id'])
            if not isinstance(p.get('cursus_ids'),list) or not all(positive(x) for x in p['cursus_ids']) or cursus_id not in p['cursus_ids']:raise ValueError('Invalid personal cursus')
            if not isinstance(p.get('status'),str) or not p['status'] or p.get('validated') is not None and type(p['validated']) is not bool:raise ValueError('Invalid personal status')
            mark=p.get('final_mark')
            if mark is not None and (type(mark) not in (int,float) or not math.isfinite(mark)):raise ValueError('Invalid personal mark')
            if p.get('vogsphere_url') is not None and not isinstance(p['vogsphere_url'],str):raise ValueError('Invalid personal repository')
        return value

    def get_curriculum(self,scope):
        value=self.api.request('GET','/v1/me/curriculum',params=scope.params())
        if not isinstance(value,dict) or value.get('cursus_id')!=scope.cursus_id or value.get('campus_id')!=scope.campus_id or not isinstance(value.get('account_id'),str):raise ValueError('Personal curriculum scope mismatch')
        if not isinstance(value.get('snapshot_id'),str) or not value['snapshot_id']:raise ValueError('Invalid personal snapshot')
        track=value.get('track');rank=value.get('rank');reg=value.get('registration')
        if not isinstance(track,dict) or track.get('track') not in (None,'old','new'):raise ValueError('Invalid personal track')
        if not isinstance(rank,dict) or rank.get('rank') is not None and (type(rank['rank']) is not int or rank['rank']<0):raise ValueError('Invalid personal rank')
        if not isinstance(reg,dict) or reg.get('status') not in ('available','unavailable','unknown') or type(reg.get('stale')) is not bool or not isinstance(reg.get('project_ids'),list) or not all(positive(x) for x in reg['project_ids']):raise ValueError('Invalid registration source')
        return value

    def get_subject_reference_sha256(self, slug):
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,255}", slug):
            raise ValueError("Invalid project slug")
        self._subject_documents.pop(slug, None)
        import httpx
        try:
            value = self.api.request("GET", f"/v1/me/subjects/{slug}")
        except httpx.HTTPStatusError as error:
            try:
                code = error.response.json().get("error")
            except (ValueError, AttributeError):
                code = None
            if error.response.status_code == 403 and code == "subject_permission_denied":
                raise ValueError("42 denied access to subject attachments for this authorization.") from error
            raise
        if not isinstance(value, dict):
            raise ValueError("Invalid subject response")
        if value.get("status") in {"pending", "unavailable"}:
            reason = value.get("reason")
            allowed = {"web_profile_busy", "web_login_required", "web_login_incomplete",
                       "web_login_form_unavailable", "browser_not_installed", "browser_dependency_missing",
                       "browser_launch_failed", "subject_link_not_found", "subject_link_ambiguous",
                       "web_subject_unavailable", "reauthorization_required", "subject_unavailable",
                       "invalid_subject_pdf", "invalid_subject_url", "subject_too_large", "subject_lease_lost"}
            message = reason if isinstance(reason, str) and reason in allowed else "pending"
            raise SubjectPendingError(message)
        digest, encoded = value.get("sha256"), value.get("pdf_base64")
        if digest is None and encoded is None:
            self._subject_documents = {slug: None}
            return None
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("Invalid subject fingerprint")
        if not isinstance(encoded, str) or len(encoded) > 28 * 1024 * 1024:
            raise ValueError("Invalid subject PDF size")
        try:
            pdf = base64.b64decode(encoded, validate=True)
        except ValueError as error:
            raise ValueError("Invalid subject PDF encoding") from error
        if len(pdf) > 20 * 1024 * 1024 or not pdf.startswith(b"%PDF-") or sha256(pdf).hexdigest() != digest:
            raise ValueError("Invalid subject PDF or fingerprint")
        # Keep only the latest document, until the worker installs it.
        self._subject_documents = {slug: pdf}
        return digest

    def download_subject_pdf(self, slug, destination: Path):
        if slug not in self._subject_documents:
            if self.get_subject_reference_sha256(slug) is None:
                return False
        pdf = self._subject_documents.pop(slug)
        if pdf is None:
            return False
        Path(destination).write_bytes(pdf)
        return True

    @staticmethod
    def _cursus(item: Any) -> CursusSnapshot:
        if not isinstance(item, dict):
            raise ValueError("Invalid cursus item from 42TUI API")
        cursus_id, name = item.get("id"), item.get("name")
        if isinstance(cursus_id, bool) or not isinstance(cursus_id, int) or cursus_id <= 0:
            raise ValueError("Invalid cursus item from 42TUI API")
        if not isinstance(name, str) or not name:
            raise ValueError("Invalid cursus item from 42TUI API")

        def parse_datetime(value: Any) -> datetime | None:
            if value is None:
                return None
            if not isinstance(value, str):
                raise ValueError("Invalid cursus timestamp from 42TUI API")
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as error:
                raise ValueError("Invalid cursus timestamp from 42TUI API") from error

        return CursusSnapshot(cursus_id, name, parse_datetime(item.get("begin_at")), parse_datetime(item.get("end_at")))
