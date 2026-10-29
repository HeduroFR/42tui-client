"""Run reviewed project Git actions and show their output in the TUI."""
import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static

from ft_tui.features.projects.adapters.git import (
    ProjectGitError, plan_project_pull, pull_project, plan_project_push, push_project, project_git_output,
)
from ft_tui.features.projects.adapters.ssh_askpass import run_with_ssh_askpass
from ft_tui.features.projects.views.ssh_prompt import ProjectSshPromptHandler
from ft_tui.i18n import translate
from ft_tui.ui.button import AppButton
from ft_tui.ui.modal import AppModal


class ProjectGitActionScreen(AppModal[str | None]):
    BINDINGS = [('escape', 'close', 'Close')]
    DEFAULT_CSS = """
    #git-action-dialog { width: 96; max-width: 94%; height: 85%; border: round $primary; padding: 1 2; }
    #git-action-scroll { height: 1fr; }
    #git-action-dialog Static { height: auto; margin-bottom: 1; }
    #git-action-output.error { color: $error; }
    #git-action-output.success { color: $success; }
    #git-action-actions { height: 3; margin-top: 1; align-horizontal: center; }
    #git-action-actions AppButton { margin: 0 2; }
    """

    def __init__(self, review, snapshot, action: str, *, project_name: str):
        super().__init__()
        self.review, self.snapshot, self.action = review, snapshot, action
        self.project_name = project_name
        self.destination = {'origin': 'dev', 'vogsphere': 'vog'}[review.remote]
        self.plan = None
        self.busy = True
        self.updated_commit = None

    def _t(self, text):
        return translate(text, self.app.language)

    def compose(self) -> ComposeResult:
        titles = {'status': 'Git status', 'log': 'Inspect commits', 'pull': 'Review Git pull', 'push': 'Review Git push'}
        with Vertical(id='git-action-dialog'):
            yield Static(self._t(titles[self.action]), classes='panel-title')
            yield Static(f'{self.project_name}\n{self.review.path}\n'
                         f'{self.destination} ({self.review.remote}) → {self.review.branch}', markup=False)
            with VerticalScroll(id='git-action-scroll'):
                yield Static(self._t('Loading') + '…', id='git-action-output', markup=False)
            with Horizontal(id='git-action-actions'):
                if self.action in {'pull', 'push'}:
                    yield AppButton(self._t('Confirm pull' if self.action == 'pull' else 'Confirm push'),
                                    id='git-action-confirm', variant='primary', disabled=True)
                yield AppButton(self._t('Close'), id='git-action-close', disabled=True)

    def on_mount(self):
        self.run_worker(self._prepare())

    def _set_busy(self, busy):
        self.busy = busy
        if not self.is_current:
            return
        self.query_one('#git-action-close', AppButton).disabled = busy
        for button in self.query('#git-action-confirm'):
            button.disabled = busy or self.plan is None

    def _output(self, text, *, error=False, success=False):
        if self.is_current:
            output = self.query_one('#git-action-output', Static)
            output.set_class(error, 'error')
            output.set_class(success, 'success')
            output.update(text)

    async def _run(self, operation, *args, **kwargs):
        prompts = ProjectSshPromptHandler(self)
        try:
            result = await asyncio.to_thread(run_with_ssh_askpass, operation, prompts, *args, **kwargs)
            if prompts.was_cancelled:
                raise ProjectGitError(self._t('Git operation cancelled.'))
            return result
        finally:
            prompts.close()

    async def _prepare(self):
        self._set_busy(True)
        try:
            if self.action in {'status', 'log'}:
                output = await self._run(project_git_output, self.review.path,
                                         history_commit=self.review.commit if self.action == 'log' else None)
                if self.action == 'log':
                    output = self._t('Latest 100 commits at most; both histories are shown.') + '\n\n' + output
                self._output(output or self._t('No output'))
                return
            operation = plan_project_pull if self.action == 'pull' else plan_project_push
            plan = await self._run(operation, self.review.path, self.destination)
            targets = plan.targets
            if (plan.commit != self.snapshot.head or plan.branch != self.snapshot.branch
                    or len(targets) != 1 or targets[0].remote != self.review.remote
                    or targets[0].branch != self.review.branch or targets[0].url != self.snapshot.remote_url
                    or self.action == 'pull' and targets[0].commit != self.review.commit):
                raise ProjectGitError(self._t('Git history or destination changed. Close this dialog and refresh the review.'))
            if self.action == 'push' and targets[0].error:
                raise ProjectGitError(targets[0].error)
            self.plan = plan
            target = plan.target_commit if self.action == 'pull' else plan.commit
            lines = [f'{self.destination} ({self.review.remote}) → {targets[0].branch}', targets[0].url,
                     self._t('Source branch: {branch}').format(branch=plan.branch),
                     self._t('Committed work: {commit}').format(commit=plan.commit),
                     self._t('Target commit: {commit}').format(commit=target), '',
                     self._t('Confirm to apply this fast-forward. Local changes are never stashed or overwritten.')
                     if self.action == 'pull' else self._t('Only committed work is pushed, without force. Confirm to continue.')]
            if self.action == 'push':
                lines.insert(5, self._t('Uncommitted changes excluded: {count}').format(count=plan.dirty_count))
            self._output('\n'.join(lines))
        except (ProjectGitError, OSError) as error:
            self.plan = None
            self._output(str(error), error=True)
        finally:
            self._set_busy(False)

    async def _apply(self):
        plan = self.plan
        if self.busy or plan is None:
            return
        self._set_busy(True)
        self.plan = None
        self._output(self._t('Running Git operation…'))
        try:
            operation = pull_project if self.action == 'pull' else push_project
            result = await self._run(operation, plan)
            if self.action == 'pull':
                self.updated_commit = plan.target_commit
                self._output(result, success=True)
            else:
                lines = []
                for outcome in result:
                    lines.append(self._t('Succeeded' if outcome.success else 'Failed') + ': ' + outcome.message)
                    if outcome.success:
                        self.updated_commit = plan.commit
                self._output('\n'.join(lines), error=not all(item.success for item in result),
                             success=all(item.success for item in result))
        except (ProjectGitError, OSError) as error:
            self._output(str(error), error=True)
        finally:
            self._set_busy(False)

    def action_close(self):
        if not self.busy:
            self.dismiss(self.updated_commit)

    async def on_button_pressed(self, event: AppButton.Pressed):
        event.stop()
        if event.button.id == 'git-action-confirm':
            await self._apply()
        elif event.button.id == 'git-action-close':
            self.action_close()
