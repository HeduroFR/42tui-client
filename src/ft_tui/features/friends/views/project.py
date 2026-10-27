"""Read-only friend attempt preview, with independently loaded evaluations."""
import asyncio
from copy import deepcopy

from textual.containers import Horizontal, Vertical
from textual.widgets import Collapsible, Digits, Static

from ft_tui.features.projects.activity.models import friend_activity, friend_evaluations
from ft_tui.features.catalog.models import project_summary
from ft_tui.features.projects.activity.presentation import format_mark
from ft_tui.services.project_presentation import readable_condition
from ft_tui.ui.modal import AppModal, modal_css
from ft_tui.features.projects.views.activity import ProjectActivityScreen


def open_friend_project(app, snapshot, attempt):
    from ft_tui.features.catalog.models import CatalogScope
    project=next((p for p in getattr(app,'projects',{}).values() if p.official_project_id==attempt['project_id']),None)
    scope=getattr(app,'_catalog_scope',lambda:None)()
    if scope is None:
        campus=next((c for c in snapshot.get('campuses',[]) if c.get('is_primary')),None)
        campus=campus or next(iter(snapshot.get('campuses',[])),None)
        if campus:scope=CatalogScope(snapshot['cursus_id'],campus['id'])
    if scope is None:
        from ft_tui.i18n import translate
        app.notify(translate('Campus unavailable',getattr(app,'language','en')),severity='warning')
        return
    if scope.cursus_id!=snapshot['cursus_id']:
        scope=CatalogScope(snapshot['cursus_id'],scope.campus_id)
    app.push_screen(FriendProjectPreview(snapshot,attempt,project,scope,app.account_id,app.provider,app.account_generation))


