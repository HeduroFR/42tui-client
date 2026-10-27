"""Account-fenced registration workers and compact Project Details controls."""
import asyncio
from datetime import datetime,timezone
from copy import deepcopy
from functools import partial
from uuid import uuid4

from ft_tui.i18n import translate
from ft_tui.features.projects.registration.presentation import registration_view
from ..registration.service import RegistrationService, StaleRegistrationContext
from ft_tui.ui.components import Button,Static,escape


class ProjectRegistrationMixin:
    def _registration_operations(self):
        service = getattr(self, 'registration_service', None)
        return service if service is not None else RegistrationService()

    def _registration_context(self):
        project=self.projects.get(self.selected_project_key or '')
        scope=self._catalog_scope()
        if project is None or not project.official_project_id or not scope or not self.account_id:
            return None
        return (self.account_id,scope.cursus_id,scope.campus_id,project.official_project_id)

    def _can_manage_project_team(self, state=None):
        state = state if state is not None else getattr(self, '_registration_state', None)
        context = self._registration_context()
        if not context or not state or state.get('project_mode') != 'group':
            return False
        identity = (state['account_id'], state['context']['cursus_id'], state['context']['campus_id'], state['project_id'])
        operation = state.get('operation')
        return (identity == context and bool(state['relationship'].get('attempt'))
                and state['relationship']['state'] in {'registered', 'in_progress', 'completed', 'failed'}
                and not (operation and operation['outcome'] in {'pending', 'outcome_unknown'}))

    def _registration_storage(self):
        identity=(getattr(self,'account_id',None),getattr(self,'account_generation',None),id(getattr(self,'provider',None)))
        if getattr(self,'_registration_identity',None)!=identity:
            self._registration_identity=identity
            self._registration_states={}
            self._registration_busy={}
            self._registration_keys={}
            self._registration_uncertain=set()
            self._registration_errors={}
            self._registration_epochs={}
            self._registration_state=None
            self._registration_view=None
        return self._registration_states

    def _clear_project_registration(self):
        timer=getattr(self,'_registration_expiry',None)
        if timer:
            timer.stop()
        self._registration_state=None
        self._registration_view=None
        for selector,text in (('#registration-relationship','Registration status unavailable'),
                              ('#registration-feedback','')):
            self.query_one(selector,Static).update(text)
        self.query_one('#registration-feedback',Static).display=False
        for selector in ('#registration-action','#registration-refresh','#registration-intra-link'):
            self.query_one(selector,Button).display=False

    def _load_project_registration(self,project_key:str):
        self._registration_storage()
        self._clear_project_registration()
        context=self._registration_context()
        if context and context not in self._registration_states:
            from ft_tui.features.projects.registration.presentation import cached_registration_state
            from ft_tui.features.catalog.models import CatalogScope
            project=self.projects[project_key]
            self._registration_states[context]=cached_registration_state(project,self.project_curriculum,context[0],CatalogScope(context[1],context[2]))
        if context in self._registration_states:
            self._render_project_registration(self._registration_states[context])
        if context in self._registration_busy:
            return
        if not context or self.provider is None or not hasattr(self.provider,'get_project_registration'):
            return
        self.run_worker(partial(self._registration_request,'read',context,self.provider,self.account_generation,self._registration_epochs.get(context,0)),
                        group='project-registration-read',exclusive=True)

    def _render_project_registration(self,state:dict):
        self._registration_storage()
        current=self._registration_context()
        if current and (state['account_id'],state['context']['cursus_id'],state['context']['campus_id'],state['project_id'])!=current:
            return
        self._registration_state=state
        now=datetime.now(timezone.utc)
        view=registration_view(state,now=now,language=self.language)
        if self._can_manage_project_team(state):
            from dataclasses import replace
            view=replace(view,action='team',enabled=callable(getattr(self.provider,'get_project_team',None)))
        self._registration_view=view
        context=self._registration_context()
        if context in self._registration_uncertain and not state.get('operation') and not state['relationship'].get('attempt'):
            from dataclasses import replace
            view=replace(view,action='refresh',enabled=True,feedback=translate('Registration outcome unknown. Refresh status before trying again.',self.language))
            self._registration_view=view
        busy=context in self._registration_busy
        self.query_one('#registration-relationship',Static).update(view.relationship)
        feedback=self.query_one('#registration-feedback',Static)
        message=self._registration_errors.get(context) or view.feedback
        feedback.update(message)
        feedback.display=bool(message)
        action=self.query_one('#registration-action',Button)
        action.display=view.action!='none'
        label={'register':'Register','refresh':'Refresh status','none':'Register','team':'Manage team'}[view.action]
        if busy:
            label='Registering…' if self._registration_busy[context][-1]=='register' else 'Checking…'
        action.set_source_label(label)
        action.disabled=busy or not view.enabled
        refresh=self.query_one('#registration-refresh',Button)
        refresh.display=view.action!='refresh'
        refresh.disabled=busy or self.provider is None
        link=self.query_one('#registration-intra-link',Button)
        link.display=bool(state.get('intra_url')) and (context in self._registration_uncertain or bool(state.get('operation') and state['operation']['outcome'] in {'pending','outcome_unknown'}))
        link.disabled=busy
        project=self.projects.get(self.selected_project_key or '')
        if project and project.official_project_id==state['project_id']:
            self._render_project_summary(project,state.get('project_mode','unknown'))
            self.query_one('#project-heading',Static).update(f'[bold]{escape(project.name)}[/bold] · {escape(view.relationship)}')
        timer=getattr(self,'_registration_expiry',None)
        if timer:
            timer.stop()
        if view.deadline:
            self._registration_expiry=self.set_timer(max(.05,(view.deadline-now).total_seconds()+.01),
                lambda:self._render_project_registration(state) if self._registration_state is state else None)

    async def _handle_registration_button(self,button_id:str|None)->bool:
        if button_id not in {'registration-action','registration-refresh','registration-intra-link'}:
            return False
        self._registration_storage()
        context=self._registration_context()
        if context in self._registration_busy:
            return True
        state=getattr(self,'_registration_state',None)
        if not context or not state:
            return True
        if button_id=='registration-action' and self._can_manage_project_team(state):
            self.action_project_team()
            return True
        view=registration_view(state,now=datetime.now(timezone.utc),language=self.language)
        action='refresh' if button_id=='registration-refresh' else 'link' if button_id=='registration-intra-link' else view.action
        if context in self._registration_uncertain and action=='register':
            action='refresh'
        if action=='link':
            url=state.get('intra_url')
            if url:
                import webbrowser
                try:
                    if not await asyncio.to_thread(webbrowser.open,url):
                        raise OSError('browser unavailable')
                except Exception:
                    self.query_one('#registration-feedback',Static).update('Could not open the project page.')
            return True
        if action not in {'register','refresh'} or self.provider is None:
            return True
        if action=='register' and not view.enabled:
            self._render_project_registration(state)
            return True
        self._registration_errors.pop(context,None)
        epoch=self._registration_epochs.get(context,0)+1
        self._registration_epochs[context]=epoch
        busy_token=(self.account_generation,id(self.provider),epoch,action)
        self._registration_busy[context]=busy_token
        if action=='register':
            self._registration_keys.setdefault(context,str(uuid4()))
        self._render_project_registration(state)
        self.run_worker(partial(self._registration_request,action,context,self.provider,self.account_generation,epoch,
                            reviewed_state=deepcopy(state)),
                        group=f'project-registration-write-{context}',exclusive=False)
        return True

    async def _handle_registration_action(self):
        await self._handle_registration_button('registration-action')

    async def _registration_request(self,action,context,provider,generation,epoch=None,*,reviewed_state=None):
        self._registration_storage()
        if epoch is None:
            epoch=self._registration_epochs.get(context,0)
        busy_token=(generation,id(provider),epoch,action)
        from ft_tui.features.catalog.models import CatalogScope
        account,cursus,campus,project_id=context
        scope=CatalogScope(cursus,campus)
        def same_account():
            return provider is self.provider and generation==self.account_generation and account==self.account_id
        def current():
            return same_account() and self._registration_epochs.get(context,0)==epoch
        try:
            state = await self._registration_operations().registration(
                provider, action, project_id, scope, account, current=current,
                key=self._registration_keys.get(context),
                state=reviewed_state if reviewed_state is not None else self._registration_states.get(context) or getattr(self,'_registration_state',None))
            if not same_account() or self._registration_epochs.get(context,0)!=epoch:
                return
            if action=='read' and context in self._registration_busy:
                return
            self._registration_errors.pop(context,None)
            self._registration_states[context]=state
            if state.get('operation') and state['operation']['outcome'] not in {'pending','outcome_unknown'} or state['relationship'].get('attempt'):
                self._registration_uncertain.discard(context)
                self._registration_keys.pop(context,None)
            if action=='register' and state.get('operation',{}).get('outcome') in {'registered','already_registered'}:
                # Reuse the normal fenced refresh to update the list and local cache.
                self._request_catalog_refresh()
            if self._registration_context()==context:
                self._render_project_registration(state)
        except StaleRegistrationContext:
            return
        except Exception:
            if not same_account() or self._registration_epochs.get(context,0)!=epoch:
                return
            if action=='register':
                self._registration_uncertain.add(context)
            if self._registration_context()==context:
                message=('Registration outcome unknown. Refresh status before trying again.' if action=='register' else 'Could not refresh registration status.')
                self._registration_errors[context]=message
                old=getattr(self,'_registration_state',None)
                if old:
                    self._render_project_registration(old)
                feedback=self.query_one('#registration-feedback',Static)
                feedback.update(message)
                feedback.display=True
                # Permit a read after failed initial loading, without guessing eligibility.
                if not old:
                    button=self.query_one('#registration-refresh',Button)
                    button.display=True
                    button.disabled=False
        finally:
            if action!='read' and self._registration_busy.get(context)==busy_token:
                self._registration_busy.pop(context,None)
            if same_account() and self._registration_context()==context:
                state=getattr(self,'_registration_state',None)
                if state:
                    self._render_project_registration(state)
