"""Review fetched history before explicitly opening existing local files."""
import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static

from ft_tui.i18n import translate
from ft_tui.ui.button import AppButton
from ft_tui.ui.modal import AppModal
from ft_tui.features.projects.adapters.checkout import CheckoutReviewRequired
from ft_tui.features.projects.adapters.git import ProjectGitError, review_project_checkout


class ProjectGitReviewScreen(AppModal[bool]):
    BINDINGS = [('escape', 'cancel', 'Cancel')]
    DEFAULT_CSS = """
    #git-review-dialog { width: 96; max-width: 94%; height: 90%; border: round $primary; padding: 1 2; }
    #git-review-scroll { height: 1fr; }
    #git-review-scroll Static { height: auto; margin-bottom: 1; }
    #git-review-actions { height: 3; align-horizontal: center; }
    """

    def __init__(self, review: CheckoutReviewRequired, *, project_name: str):
        super().__init__()
        self.review = review
        self.project_name = project_name

    def compose(self) -> ComposeResult:
        tr = lambda text: translate(text, self.app.language)
        with Vertical(id='git-review-dialog'):
            yield Static(tr('Review Git differences'), classes='panel-title')
            with VerticalScroll(id='git-review-scroll'):
                yield Static(f'{self.project_name}\n{self.review.path}', markup=False)
                yield Static(tr('Remote snapshot') + f': {self.review.remote}/{self.review.branch}\n{self.review.commit}', markup=False)
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
            result = await asyncio.to_thread(review_project_checkout, self.review.path, self.review.commit)
            content = (f'{tr("Local branch")}: {result.branch}\nHEAD: {result.head}\n\n'
                       f'{tr("Local changes")}\n{result.status or tr("None")}\n\n'
                       f'{tr("Diff: remote snapshot → local tracked files")}\n{result.diff or tr("No tracked differences")}')
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
