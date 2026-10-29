"""Review captured committed work before publishing it to project remotes."""
import asyncio

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Static

from ft_tui.features.projects.adapters.git import ProjectGitError, plan_project_push, push_project
from ft_tui.i18n import translate
from ft_tui.ui.button import AppButton
from ft_tui.ui.modal import AppModal


class ProjectGitPushScreen(AppModal):
    BINDINGS = [("escape", "close", "Close")]
    DEFAULT_CSS = """
    #git-push-dialog { width: 90%; max-width: 100; height: 85%; border: round $primary; padding: 1 2; }
    #git-push-scroll { height: 1fr; }
    #git-push-review, #git-push-results { height: auto; margin-bottom: 1; }
    #git-push-actions { height: auto; }
    #git-push-actions AppButton { width: 1fr; min-width: 10; }
    """

    def __init__(self, project_name: str, path: str, destination: str, *, dev_remote_url=None, vogsphere_url=None):
        super().__init__()
        self.project_name = project_name
        self.path = path
        self.destination = destination
        self.remote_urls = {"dev_remote_url": dev_remote_url, "vogsphere_url": vogsphere_url}
        self.plan = None
        self.busy = False
        self.results = {}

    def _t(self, message):
        return translate(message, self.app.language)

    def compose(self) -> ComposeResult:
        with Vertical(id="git-push-dialog"):
            yield Static(self._t("Review Git push"), classes="panel-title")
            with VerticalScroll(id="git-push-scroll"):
                yield Static("", id="git-push-review", markup=False)
                yield Static("", id="git-push-results", markup=False)
            with Horizontal(id="git-push-actions"):
                yield AppButton(self._t("Push reviewed commit"), id="git-push-confirm", variant="primary", disabled=True)
                yield AppButton(self._t("Retry dev"), id="git-push-retry-dev", disabled=True)
                yield AppButton(self._t("Retry Vogsphere"), id="git-push-retry-vog", disabled=True)
                yield AppButton(self._t("Close"), id="git-push-close")

    def on_mount(self):
        self._set_busy(True)
        self.run_worker(self._prepare(self.destination))

    def _set_busy(self, busy):
        self.busy = busy
        if not self.is_current:
            return
        self.query_one("#git-push-confirm", AppButton).disabled = busy or self.plan is None
        self.query_one("#git-push-close", AppButton).disabled = busy
        for destination in ("dev", "vog"):
            result = self.results.get(destination)
            self.query_one(f"#git-push-retry-{destination}", AppButton).disabled = busy or result is None or result.success

    async def _prepare(self, destination):
        self.plan = None
        self._set_busy(True)
        review = self.query_one("#git-push-review", Static)
        review.update(self._t("Checking committed work and destinations…"))
        try:
            self.plan = await asyncio.to_thread(plan_project_push, self.path, destination, **self.remote_urls)
            if not self.is_current:
                return
            plan = self.plan
            lines = [self.project_name, str(plan.path),
                     self._t("Source branch: {branch}").format(branch=plan.branch),
                     self._t("Committed work: {commit}").format(commit=plan.commit),
                     self._t("Uncommitted changes excluded: {count}").format(count=plan.dirty_count), ""]
            for target in plan.targets:
                lines.append(f"{target.remote}: {target.url} → {target.branch}")
                if target.error:
                    lines.append(self._t("Blocked: {error}").format(error=target.error))
            lines.extend(("", self._t("Only this commit and its history are pushed. Files are never staged or committed."),
                          self._t("Vogsphere requires the 42 campus network; the reviewed destination branch is used without force.")))
            review.update("\n".join(lines))
        except (ProjectGitError, OSError) as error:
            if self.is_current:
                review.update(self._t("Cannot prepare push: {error}").format(error=error))
        finally:
            self._set_busy(False)

    async def _push(self):
        plan = self.plan
        if plan is None or self.busy:
            return
        self._set_busy(True)
        self.query_one("#git-push-review", Static).update(self._t("Pushing reviewed commit…"))
        try:
            results = await asyncio.to_thread(push_project, plan)
            if not self.is_current:
                return
            self.results.update((result.target.destination, result) for result in results)
            lines = []
            for result in self.results.values():
                status = self._t("Succeeded") if result.success else self._t("Failed")
                lines.append(f"{result.target.remote} → {result.target.branch}: {status}\n{result.message}")
            self.query_one("#git-push-results", Static).update("\n\n".join(lines))
            self.query_one("#git-push-review", Static).update(self._t("Push results"))
        except (ProjectGitError, OSError) as error:
            if self.is_current:
                self.query_one("#git-push-review", Static).update(self._t("Push failed: {error}").format(error=error))
        finally:
            self.plan = None
            self._set_busy(False)

    async def on_button_pressed(self, event: AppButton.Pressed):
        event.stop()
        if event.button.id == "git-push-close":
            self.action_close()
        elif event.button.id == "git-push-confirm":
            await self._push()
        elif event.button.id in ("git-push-retry-dev", "git-push-retry-vog") and not self.busy:
            destination = event.button.id.removeprefix("git-push-retry-")
            result = self.results.get(destination)
            if result is not None and not result.success:
                await self._prepare(destination)

    def action_close(self):
        if not self.busy:
            self.dismiss()
