"""Compose and review a host-scoped report without replaying uncertain writes."""
import webbrowser
from uuid import uuid4

from textual import on
from textual.containers import Vertical,VerticalScroll,Horizontal,Grid
from textual.widgets import TextArea

from ft_tui.ui.modal import AppModal
from ft_tui.ui.components import Button,Static
from ft_tui.features.cluster_map.adapters.factory import resolve_cluster_service


class IssueChoiceButton(Button):
    """Keep the API choice separate from its translated label."""

    def __init__(self,group,value,selected=False):
        super().__init__(value,classes='issue-choice',variant='primary' if selected else 'default')
        self.group=group;self.value=value
        self.set_class(selected,'selected')


class ClusterIssueModal(AppModal):
    BINDINGS=[('escape','close','Close')]
    DEFAULT_CSS='''
    ClusterIssueModal { background: $background 65%; }
    ClusterIssueModal #issue-dialog { width: 86; max-width: 96%; height: 42; max-height: 94%; padding: 1 2; border: round $primary; background: $surface; }
    ClusterIssueModal VerticalScroll { height: 1fr; }
    ClusterIssueModal Static { height: auto; margin-bottom: 1; }
    ClusterIssueModal .issue-choices { grid-size: 2; grid-rows: auto; grid-gutter: 0 1; height: auto; margin-bottom: 1; }
    ClusterIssueModal .issue-choice { width: 1fr; min-width: 0; height: auto; min-height: 3; text-wrap: wrap; }
    /* Preserve the complete selection outline through variant hover/press rules. */
    ClusterIssueModal .issue-choice.selected { text-style: bold; border: solid $accent !important; }
    ClusterIssueModal TextArea { height: 9; min-height: 4; }
    ClusterIssueModal #issue-actions { height: auto; min-height: 3; }
    ClusterIssueModal #issue-actions Button { width: 1fr; min-width: 8; }
    ClusterIssueModal #issue-preview { border: round $accent; padding: 0 1; }
    '''

    def __init__(self,workstation):
        super().__init__()
        self.workstation=workstation;self.hostname=workstation.hostname
        self.provider=workstation.app.provider
        self.selection=dict(category=None,component=None,problem=None)
        self.options={};self.can_submit=False;self.busy=False;self.attempted=False;self.reviewed=False
        self.idempotency_key=str(uuid4())

    @property
    def service(self):
        return getattr(self.workstation,'service',None) or resolve_cluster_service(self.app)

    def t(self,text):return self.workstation.t(text)

    def compose(self):
        with Vertical(id='issue-dialog'):
            yield Static(self.t('Report an issue on {host}').format(host=self.hostname),markup=False,localize=False)
            with VerticalScroll():
                yield Static('Review existing reports before submitting a new issue.')
                yield Static('',id='issue-existing',markup=False,localize=False)
                yield Static('',id='issue-status',markup=False,localize=False)
                yield Static('Type')
                yield Grid(id='issue-type',classes='issue-choices')
                yield Static('Component')
                yield Grid(id='issue-component',classes='issue-choices')
                yield Static('Problem')
                yield Grid(id='issue-problem',classes='issue-choices')
                yield Static('Description')
                yield Static('Describe what happened, when it started, any error messages, and what you tried.')
                yield TextArea('',id='issue-description')
                yield Static('0 / 2000',id='issue-length',localize=False)
                yield Static('',id='issue-preview',markup=False,localize=False)
            with Horizontal(id='issue-actions'):
                yield Button('Cancel',id='issue-cancel')
                yield Button('Open cluster map',id='issue-browser')
                yield Button('Review report',id='issue-review',variant='primary',disabled=True)
                yield Button('Submit report',id='issue-submit',variant='primary',disabled=True)

    def on_mount(self):
        self.query_one('#issue-preview').display=False
        self.query_one('#issue-submit').display=False
        for widget in self.query('*'):
            apply=getattr(widget,'apply_language',None)
            if apply:apply()
        self.run_worker(self._load(),group='issue-options',exclusive=True)
        self.set_interval(.5,self._check_context)

    def _valid(self):return self.is_mounted and self.workstation._valid()

    def _check_context(self):
        if not self.workstation._valid():self.dismiss(False)

    def action_close(self):
        # A running write is allowed to finish before closing this modal.
        if not self.busy:self.dismiss(False)

    async def _load(self):
        status=self.query_one('#issue-status',Static);status.update(self.t('Loading reports…'))
        try:
            data=await self.service.options(self.provider,self._valid)
            if not self._valid():return
            self.options=data['options'];self.can_submit=data['can_submit']
            self.selection['category']=next(iter(self.options))
            self._reset_component()
            await self._render_choices('category','component','problem')
            status.update(self.t('Reporting as {login}').format(login=data['reporter_login']) if self.can_submit else self.t('Direct reporting is unavailable for this account. Use the cluster map website.'))
        except Exception:
            if self._valid():status.update(self.t('Report options unavailable. Open the cluster map website to report this issue.'))
        if not self._valid():return
        lines=[item['title'] for item in self.workstation.items if item['status']!='resolved']
        caption=self.t('No known open reports') if not lines else '\n'.join('• '+line for line in lines)
        if not self.workstation.reports_loaded:caption=self.t('Reports unavailable.')
        elif self.workstation.next_cursor:caption+='\n'+self.t('More reports are available in workstation details.')
        if self.workstation.reports_stale:caption+='\n'+self.t('Saved reports (stale)')
        self.query_one('#issue-existing',Static).update(caption)
        self._update()

    def _reset_component(self):
        components=self.options.get(self.selection['category'],{})
        self.selection['component']=next(iter(components),None)
        self._reset_problem()

    def _reset_problem(self):
        problems=self.options.get(self.selection['category'],{}).get(self.selection['component'],[])
        self.selection['problem']=problems[0] if len(problems)==1 else None

    async def _render_choices(self,*groups):
        choices={'category':self.options,
                 'component':self.options.get(self.selection['category'],{}),
                 'problem':self.options.get(self.selection['category'],{}).get(self.selection['component'],[])}
        for group in groups:
            container=self.query_one('#issue-'+('type' if group=='category' else group),Grid)
            await container.remove_children()
            buttons=[IssueChoiceButton(group,value,self.selection[group]==value) for value in choices[group]]
            if buttons:await container.mount(*buttons)
            for button in buttons:button.apply_language()

    async def _choose(self,button):
        if not self._valid() or self.busy or self.attempted or not self.options:return
        group=button.group
        if self.selection[group]==button.value:return
        self.selection[group]=button.value
        for sibling in self.query(IssueChoiceButton):
            if sibling.group==group:
                selected=sibling.value==button.value
                sibling.variant='primary' if selected else 'default'
                sibling.set_class(selected,'selected')
        if group=='category':
            self._reset_component()
            await self._render_choices('component','problem')
        elif group=='component':
            self._reset_problem()
            await self._render_choices('problem')
        self._edit();self._update()

    @on(TextArea.Changed,'#issue-description')
    def description_changed(self,event):
        event.stop();self._edit();self._update()

    def _edit(self):
        if not self.is_mounted:return
        self.reviewed=False
        self.query_one('#issue-preview').display=False
        self.query_one('#issue-submit').display=False
        self.query_one('#issue-review').display=True

    def _draft(self):
        category=self.selection['category']
        component=self.selection['component']
        problem=self.selection['problem']
        description=self.query_one('#issue-description',TextArea).text
        if (not isinstance(category,str) or not isinstance(component,str) or not isinstance(problem,str)
            or problem not in self.options.get(category,{}).get(component,[])
            or not description.strip() or len(description.encode('utf-16-le'))//2>2000):return None
        return dict(category=category,component=component,problem=problem,description=description.strip())

    def _update(self):
        length=len(self.query_one('#issue-description',TextArea).text.encode('utf-16-le'))//2
        self.query_one('#issue-length',Static).update(f'{length} / 2000')
        disabled=not self.can_submit or self.busy or self.attempted
        self.query_one('#issue-review',Button).disabled=disabled or self._draft() is None
        self.query_one('#issue-submit',Button).disabled=disabled or not self.reviewed
        for button in self.query(IssueChoiceButton):button.disabled=self.busy or self.attempted
        self.query_one('#issue-description',TextArea).read_only=self.busy or self.attempted
        self.query_one('#issue-cancel',Button).disabled=self.busy

    @on(Button.Pressed)
    async def pressed(self,event):
        if isinstance(event.button,IssueChoiceButton):
            event.stop()
            await self._choose(event.button)
            return
        ident=event.button.id
        if ident=='issue-cancel':self.action_close()
        elif ident=='issue-browser':webbrowser.open('https://cluster-map.42angouleme.fr/')
        elif ident=='issue-review':
            draft=self._draft()
            if not draft or not self._valid():return
            self.reviewed=True
            preview=self.query_one('#issue-preview',Static)
            preview.update(f'{self.hostname} - {draft["category"]} - {draft["component"]} - {draft["problem"]}\n\n{draft["description"]}')
            preview.display=True;preview.scroll_visible()
            self.query_one('#issue-review').display=False;self.query_one('#issue-submit').display=True
            self._update()
        elif ident=='issue-submit':
            if self._valid() and self.can_submit and self.reviewed and not self.busy and not self.attempted:
                self.busy=True;self.attempted=True;self._update()
                self.run_worker(self._submit(),group='issue-submit',exclusive=True)
        else:return
        event.stop()

    async def _submit(self):
        draft=self._draft()
        if not draft or not self._valid():self.busy=False;return
        status=self.query_one('#issue-status',Static);status.update(self.t('Submitting report…'))
        try:
            result=await self.service.submit(self.provider,self.hostname,draft,self.idempotency_key,self._valid)
            if self._valid():self.dismiss(True)
        except Exception as error:
            if self._valid():
                response=getattr(error,'response',None)
                code=''
                if response is not None:
                    try:code=response.json().get('error','')
                    except (ValueError,AttributeError):pass
                message={
                    'cluster_issue_reporter_mismatch':'Direct reporting is unavailable for this account. Use the cluster map website.',
                    'cluster_issue_invalid':'The server rejected the report. Check your description before creating a new report.',
                    'invalid_cluster_issue':'The server rejected the report. Check your description before creating a new report.',
                    'cluster_map_rate_limited':'Too many requests. Wait before creating a new report.',
                    'cluster_map_session_rejected':'The report session expired. Try again after the session has been refreshed.',
                    'cluster_issue_duplicate':'A matching report already exists. Refresh workstation reports before reporting again.',
                    'cluster_issue_duplicates_unavailable':'Existing reports could not be checked. Refresh workstation reports before reporting again.',
                }.get(code,'Report outcome unknown. Check existing reports before creating another report.')
                status.update(self.t(message));status.scroll_visible()
        finally:
            self.busy=False
            if self.is_mounted:self._update()