class FriendProjectPreview(ProjectActivityScreen, AppModal):
    FEEDBACK_LABEL = 'Feedback'
    DEFAULT_CSS = modal_css('FriendProjectPreview') + """
    #friend-project-dialog { width: 88%; max-width: 132; height: 88%; max-height: 48; border: solid $primary; background: $surface; padding: 0 1; }
    #friend-project-result { height: 7; margin-bottom: 1; }
    #friend-project-score { width: 26; height: 7; padding: 1; margin-right: 2; background: $boost; color: $text-muted; }
    #friend-project-score.passed { background: #46783d; color: #ffffff; }
    #friend-project-score.failed { background: #9e3d3d; color: #ffffff; }
    #friend-project-score.ongoing { background: #bf983e; color: #1c170b; }
    #friend-project-score-status { height: 1; text-align: center; text-style: bold; }
    #friend-project-score-number { height: 3; align: center middle; }
    #friend-project-mark { width: auto; height: 3; text-style: bold; }
    #friend-project-mark-scale { width: 4; height: 3; content-align: left bottom; }
    #friend-project-mark-caption { height: 1; text-align: center; }
    #friend-project-identity { width: 1fr; height: 1fr; align: left middle; }
    #friend-project-attempt { height: auto; text-style: bold; }
    #friend-project-facts { height: auto; margin-top: 1; color: $text-muted; }
    #friend-project-attempt.passed { color: $success; }
    #friend-project-attempt.failed { color: $error; }
    #friend-project-attempt.ongoing { color: $warning; }
    #friend-project-overview { height: auto; max-height: 9; overflow-y: auto; margin-bottom: 1; }
    #friend-project-description { height: auto; }
    FriendProjectPreview #activity-sidebar { width: 28; min-width: 20; margin-right: 1; }
    FriendProjectPreview #activity-body.compact #activity-sidebar { width: 1fr; height: 4; min-height: 3; }
    FriendProjectPreview #activity-controls { margin-top: 0; }
    FriendProjectPreview.short-preview #friend-project-result { height: 5; }
    FriendProjectPreview.short-preview #friend-project-score { height: 5; padding: 0 1; width: 22; margin-right: 1; }
    FriendProjectPreview.short-preview #friend-project-facts { margin-top: 0; }
    """

    def __init__(self, snapshot, attempt, project, scope, account_id, provider, account_generation):
        self.student = deepcopy(snapshot)
        self.attempt = deepcopy(attempt)
        self.catalog = deepcopy(project.catalog_data) if project else {}
        self.snapshot_id = self.catalog.get('snapshot_id')
        super().__init__(attempt['project_id'], attempt['name'], scope, account_id, provider, account_generation, None)

    def compose(self):
        with Vertical(id='friend-project-dialog'):
            with Horizontal(id='friend-project-result'):
                with Vertical(id='friend-project-score'):
                    yield Static('', id='friend-project-score-status', markup=False)
                    with Horizontal(id='friend-project-score-number'):
                        yield Digits('-', id='friend-project-mark')
                        yield Static('/100', id='friend-project-mark-scale', markup=False)
                    yield Static('', id='friend-project-mark-caption', markup=False)
                with Vertical(id='friend-project-identity'):
                    yield Static('', id='friend-project-attempt', markup=False)
                    yield Static('', id='friend-project-facts', markup=False)
            with Collapsible(title=self.t('Project Details'), collapsed=False, id='friend-project-overview'):
                yield Static('', id='friend-project-description', markup=False)
            yield from super().compose()

    def on_mount(self):
        # Textual dispatches ProjectActivityScreen's mount handler through the MRO.
        self.set_class(self.size.height<38,'short-preview')
        if self.size.width<100 or self.size.height<40:
            self.query_one('#friend-project-overview',Collapsible).collapsed=True
        self._render_attempt()
        self._render_catalog()
        # Friend evaluation payloads are distinct from the signed-in user's activity.
        self.query_one('#activity-intra').display = False
        self.query_one('#activity-sidebar-title', Static).update(self.t('Teams'))
        if self.scope and callable(getattr(self.provider, 'get_catalog_project', None)):
            self.run_worker(self._load_catalog(), group='friend-project-catalog', exclusive=True)
        self.call_after_refresh(self._responsive_preview)

    def on_resize(self,event):
        if self.is_mounted:self.call_after_refresh(self._responsive_preview)

    def _responsive_preview(self):
        if not self.is_mounted:return
        dialog=self.query_one('#friend-project-dialog')
        self.query_one('#activity-body').set_class(dialog.content_size.width<90,'compact')
        self.set_class(self.size.height<38,'short-preview')
        if self.size.height<40:
            self.query_one('#friend-project-overview',Collapsible).collapsed=True

    def _cache_key(self, team_id=None):
        return (*super()._cache_key(team_id), 'friend', self.student['user_id'], self.attempt['id'])

    def _render_attempt(self):
        item = self.attempt
        stages={'in_progress':'In progress','waiting_for_correction':'Awaiting correction',
                'creating_group':'Creating team','searching_a_group':'Searching for a team',
                'waiting_to_start':'Waiting to start','finished':'Finished'}
        state = ('Validated' if item.get('validated') is True else
                 'Failed' if item['status'] == 'finished' and item.get('validated') is False else
                 stages.get(item['status'],item['status'].replace('_', ' ').capitalize()))
        widget = self.query_one('#friend-project-attempt', Static)
        widget.update(f"{self.student['login']} · {item['name']}\n{self.t(state)} · #{item['id']}")
        widget.set_class(item.get('validated') is True, 'passed')
        widget.set_class(item['status'] == 'finished' and item.get('validated') is False, 'failed')
        widget.set_class(item.get('validated') is not True and item['status'] != 'finished', 'ongoing')
        card=self.query_one('#friend-project-score')
        for name in ('passed','failed','ongoing'):
            card.set_class(widget.has_class(name),name)
        icon='✓' if card.has_class('passed') else '×' if card.has_class('failed') else '◷' if card.has_class('ongoing') else '—'
        self.query_one('#friend-project-score-status',Static).update(f'{icon} {self.t(state)}')
        mark=item.get('final_mark')
        self.query_one('#friend-project-mark',Digits).update('-' if mark is None else f'{mark:g}')
        self.query_one('#friend-project-mark-scale').display=mark is not None
        caption=self.t('Result pending') if mark is None else f"{self.t('Mark')}: {format_mark(mark)}"
        self.query_one('#friend-project-mark-caption',Static).update(caption)

    def _render_catalog(self):
        data = self.catalog
        facts = []
        for field, label in [('rank', 'Rank'), ('xp', 'XP'), ('duration', 'Duration'), ('project_mode', 'Team')]:
            if data.get(field) is not None:
                value={'solo':'Solo','group':'Group','unknown':'Team size unavailable'}.get(data[field],str(data[field])) if field=='project_mode' else str(data[field])
                facts.append(f"{self.t(label)}: {self.t(value)}")
        if data.get('team_size') is not None:
            facts.append(f"{self.t('Members')}: {data['team_size']}")
        description = data.get('description') or self.t('Project description unavailable.')
        lines = [' · '.join(facts), description]
        for clause in data.get('clauses', []):
            condition = readable_condition(clause.get('expression', {}), getattr(self.app, 'language', 'en'))
            if condition:
                label = 'Recommendation' if clause.get('modality') == 'recommended' else 'Requirement'
                lines.append(f'{self.t(label)}: {condition}')
        self.query_one('#friend-project-description', Static).update('\n'.join(line for line in lines if line))
        self.query_one('#friend-project-facts',Static).update(' · '.join(facts))

    async def _load_catalog(self):
        try:
            data = await asyncio.to_thread(self.provider.get_catalog_project, self.project_id, self.scope, self.snapshot_id)
            data = project_summary(data)
            if not self._same_account() or data['project_id'] != self.project_id:
                return
            self.catalog = data
            self._render_catalog()
        except Exception:
            # Keep the already displayed attempt and cached project description.
            pass

    def _read_history(self, refresh):
        value = self.provider.get_friend_project_activity(self.project_id, self.attempt['id'], self.student['user_id'],
                                                        self.scope, self.account_id, refresh=refresh)
        return friend_activity(value, self.project_id, self.attempt['id'], self.student['user_id'], self.scope, self.account_id)

    def _read_evaluations(self, team_id, refresh):
        value = self.provider.get_friend_project_evaluations(self.project_id, self.attempt['id'], self.student['user_id'],
                                                           team_id, self.scope, self.account_id, refresh=refresh)
        return friend_evaluations(value, self.project_id, self.attempt['id'], self.student['user_id'], team_id, self.scope, self.account_id)

    def _show_source_status(self):
        super()._show_source_status()
        if self.history and not self.history['teams'] and self.history['source']['status']=='available' and not self.history['source']['stale']:
            self.query_one('#activity-status', Static).update(self.t('No evaluation team for this attempt.'))

    async def _display_history(self, value, epoch, previous=None):
        if self._same_account() and value['source']['status']=='available' and not value['source']['stale']:
            current=next((team for team in value['teams'] if team['id']==value['current_team_id']),None)
            if current:
                self.attempt.update(status=current['status'],validated=current['validated'],final_mark=current['final_mark'])
                self._render_attempt()
        await super()._display_history(value, epoch, previous)
        if self._same_account():
            self._show_source_status()

    def _peer_sections(self, value):
        finished=self.attempt.get('validated') is True or self.attempt['status']=='finished'
        peers=value['peer']['items']
        sections=[]
        if not finished or any(not item['filled_at'] for item in peers):
            sections.append((False,'Scheduled & pending evaluations'))
        if finished or any(item['filled_at'] for item in peers):
            sections.append((True,'Completed evaluations'))
        return sections

    def _show_automated(self, value):
        return bool(value['automated']['items']) or self.attempt['status'] in ('waiting_for_correction','finished') or self.attempt.get('validated') is True

    def _invalidate(self, message, *, clear_scope=True):
        super()._invalidate(message, clear_scope=clear_scope)
        self.query_one('#friend-project-attempt', Static).update('')
        self.query_one('#friend-project-description', Static).update('')
        self.query_one('#friend-project-facts',Static).update('')
        self.query_one('#friend-project-score').display=False

    def _authorization_failed(self, error):
        import httpx
        if isinstance(error,httpx.HTTPStatusError) and error.response.status_code==403:
            message=self.t('Evaluation details are restricted by 42.')
            self._invalidate(message, clear_scope=False)
            return True
        return super()._authorization_failed(error)

    def action_close(self):
        self._alive = False
        self._epoch += 1
        self.workers.cancel_node(self)
        self.dismiss()
