"""Read-only workstation details with independently pinned person identity."""
from ft_tui.features.cluster_map.state import session_label, status_label
from ft_tui.features.cluster_map.experience import estimate_experience,SOURCE as XP_SOURCE
from hashlib import sha256
from time import monotonic
from rich.markup import escape
from textual import on
from textual.await_complete import AwaitComplete
from textual.containers import Vertical,Horizontal,VerticalScroll
from textual.widgets import TabbedContent,Collapsible,ProgressBar
from ft_tui.ui.modal import AppModal
from ft_tui.ui.components import Button,Static,TabPane
from ft_tui.features.friends.adapters.storage import ongoing
from ft_tui.app.read_cache import backend_origin
from ft_tui.i18n import translate
from ft_tui.features.cluster_map.adapters.factory import resolve_cluster_service
from ft_tui.features.cluster_map.views.portrait import ClusterPortrait


class ClusterWorkstationModal(AppModal):
    BINDINGS=[('escape','close','Close')]

    def t(self,text):return translate(text,getattr(self.app,'language','en'))

    def __init__(self,workspace,hostname,seat,initial_tab,context):
        super().__init__()
        self.workspace=workspace;self.hostname=hostname;self.seat=seat;self.person_seat=seat
        self.initial_tab='workstation' if initial_tab=='issues' else initial_tab;self.context=context;self.include_resolved=False
        self.items=[];self.next_cursor=None;self.issue_generation=0;self.person_generation=0
        self.reports_loaded=False;self.reports_stale=False;self.issue_busy=False
        self.issue_retry_at=0
        self.loaded_pages=1
        self._close_requested=False;self._dismissed=False;self._close_result=None
        self.person_data={};self.adding_friend=False;self._person_cache_fresh=False

    @property
    def service(self):
        return getattr(self.workspace,'service',None) or resolve_cluster_service(self.app)

    def compose(self):
        with Vertical(id='cluster-dialog'):
            with Horizontal(id='cluster-modal-header'):
                yield Button('×',id='cluster-close',tooltip='Close',square=True, variant='danger')
            with Vertical(id='cluster-occupant-notice'):
                yield Static('Occupant changed. The person shown below is preserved.',markup=False,localize=True)
                yield Button('View latest',id='cluster-latest')
            with TabbedContent(initial='cluster-'+self.initial_tab,id='cluster-modal-tabs'):
                with TabPane('Person',id='cluster-person'):
                    with Horizontal(id='cluster-person-row'):
                        with Vertical(id='cluster-person-photo'):
                            yield ClusterPortrait()
                            yield Static('',id='cluster-portrait-name',markup=False,localize=False)
                            yield Static('',id='cluster-portrait-seat',markup=False,localize=False)
                        with VerticalScroll(id='cluster-person-details',classes='cluster-modal-scroll'):
                            with Horizontal(id='cluster-person-heading'):
                                yield Static('',id='cluster-person-info',markup=False,localize=False)
                                with Horizontal(id='cluster-person-actions',classes='cluster-modal-actions'):
                                    yield Button('♧ Send friend request',id='cluster-add-friend',variant='primary')
                                    yield Button('✓ Friend',id='cluster-friend-details')
                                    yield Button('Poke',id='cluster-poke')
                                    yield Button('View profile',id='cluster-profile')
                            with Horizontal(id='cluster-person-cards'):
                                with Vertical(classes='cluster-detail-card'):
                                    yield Static('Host details',classes='cluster-detail-title')
                                    yield Static('',id='cluster-person-host',markup=False,localize=False)
                                with Vertical(classes='cluster-detail-card'):
                                    yield Static('User information',classes='cluster-detail-title')
                                    yield Static('',id='cluster-person-user',markup=False,localize=False)
                                with Vertical(classes='cluster-detail-card'):
                                    yield Static('School life',classes='cluster-detail-title')
                                    yield Static('',id='cluster-person-school',markup=False,localize=False)
                            with Vertical(classes='cluster-detail-card',id='cluster-titles-card'):
                                yield Static('Titles',classes='cluster-detail-title')
                                yield Static('',id='cluster-person-titles',markup=False,localize=False)
                            with Vertical(classes='cluster-detail-card'):
                                yield Static('Cursus progress',classes='cluster-detail-title')
                                yield Static('',id='cluster-person-cursus',markup=False,localize=False)
                                yield Static('Next level',id='cluster-next-level',classes='cluster-detail-title')
                                yield Static('',id='cluster-person-xp',markup=False,localize=False)
                                yield ProgressBar(total=100,show_eta=False,id='cluster-level-progress')
                            with Vertical(classes='cluster-detail-card'):
                                yield Static('Current projects',classes='cluster-detail-title')
                                yield Static('',id='cluster-person-projects',markup=False,localize=False)
                with TabPane('Workstation',id='cluster-workstation'):
                    with VerticalScroll(id='cluster-workstation-scroll',classes='cluster-modal-scroll'):
                        with Horizontal(id='cluster-workstation-layout'):
                            with Vertical(id='cluster-workstation-overview',classes='cluster-detail-card'):
                                yield Static('Workstation',classes='cluster-detail-title')
                                yield Static(self.hostname,classes='cluster-host-name',markup=False,localize=False)
                                yield Static('',id='cluster-machine-status',markup=False,localize=False)
                                yield Static('',id='cluster-machine-info',classes='cluster-host-location',markup=False,localize=False)
                                yield Static('Issues',classes='cluster-detail-title')
                                yield Static('',id='cluster-machine-reports',markup=False,localize=False)
                            with Vertical(id='cluster-workstation-details'):
                                with Vertical(classes='cluster-detail-card'):
                                    yield Static('Current session',classes='cluster-detail-title')
                                    yield Static('',id='cluster-machine-session',markup=False,localize=False)
                                yield Static('Storage usage',id='cluster-storage-title',classes='cluster-detail-title')
                                with Vertical(classes='cluster-storage-cards'):
                                    for kind,label in (('root','Root storage'),('goinfre','Goinfre storage')):
                                        with Vertical(classes='cluster-detail-card'):
                                            yield Static(label,classes='cluster-detail-title')
                                            yield Static('',id='cluster-storage-'+kind,classes='cluster-storage-value',markup=False,localize=False)
                                            yield ProgressBar(total=100,show_eta=False,show_percentage=False,id='cluster-storage-'+kind+'-progress',classes='cluster-storage-progress')
                        with Vertical(id='cluster-issues-section'):
                            with Horizontal(classes='cluster-section-heading',id='cluster-issues-heading'):
                                yield Static('Issues',id='cluster-issues-title',classes='cluster-section-name')
                                yield Button('Include resolved',id='cluster-resolved')
                            yield Static('Loaded reports',id='cluster-count-caption',classes='cluster-detail-title')
                            with Vertical(id='cluster-issue-counts',classes='cluster-summary-cards'):
                                for status,label in (('open','Open'),('in_progress','In progress'),('resolved','Resolved')):
                                    with Vertical(classes='cluster-detail-card cluster-count-card status-'+status):
                                        yield Static('—',id='cluster-count-'+status,classes='cluster-count-value',localize=False)
                                        yield Static(label,classes='cluster-detail-title')
                            yield Static('',id='cluster-report-status',markup=False,localize=False)
                            yield Button('Report an issue',id='cluster-new-report',variant='primary')
                            with Vertical(id='cluster-reports'):pass
                            yield Button('Load more',id='cluster-more-reports')

    def on_mount(self):
        self.set_class(self.app.size.width<100,'compact-person')
        for widget in self.query('*'):
            apply_language=getattr(widget,'apply_language',None)
            if apply_language:apply_language()
        self.query_one('#cluster-occupant-notice').display=False
        self.query_one('#cluster-more-reports').display=False
        self.query_one('#cluster-issue-counts').display=False
        self.query_one('#cluster-count-caption').display=False
        self._render_person();self.update_seat(self.seat)
        self.call_after_refresh(self._initial_details)
        if not self._person_cache_fresh:self.run_worker(self._load_person(),group='cluster-person',exclusive=True)
        if self.initial_tab=='workstation' and not self.issue_busy and not self.reports_loaded:self.run_worker(self._load_issues(),group='cluster-issues',exclusive=True)
        self.set_interval(30,self._refresh_reports)
        self.set_interval(1,self._render_person_session)

    def on_resize(self):self.set_class(self.app.size.width<100,'compact-person')

    def _initial_details(self):
        if self.is_mounted:
            self.update_seat(self.seat)
            self.refresh_portrait()

    def _valid(self):
        return not self._close_requested and self.is_mounted and self.workspace._scope()==self.context

    def dismiss(self,result=None):
        # Textual dismiss resolves this screen's result but pops the active
        # screen. If covered by another modal, wait until this one resumes.
        if self._dismissed or not self.is_mounted:return AwaitComplete.nothing()
        if not self._close_requested:
            self._close_requested=True;self._close_result=result
        if not self.is_active:return AwaitComplete.nothing()
        self._dismissed=True
        return super().dismiss(self._close_result)

    def on_screen_resume(self):
        if self._close_requested and not self._dismissed:self.dismiss(self._close_result)

    def action_close(self):self.dismiss()

    def refresh_portrait(self):
        if not self.is_mounted:return
        portrait=self.query_one(ClusterPortrait)
        url=(self.person_seat.person or {}).get('image_url')
        portrait.image=self.workspace.cache.images.get(url)
        portrait.status=self.workspace.cache.statuses.get(url)
        portrait.refresh()

    def _render_person_session(self):
        s=self.person_seat;person=s.person or {}
        session=session_label(s,self.t)
        name=self.person_data.get('display_name') or person.get('display_name') or s.login
        login=self.person_data.get('login') or s.login
        text=f'{name}\n@{login}\n{session}' if s.login else self.t('No active session')
        self.query_one('#cluster-person-info',Static).update(text)
        self.query_one('#cluster-portrait-name',Static).update(name or self.t('No active session'))
        self.query_one('#cluster-portrait-seat',Static).update(f'{self.hostname} · {session}')
        self.query_one('#cluster-person-host',Static).update(f'{self.t("Hostname")}: {self.hostname}\n{self.t("Session")}: {session}')

    def _render_person(self):
        s=self.person_seat
        self.person_generation+=1
        self.person_data={};self._person_cache_fresh=False
        self._render_person_session()
        for ident in ('user','school','titles'):
            self.query_one('#cluster-person-'+ident,Static).update(self.t('Loading…') if s.login else self.t('Unavailable'))
        self.query_one('#cluster-level-progress').display=False
        self.query_one('#cluster-next-level').display=False
        self.query_one('#cluster-person-xp',Static).update('')
        self.query_one('#cluster-person-cursus',Static).update(self.t('Loading cursus and current projects…') if s.login else '')
        self.query_one('#cluster-person-projects',Static).update(self.t('Loading…') if s.login else '')
        self.query_one('#cluster-profile',Button).disabled=not bool(s.login)
        self._render_friend_actions()
        self.refresh_portrait()

        if s.login:
            cursus=self.service.configured_cursus()
            if cursus:
                cached=self.workspace.cached_person(self.workspace.person_cache_key(s,cursus))
                if cached:
                    data,self._person_cache_fresh=cached
                    if not self._person_cache_fresh:data={**data,'meta':{**data.get('meta',{}),'stale':True}}
                    self._render_person_data(data)

    def _render_friend_actions(self):
        s=self.person_seat;factory=getattr(self.app,'session_factory',None)
        account=getattr(self.app,'account_id',None)
        user_id=self.person_data.get('user_id') or (s.person or {}).get('user_id')
        watches=self.service.memberships(account,origin=backend_origin(self.app))
        friend=any(w.login==s.login or user_id and w.user_id==user_id for w in watches)
        own=s.login==getattr(self.app,'account_login',None) or bool(user_id and user_id==account)
        add=self.query_one('#cluster-add-friend',Button)
        add.display=not friend and bool(s.login) and not own
        add.disabled=self.adding_friend or not bool(factory and account and getattr(self.app,'account_connected',False))
        add.set_source_label('Checking login…' if self.adding_friend else '♧ Send friend request')
        self.query_one('#cluster-friend-details',Button).display=friend
        self.query_one('#cluster-poke',Button).display=friend
        self.query_one('#cluster-poke',Button).disabled=not getattr(self.app,'account_connected',False)

    def update_seat(self,seat):
        self.seat=seat
        if not self._valid():return
        if seat.login==self.person_seat.login:
            self.person_seat=seat
            self._render_person_session()
        self._render_friend_actions()
        reports=self.t('Reports unavailable') if seat.open_count is None else self.t('{count} open reports').format(count=seat.open_count)
        self.query_one('#cluster-occupant-notice').display=seat.login!=self.person_seat.login
        storage=seat.storage or {}
        self.query_one('#cluster-machine-info',Static).update(
            f'{self.t("Cluster")}: C{self.hostname[0]}\n{self.t("Row")}: {self.hostname[1]} · {self.t("Seat")}: {self.hostname[2:]}')
        self.query_one('#cluster-machine-session',Static).update(
            f'{self.t("Session")}: {status_label(seat.session,self.t)}\n{self.t("Login")}: {seat.login or self.t("No active login")}')
        self.query_one('#cluster-machine-reports',Static).update(reports)
        machine=self.query_one('#cluster-machine-status',Static)
        machine.update('● '+status_label(seat.machine,self.t))
        for state in ('online','offline','unknown'):machine.set_class(seat.machine==state,'machine-'+state)
        self.query_one('#cluster-workstation-overview').set_class(bool(seat.open_count),'has-issues')
        for kind in ('root','goinfre'):
            value=storage.get(kind)
            self.query_one('#cluster-storage-'+kind,Static).update(str(value) if value is not None else self.t('Unavailable'))
            bar=self.query_one('#cluster-storage-'+kind+'-progress',ProgressBar)
            try:
                percent=float(str(value).removesuffix('%')) if str(value).endswith('%') else None
            except ValueError:percent=None
            bar.display=percent is not None and 0<=percent<=100
            if bar.display:bar.update(progress=percent)
            bar.set_class(bar.display and percent>=90,'storage-critical')
            bar.set_class(bar.display and 75<=percent<90,'storage-warning')

    def _render_person_data(self,data):
        self.person_data=data
        self._render_person_session();self._render_friend_actions()
        def value(key):
            result=data.get(key)
            return str(result) if result is not None else self.t('Unavailable')
        pool=' '.join(str(data[k]).capitalize() for k in ('pool_month','pool_year') if data.get(k)) or self.t('Unavailable')
        coalitions=data.get('coalitions')
        coalition=coalitions[0]['name'] if coalitions and len(coalitions)==1 else self.t('None' if coalitions==[] else 'Unavailable')
        self.query_one('#cluster-person-user',Static).update(
            f'{self.t("Login")}: {data["login"]}\n{self.t("Pool")}: {pool}\n{self.t("Coalition")}: {coalition}')
        self.query_one('#cluster-person-school',Static).update(
            f'{self.t("Balance")}: {value("wallet")} ₳\n{self.t("Evaluation points")}: {value("correction_point")}\n{self.t("Achievements")}: {value("achievements_count")}')
        titles=data.get('titles')
        self.query_one('#cluster-person-titles',Static).update('\n'.join(title.replace('%login',data['login']).replace('{login}',data['login']) for title in titles) if titles else self.t('None' if titles==[] else 'Unavailable'))
        projects=ongoing(data.get('items',[])).values()
        level=data.get('level')
        level_text=f'{level:.2f}' if level is not None else self.t('Unavailable')
        self.query_one('#cluster-person-cursus',Static).update(
            f'{self.t("Cursus")}: {data.get("cursus_name") or data["cursus_id"]}\n'
            f'{self.t("Level")}: {level_text} · '
            f'{self.t("Grade")}: {data.get("grade") or self.t("Unavailable")}')
        bar=self.query_one('#cluster-level-progress',ProgressBar)
        bar.display=False
        self.query_one('#cluster-next-level').display=False
        xp=data.get('xp_progress') or estimate_experience(data['cursus_id'],level)
        self.query_one('#cluster-person-xp',Static).update(self.t('XP unavailable'))
        self.query_one('#cluster-person-xp',Static).tooltip=None
        if xp:
            earned=xp['total_xp']-xp['level_start_xp']
            required=xp['next_level_xp']-xp['level_start_xp']
            xp_label=self.query_one('#cluster-person-xp',Static)
            xp_label.update(
                (self.t('Estimated XP')+'\n' if xp.get('estimated') else '')+
                self.t('{earned} / {required} XP · {remaining} XP remaining').format(earned=f'{earned:,}',required=f'{required:,}',remaining=f'{required-earned:,}')+'\n'+
                self.t('Total XP: {total} · Next level: {next} XP').format(total=f'{xp["total_xp"]:,}',next=f'{xp["next_level_xp"]:,}'))
            if xp.get('estimated'):
                xp_label.tooltip=self.t('Estimated from the reported level and community XP thresholds.')+'\n'+XP_SOURCE
            bar.display=True;self.query_one('#cluster-next-level').display=True
            bar.update(total=required,progress=earned)
        lines=[]
        lines.extend(f'• {p.get("name") or p.get("project_name") or p.get("project_id")} · {p["status"]}' for p in projects)
        if not lines:lines.append(self.t('No current projects'))
        if data.get('meta',{}).get('stale'):lines.append(self.t('Saved profile details · stale'))
        self.query_one('#cluster-person-projects',Static).update('\n'.join(lines))

    async def _load_person(self):
        self.person_generation+=1;generation=self.person_generation
        s=self.person_seat;provider=getattr(self.app,'provider',None)
        if not s.login:return
        cursus=self.service.configured_cursus()
        if not cursus or not callable(getattr(provider,'get_friend',None)):
            for ident in ('user','school','titles'):self.query_one('#cluster-person-'+ident,Static).update(self.t('Unavailable'))
            self.query_one('#cluster-person-cursus',Static).update(self.t('Unavailable'))
            self.query_one('#cluster-person-projects',Static).update(self.t('Cursus and current projects unavailable.'));return
        cache_key=self.workspace.person_cache_key(s,cursus)
        previous_data=self.person_data
        try:
            data=await self.service.person(provider,s.login,cursus,(s.person or {}).get('user_id'),
                lambda:self._valid() and generation==self.person_generation)
            if not self._valid() or generation!=self.person_generation or data is None:return
            self._render_person_data(data)
            self.workspace.remember_person(cache_key,data)
        except Exception:
            if self._valid() and generation==self.person_generation:
                self.person_data=previous_data
                if previous_data:
                    self._render_person_data({**previous_data,'meta':{**previous_data.get('meta',{}),'stale':True}})
                    return
                self._render_person_session()
                for ident in ('user','school','titles'):self.query_one('#cluster-person-'+ident,Static).update(self.t('Unavailable'))
                self.query_one('#cluster-person-cursus',Static).update(self.t('Unavailable'))
                self.query_one('#cluster-person-projects',Static).update(self.t('Cursus and current projects unavailable.'))

    async def _add_friend(self):
        if not self._valid() or self.adding_friend or not self.person_seat.login:return
        from ft_tui.features.friends.views.workspace import FriendsWorkspace
        friends=self.workspace.screen.query_one(FriendsWorkspace)
        login=self.person_seat.login
        user_id=self.person_data.get('user_id') or (self.person_seat.person or {}).get('user_id')
        self.adding_friend=True;self._render_friend_actions()
        try:
            if friends.busy and friends.worker:await friends.worker.wait()
            if not self._valid():return
            await friends.reload()
            friends.add_friend(login,(login,user_id) if user_id else None)
            if friends.adding and friends.add_worker:await friends.add_worker.wait()
            if self._valid():await self.workspace.reload()
        finally:
            self.adding_friend=False
            if self.is_mounted:self._render_friend_actions()

    @on(TabbedContent.TabActivated,'#cluster-modal-tabs')
    def tab_changed(self,event):
        event.stop()
        if event.pane.id=='cluster-workstation' and not self.reports_loaded and not self.issue_busy:
            self.run_worker(self._load_issues(),group='cluster-issues',exclusive=True)

    def _refresh_reports(self):
        if self._valid() and self.query_one('#cluster-modal-tabs',TabbedContent).active=='cluster-workstation' and not self.issue_busy:
            self.run_worker(self._load_issues(),group='cluster-issues',exclusive=True)

    async def _compose_issue(self):
        if not self._valid():return
        if not self.reports_loaded and not self.issue_busy:await self._load_issues()
        if not self._valid():return
        from ft_tui.features.cluster_map.views.cluster_issue import ClusterIssueModal
        def completed(submitted):
            if submitted and self._valid():
                self.app.notify(self.t('Issue reported successfully!'))
                self.issue_retry_at=0;self.loaded_pages=1
                self.run_worker(self._load_issues(),group='cluster-issues',exclusive=True)
                self.workspace.run_worker(self.workspace.reload(),group='cluster-refresh',exclusive=True)
        self.app.push_screen(ClusterIssueModal(self),completed)

    async def _load_issues(self,cursor=None):
        self.issue_generation+=1;generation=self.issue_generation;resolved=self.include_resolved
        status=self.query_one('#cluster-report-status',Static)
        self._render_issue_counts()
        if not self.reports_loaded and not cursor:
            await self.query_one('#cluster-reports',Vertical).remove_children()
        if monotonic()<self.issue_retry_at:
            status.update(self.t('Reports unavailable.'));return
        self.issue_busy=True
        status.update(self.t('Loading reports…'))
        provider=getattr(self.app,'provider',None)
        try:
            if not callable(getattr(provider,'get_cluster_issues',None)):raise ValueError('Reports unavailable')
            # Refresh the complete loaded prefix: a page-one poll must not remove
            # an expanded report from a later page while someone is reading it.
            target_pages=1 if cursor else self.loaded_pages
            pending=list(self.items) if cursor else []
            request_cursor=cursor;loaded=0;stale=False
            for _ in range(target_pages):
                data=await self.service.issues(provider,self.hostname,lambda:self._valid() and generation==self.issue_generation,include_resolved=resolved,cursor=request_cursor)
                if not self._valid() or generation!=self.issue_generation:return
                pending.extend(data['items']);loaded+=1;stale=stale or data.get('meta',{}).get('stale',False)
                request_cursor=data['next_cursor']
                if request_cursor is None:break
            if len({item['id'] for item in pending})!=len(pending):raise ValueError('Reports changed during pagination')
            self.items=sorted(pending,key=lambda item:item['status']=='resolved')
            self.loaded_pages=self.loaded_pages+loaded if cursor else loaded
            self.next_cursor=request_cursor;self.reports_loaded=True
            self.reports_stale=stale
            await self._render_issues()
            message=self.t('{count} reports').format(count=len(self.items)) if self.items else self.t('No known reports' if resolved else 'No known open reports')
            if stale:message+=' · '+self.t('Saved reports (stale)')
            status.update(message)
        except Exception as error:
            if self._valid() and generation==self.issue_generation:
                self.reports_stale=True
                delay=getattr(getattr(error,'response',None),'headers',{}).get('Retry-After','30')
                self.issue_retry_at=monotonic()+max(30,min(86400,int(delay) if str(delay).isdigit() else 30))
                status.update(self.t('Reports unavailable.')+(' '+self.t('Previously loaded reports are retained.') if self.items else ''))
        finally:
            if generation==self.issue_generation:
                self.issue_busy=False
                if self.is_mounted and not self._close_requested:self._render_issue_counts()

    def _render_issue_counts(self):
        self.query_one('#cluster-issue-counts').display=bool(self.items)
        self.query_one('#cluster-count-caption').display=bool(self.items)
        for state in ('open','in_progress','resolved'):
            self.query_one('#cluster-count-'+state,Static).update(str(sum(item['status']==state for item in self.items)))

    async def _render_issues(self):
        container=self.query_one('#cluster-reports',Vertical)
        expanded={w.id for w in container.query(Collapsible) if not w.collapsed}
        scroll=self.query_one('#cluster-workstation-scroll',VerticalScroll);y=scroll.scroll_y
        await container.remove_children()
        for item in self.items:
            ident='cluster-report-'+sha256(item['id'].encode()).hexdigest()[:16]
            history=item.get('history') or []
            parts=[self.t({'open':'Open','in_progress':'In progress','resolved':'Resolved'}[item['status']]),item.get('component'),item['title']]
            title=' · '.join(part for part in parts if part)
            metadata=' · '.join(part for part in (item.get('category'),item.get('updated_at')) if part)
            report=Vertical(classes='cluster-report-card status-'+item['status'])
            await container.mount(report)
            if metadata:await report.mount(Static(metadata,markup=False,classes='cluster-report-meta',localize=False))
            description=item.get('description')
            if not description or not description.strip():description=self.t('No description supplied.')
            details=[Static('Description',classes='cluster-detail-title'),
                Static(description,markup=False,classes='cluster-report-body',localize=False)]
            if history:
                history_text='\n'.join(f'{h.get("date") or ""} · {h["content"]}' for h in history)
                details.extend([Static('History',classes='cluster-detail-title'),
                    Static(history_text,markup=False,classes='cluster-report-body',localize=False)])
            await report.mount(Collapsible(*details,title=escape(title),collapsed=ident not in expanded,id=ident))
        self.query_one('#cluster-more-reports',Button).display=self.next_cursor is not None
        self.call_after_refresh(scroll.scroll_to,y=y,animate=False)

    @on(Button.Pressed)
    def pressed(self,event):
        if self._close_requested:event.stop();return
        ident=event.button.id
        if ident=='cluster-close':self.dismiss()
        elif ident=='cluster-latest':
            self.person_seat=self.seat;self._render_person();self.update_seat(self.seat)
            if not self._person_cache_fresh:self.run_worker(self._load_person(),group='cluster-person',exclusive=True)
        elif ident=='cluster-resolved':
            self.include_resolved=not self.include_resolved;event.button.variant='primary' if self.include_resolved else 'default'
            self.items=[];self.reports_loaded=False
            self.loaded_pages=1
            self.run_worker(self._load_issues(),group='cluster-issues',exclusive=True)
        elif ident=='cluster-more-reports':
            if not self.issue_busy and self.next_cursor:self.run_worker(self._load_issues(self.next_cursor),group='cluster-issues',exclusive=True)
        elif ident=='cluster-new-report':
            self.run_worker(self._compose_issue(),group='cluster-compose',exclusive=True)
        elif ident=='cluster-profile':
            if self.person_seat.login:
                from ft_tui.features.profiles.views.user_profile import open_user_profile
                user_id=self.person_data.get('user_id') or (self.person_seat.person or {}).get('user_id')
                open_user_profile(self.app,self.person_seat.login,user_id,seed=self.person_data or None)
        elif ident=='cluster-add-friend':
            self.run_worker(self._add_friend(),group='cluster-add-friend',exclusive=True)
        elif ident=='cluster-poke':
            from ft_tui.features.social.views.inbox import SocialInbox
            inbox=self.workspace.screen.query_one(SocialInbox)
            target=next((f for f in inbox.snapshot.get('friends',[]) if f['login']==self.person_seat.login),None)
            if target:inbox.compose_poke(target['account_id'])
        elif ident=='cluster-friend-details':
            from ft_tui.features.friends.views.workspace import FriendsWorkspace
            login=self.person_data.get('login') or self.person_seat.login
            self.dismiss()
            def navigate():
                self.app.query_one(TabbedContent).active='friends'
                ws=self.app.query_one(FriendsWorkspace);ws.selected_login=login;ws.expanded_friend=True;ws._refresh_view()
            self.app.call_later(navigate)
        else:return
        event.stop()
