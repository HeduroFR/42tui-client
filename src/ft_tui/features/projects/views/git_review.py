"""Review fetched history before explicitly opening existing local files."""
import asyncio
import shlex

from rich.text import Text

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static

from ft_tui.i18n import translate
from ft_tui.ui.button import AppButton
from ft_tui.ui.modal import AppModal
from ft_tui.features.projects.adapters.checkout import CheckoutReviewRequired
from ft_tui.features.projects.adapters.git import ProjectGitError, review_project_checkout


_HISTORY_ADVICE = {
    'behind': 'The remote is ahead. Review a fast-forward pull from {remote}.',
    'diverged': 'Local and {remote} histories diverge. A fast-forward pull cannot combine them; inspect the commits and choose a merge or rebase manually.',
    'unrelated': 'Local and {remote} histories have no common ancestor. Verify the remote URL and project before reconciling them manually.',
    'ahead': 'Local history contains the fetched {remote} snapshot. No pull is needed; review a push to publish local commits.',
    'equal': 'Local history matches the fetched {remote} snapshot. No pull is needed.',
    'unborn': 'There is no local commit. Preserve existing files before choosing how to recover the remote history.',
    'unknown': 'Inspect local Git history before synchronizing.',
}


class ProjectGitReviewScreen(AppModal[bool]):
    BINDINGS = [('escape', 'cancel', 'Cancel')]
    COMPONENT_CLASSES = {'git-review--added', 'git-review--removed', 'git-review--file',
                         'git-review--hunk', 'git-review--metadata'}
    DEFAULT_CSS = """
    ProjectGitReviewScreen .git-review--added { color: $success; }
    ProjectGitReviewScreen .git-review--removed { color: $error; }
    ProjectGitReviewScreen .git-review--file { color: $primary; text-style: bold; }
    ProjectGitReviewScreen .git-review--hunk { color: $accent; text-style: bold; }
    ProjectGitReviewScreen .git-review--metadata { text-style: dim; }
    #git-review-dialog { width: 96; max-width: 94%; height: 90%; border: round $primary; padding: 1 2; }
    #git-review-scroll { height: 1fr; }
    #git-review-scroll Static { height: auto; margin-bottom: 1; }
    #git-review-actions { height: 3; align-horizontal: center; }
    """

    def __init__(self, review: CheckoutReviewRequired, *, project_name: str):
        super().__init__()
        self.review = review
        self.project_name = project_name
        self.destination = {"origin": "dev", "vogsphere": "vog"}.get(review.remote, review.remote)

    def compose(self) -> ComposeResult:
        tr = lambda text: translate(text, self.app.language)
        with Vertical(id='git-review-dialog'):
            yield Static(tr('Review Git differences'), classes='panel-title')
            with VerticalScroll(id='git-review-scroll'):
                yield Static(f'{self.project_name}\n{self.review.path}', markup=False)
                yield Static(tr('Remote concerned') + f': {self.destination} ({self.review.remote})\n'
                             + tr('Remote branch') + f': {self.review.branch}\n{self.review.commit}',
                             id='git-review-remote', markup=False)
                yield Static(tr('Opening local files does not pull, merge or overwrite your work. Reconcile Git history before synchronizing.'))
                yield Static(tr('Untracked files are listed below; their contents are not included in the diff.'))
                yield Static(tr('Loading') + '…', id='git-review-content', markup=False)
            with Horizontal(id='git-review-actions'):
                yield AppButton(tr('Open local files'), id='git-review-open', disabled=True)
                yield AppButton(tr('Cancel'), id='git-review-cancel')

    def on_mount(self) -> None:
        self.run_worker(self._load())

    async def _load(self) -> None:
        tr = lambda text: translate(text, self.app.language)
        try:
            result = await asyncio.to_thread(review_project_checkout, self.review.path, self.review.commit,
                                             remote=self.review.remote)
            advice = _HISTORY_ADVICE[result.relationship]
            commands = [f'cd {shlex.quote(str(self.review.path))}', '42git status']
            if result.relationship == 'behind':
                commands.append(shlex.join(('42git', 'pull', self.destination)))
            elif result.relationship == 'ahead':
                commands.append(shlex.join(('42git', 'push', self.destination)))
            elif result.relationship in {'diverged', 'unrelated'}:
                commands.append(shlex.join(('git', '-C', str(self.review.path), 'log', '--oneline', '--graph',
                                            'HEAD', self.review.commit, '--')))
            content = Text.assemble(
                (tr('Remote URL') + ': ', 'bold'), f'{result.remote_url or "—"}\n',
                (tr('Commits only here: {local} · only on {remote}: {count}').format(
                    local=result.local_only, remote=self.destination, count=result.remote_only) + '\n\n', 'bold'),
                (tr('Suggested next step') + '\n', 'bold'),
                tr(advice).format(remote=self.destination) + '\n',
                (tr(result.pull_blocker) + '\n' if result.pull_blocker else '', 'bold'),
                ('\n'.join(commands) + '\n', self.get_component_rich_style('git-review--hunk', partial=True)),
                tr('Run these commands in your terminal. Nothing is pulled, merged or pushed by this dialog.') + '\n\n',
                (f'{tr("Local branch")}: ', 'bold'), f'{result.branch}\n',
                ('HEAD: ', 'bold'), (f'{result.head}\n\n', 'dim'),
                (tr("Local changes") + '\n', 'bold'), f'{result.status or tr("None")}\n\n',
                (tr("Diff: remote snapshot → local tracked files") + '\n', 'bold'),
            )
            for line in (result.diff or tr("No tracked differences")).splitlines(keepends=True):
                if line.startswith(('diff --git ', '--- ', '+++ ', 'rename from ', 'rename to ')):
                    kind = 'file'
                elif line.startswith('@@'):
                    kind = 'hunk'
                elif line.startswith('+'):
                    kind = 'added'
                elif line.startswith('-'):
                    kind = 'removed'
                elif line.startswith(('index ', 'new file mode ', 'deleted file mode ', 'similarity index ')):
                    kind = 'metadata'
                else:
                    kind = None
                style = self.get_component_rich_style(f'git-review--{kind}', partial=True) if kind else ''
                content.append(line, style=style)
        except (ProjectGitError, OSError) as error:
            content = f'{tr("Could not inspect Git differences")}: {error}'
        if not self.is_current:
            return
        self.query_one('#git-review-content', Static).update(content)
        self.query_one('#git-review-open', AppButton).disabled = False

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: AppButton.Pressed) -> None:
        event.stop()
        self.dismiss(event.button.id == 'git-review-open')
