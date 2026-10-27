"""Uniform no-scroll campus maps with account-scoped asynchronous observations."""
import asyncio
from collections import OrderedDict
from copy import deepcopy
from math import ceil
from time import monotonic
from textual import on
from textual.containers import Horizontal,Vertical
from textual.widgets import TabbedContent
from ft_tui.ui.components import Button,Input,Select,Static
from ft_tui.features.cluster_map.geometry import positions
from ft_tui.features.cluster_map.state import seat_states,matching_hosts,status_label
from ft_tui.app.read_cache import backend_origin
from ft_tui.i18n import translate
from ft_tui.features.cluster_map.adapters.factory import resolve_cluster_service
from ft_tui.features.cluster_map.views.cluster_map_grid import ClusterMapGrid
from ft_tui.features.cluster_map.views.portrait import PortraitCache


def observed_seat(app,login,user_id=None):
    """Reuse a recent, account-scoped map observation without waiting for a profile."""
    from datetime import datetime,timezone
    if not login or not getattr(app,'account_connected',False):return None
    for screen in reversed(app.screen_stack):
        for workspace in screen.query(ClusterMapWorkspace):
            if workspace.context!=workspace._scope() or workspace.error:continue
            meta=workspace.snapshot.get('meta',{})
            if meta.get('stale'):continue
            try:
                stamp=datetime.fromisoformat(meta['cached_at'].replace('Z','+00:00'))
                if not 0<=(datetime.now(timezone.utc)-stamp).total_seconds()<60:continue
            except (KeyError,ValueError,TypeError):continue
            for seat in workspace.states.values():
                if (seat.login or '').casefold()!=login.casefold() or seat.machine=='unknown' or seat.session=='unknown':continue
                identity=(seat.person or {}).get('user_id')
                if user_id and identity and str(user_id)!=str(identity):continue
                return (seat.hostname if seat.machine=='online' else 'No active session'),stamp
    return None


class ClusterMapWorkspace(Vertical):
    def t(self,text):return translate(text,getattr(self.app,'language','en'))

    def __init__(self,service=None):
        self._service=service
        super().__init__(id='cluster-map-workspace')
        self.view='all';self.snapshot={};self.states=seat_states({},frozenset());self.friend_logins=frozenset()
        self.friends_only=False;self.context=None;self.epoch=0;self.busy=False;self.search_index=-1
        self.cache=PortraitCache();self.modal=None;self.error=None
        self.retry_at=0
        self._next_refresh_at=0
        self._freshness_label=None
        self._portrait_batch=None
        self.person_cache=OrderedDict()

    @property
    def service(self):
        return self._service if self._service is not None else resolve_cluster_service(self.app)

    def person_cache_key(self,seat,cursus):
        user_id=(seat.person or {}).get('user_id')
        return self._scope(),cursus,('id',user_id) if user_id else ('login',seat.login)

    def cached_person(self,key):
        entry=self.person_cache.get(key)
        if entry is None:return None
        stamp,data=entry;age=monotonic()-stamp
        if age>=3600:
            self.person_cache.pop(key,None);return None
        self.person_cache.move_to_end(key)
        return deepcopy(data),age<300 and not data.get('meta',{}).get('stale')

    def remember_person(self,key,data):
        self.person_cache[key]=(monotonic(),deepcopy(data))
        self.person_cache.move_to_end(key)
        while len(self.person_cache)>192:self.person_cache.popitem(last=False)

    def compose(self):
        with Vertical(id='cluster-body'):
            with Horizontal(id='cluster-toolbar'):
                yield Static('Cluster Map',id='cluster-menu-title',classes='cluster-menu-label')
                yield Static('View',classes='cluster-menu-label cluster-menu-caption')
                with Vertical(id='cluster-view'):
                    for label,view in self._view_options():
                        yield Button(label,id=f'cluster-view-{view}',classes='cluster-view-button')
                yield Static('Search',classes='cluster-menu-label cluster-menu-caption')
                yield Input(placeholder='Login / name / host',id='cluster-search',tooltip='Search login / name / host')
                yield Static('Filter',classes='cluster-menu-label cluster-menu-caption')
                yield Select([('All seats','all'),('Free','free'),('Free · no reports','healthy'),('Occupied','occupied'),('Has reports','issues')],value='all',id='cluster-filter')
                with Horizontal(id='cluster-menu-actions'):
                    friends_button=Button('♧ 0',id='cluster-friends')
                    friends_button.styles.line_pad=0
                    yield friends_button
                    yield Button('↻',id='cluster-refresh',tooltip='Refresh',square=True)
                yield Static('',id='cluster-freshness',markup=False,localize=False)
                yield Static('/ Search\n↑ ↓ ← → Move\nEnter Details',id='cluster-menu-hints',classes='cluster-menu-label',markup=False)
            with Vertical(id='cluster-map-panel'):
                yield ClusterMapGrid()
                yield Static('Select a workstation',id='cluster-focus',markup=False,localize=False)

    async def on_mount(self):
        self._next_refresh_at=monotonic()+15
        self.set_interval(2,self._poll_portraits)
        self.set_interval(1,self._check_context)
        # Sample between second boundaries so timer jitter cannot hide a second.
        self.set_interval(0.1,self._tick_refresh)
        await self.reload()

    def _scope(self):
        return (getattr(self.app,'account_generation',0),getattr(self.app,'account_id',None),id(getattr(self.app,'provider',None)))

    def _active(self):
        tabs=self.app.query(TabbedContent)
        return bool(self.modal or tabs and tabs.first().active=='cluster-map')

    def _check_context(self):
        if self.context!=self._scope():self.run_worker(self.reload(),group='cluster-context',exclusive=True)

    def _tick_refresh(self):
        if monotonic()>=max(self._next_refresh_at,self.retry_at):
            self._next_refresh_at=monotonic()+15
            self._poll()
        self._update_freshness()

    def _poll(self):
        if self._active():self.run_worker(self.reload(),group='cluster-refresh',exclusive=False)

    def _poll_portraits(self):
        if self._active() and self.context==self._scope():
            self.run_worker(self._portraits(self.epoch,self.context),group='cluster-portraits',exclusive=False)

    def _valid(self,epoch,context):return self.is_mounted and self.epoch==epoch and self._scope()==context

    async def reload(self):
        context=self._scope()
        if context!=self.context:
            self.context=context;self.epoch+=1;self.busy=False;self.snapshot={};self.error=None
            self.person_cache.clear()
            self.retry_at=0
            origin=getattr(getattr(getattr(self.app,'provider',None),'api',None),'base_url','')
            directory=self.service.portrait_directory(context[1],origin)
            self.cache=PortraitCache(directory)
            grid=self.query_one(ClusterMapGrid)
            grid.set_images(self.cache.images);grid._portrait_lines.clear()
            if self.modal and self.modal.is_mounted:self.modal.dismiss()
        self.friend_logins=frozenset()
        self.friend_logins=frozenset(w.login for w in self.service.memberships(context[1],origin=backend_origin(self.app)))
        self._update()
        provider=getattr(self.app,'provider',None)
        if not getattr(self.app,'account_connected',False) or not callable(getattr(provider,'get_cluster_map',None)):
            self.error='Connect your 42 account to load presence.';self._update();return
        if self.busy or not self._active() or monotonic()<self.retry_at:return
        epoch=self.epoch;self.busy=True
        self._next_refresh_at=monotonic()+15
        self._update_freshness()
        try:
            snapshot=await self.service.map(provider,lambda:self._valid(epoch,context))
            if not self._valid(epoch,context):return
            self.snapshot=snapshot;self.error=None;self.retry_at=0;self._update()
            self._poll_portraits()
        except Exception as error:
            if self._valid(epoch,context):
                self.error='Presence unavailable; last observation retained.' if self.snapshot else 'Presence unavailable.'
                delay=getattr(getattr(error,'response',None),'headers',{}).get('Retry-After','15')
                self.retry_at=monotonic()+max(15,min(86400,int(delay) if str(delay).isdigit() else 15))
                if self.snapshot:self.snapshot={**self.snapshot,'meta':{**self.snapshot.get('meta',{}),'stale':True}}
                self._update()
        finally:
            if self._valid(epoch,context):
                self.busy=False;self._update_freshness()

    async def _portraits(self,epoch,context):
        batch=(epoch,context)
        if not self._valid(epoch,context) or self._portrait_batch==batch:return
        self._portrait_batch=batch
        try:
            provider=getattr(self.app,'provider',None);cache=self.cache
            fetch=getattr(provider,'get_cluster_portrait',None)
            if not callable(fetch):return
            urls={(s.person or {}).get('image_url'):s.hostname for s in self.states.values() if s.person}
            async def load(url,host):
                if not self._valid(epoch,context):return
                before=cache.images.get(url)
                before_status=cache.statuses.get(url)
                await cache.load(url,lambda:self.service.portrait(provider,host,lambda:self._valid(epoch,context)))
                if self._valid(epoch,context):
                    if before is not cache.images.get(url):
                        grid=self.query_one(ClusterMapGrid);grid.set_images(cache.images)
                    self._update_freshness()
                    if self.modal and self.modal.is_mounted and (before is not cache.images.get(url) or before_status!=cache.statuses.get(url)):
                        if (self.modal.person_seat.person or {}).get('image_url')==url:self.modal.refresh_portrait()
            await asyncio.gather(*(load(url,host) for url,host in urls.items() if url))
        finally:
            if self._portrait_batch==batch:self._portrait_batch=None

    def set_view(self,view):
        if view not in ('all','c1','c2','c3'):return
        self.view=view;self.search_index=-1
        self.query_one(ClusterMapGrid).clear_selection()
        self._update()

    def on_resize(self):
        self.set_class(self.size.height<28,'short-sidebar')

    def _matches(self):
        return matching_hosts(self.states,self.query_one('#cluster-search',Input).value,
            str(self.query_one('#cluster-filter',Select).value),self.friends_only)

    def _view_options(self):
        options=[]
        for label,view in (('All','all'),('C1','c1'),('C2','c2'),('C3','c3')):
            hosts=positions(view)
            occupied=sum(bool(self.states[host].login) for host in hosts)
            percent=f'{round(100*occupied/len(hosts))}%' if self.snapshot else '—'
            options.append((f'{self.t(label)} {percent}',view))
        return options

    def _update(self):
        if not self.is_mounted:return
        self.states=seat_states(self.snapshot,self.friend_logins)
        grid=self.query_one(ClusterMapGrid)
        grid.set_state(self.view,self.states,frozenset(self._matches()))
        for label,view in self._view_options():
            button=self.query_one(f'#cluster-view-{view}',Button)
            button.set_source_label(label)
            hosts=positions(view)
            occupied=str(sum(bool(self.states[host].login) for host in hosts)) if self.snapshot else '—'
            button.set_source_tooltip(f'{label} · {occupied}/{len(hosts)}')
            button.set_class(view==self.view,'selected')
            color=grid.occupancy_color(view)
            button.styles.color=color
            button.styles.background=color.with_alpha(0.18 if view==self.view else 0.06) if color else None
        count=sum(s.friend for s in self.states.values())
        button=self.query_one('#cluster-friends',Button);button.set_source_label(f'♧ {self.t("Friends")} · {count}');button.variant='primary' if self.friends_only else 'default'
        button.tooltip=self.t('Highlight connected friends' if self.snapshot else 'Friend presence unavailable')
        self._update_freshness()
        if self.modal and self.modal.is_mounted:
            self.modal.update_seat(self.states[self.modal.hostname])

    def _update_freshness(self):
        remaining=max(0,ceil(max(self._next_refresh_at,self.retry_at)-monotonic()))
        countdown=self.t('Auto refresh in {seconds}s').format(seconds=remaining)
        status=self.error or ('Stale presence' if self.snapshot.get('meta',{}).get('stale') else None)
        label=self.t('Refreshing presence…') if self.busy else (self.t(status)+' · ' if status else '')+countdown
        content=label
        if content!=self._freshness_label:
            self._freshness_label=content
            self.query_one('#cluster-freshness',Static).update(content)

    @on(Select.Changed,'#cluster-filter')
    def change_filter(self,event):event.stop();self.search_index=-1;self._update()

    @on(Input.Changed,'#cluster-search')
    def change_search(self,event):event.stop();self.search_index=-1;self._update()

    @on(Input.Submitted,'#cluster-search')
    def cycle_match(self,event):
        event.stop();matches=self._matches()
        if not matches:return
        self.search_index=(self.search_index+1)%len(matches);host=matches[self.search_index]
        if host not in positions(self.view):self.set_view('all');self.query_one('#cluster-view',Select).value='all'
        self.query_one(ClusterMapGrid).select_host(host)

    @on(Button.Pressed)
    def button_pressed(self,event):
        if event.button.id and event.button.id.startswith('cluster-view-'):
            self.set_view(event.button.id.removeprefix('cluster-view-'))
        elif event.button.id=='cluster-friends':self.friends_only=not self.friends_only;self._update()
        elif event.button.id=='cluster-refresh':self.run_worker(self.reload(),group='cluster-refresh',exclusive=False)
        else:return
        event.stop()

    @on(ClusterMapGrid.Focused)
    def focused_host(self,event):
        s=self.states.get(event.hostname)
        if s is None:
            self.query_one('#cluster-focus',Static).update(self.t('Select a workstation'))
        if s:
            reports=self.t('Reports unavailable') if s.open_count is None else self.t('{count} open reports').format(count=s.open_count)
            self.query_one('#cluster-focus',Static).update(f'{s.hostname} · {s.login or self.t("No active login")} · {status_label(s.machine,self.t)} · {status_label(s.session,self.t)} · {reports}'+(' · '+self.t('Friend') if s.friend else ''))

    @on(ClusterMapGrid.SeatSelected)
    def open_seat(self,event):
        from ft_tui.features.cluster_map.views.cluster_workstation import ClusterWorkstationModal
        if self.modal:return
        state=self.states[event.hostname]
        self.modal=ClusterWorkstationModal(self,event.hostname,state,'workstation' if event.open_issues else 'person' if state.login else 'workstation',self._scope())
        def closed(result):
            self.modal=None
            if self.is_mounted:
                grid=self.query_one(ClusterMapGrid)
                grid.clear_selection()
                grid.focus()
        self.app.push_screen(self.modal,closed)

    def on_key(self,event):
        if event.key=='tab' and self.app.focused is self.query_one('#cluster-search',Input) and self._matches():
            self.query_one(ClusterMapGrid).focus();event.stop();event.prevent_default();return
        if event.key=='slash' and not isinstance(self.app.focused,Input):
            self.query_one('#cluster-search',Input).focus();event.stop();event.prevent_default()
