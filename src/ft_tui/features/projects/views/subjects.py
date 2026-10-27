"""Subject rendering and timers, backed by headless subject operations."""
from datetime import datetime
from ft_tui.ui.components import Button,Project,Static,translate
from ..subjects.models import compare_subject_hashes,SubjectViewerUnavailable


class SubjectMixin:
    SUBJECT_PENDING_POLL_SECONDS=2

    def _subject_operations(self):
        service=getattr(self,'subject_service',None)
        if service is None:
            from ft_tui.app.bootstrap import build_subject_service
            service=build_subject_service(self.session_factory)
        return service

    def _refresh_subject_status(self, project: Project) -> None:
        """Render the last automatic local subject check."""
        status = self.query_one("#project-subject-status", Static)
        subject_path,folder_exists,subject_exists=SubjectMixin._subject_operations(self).inspect(
            project.local_path,project.subject_pdf_path)
        self.query_one("#open-subject",Button).disabled=not folder_exists or not subject_exists
        if not project.local_path:
            status.update("SUBJECT · NO FOLDER")
            return
        if not folder_exists:
            status.update(translate("SUBJECT · PATH MISSING", self.language))
            return
        worker_state = getattr(project, "_subject_worker_state", None)
        if worker_state:
            status.update("SUBJECT · QUEUED" if worker_state == "pending" else f"SUBJECT · WORKER · {worker_state}")
            return
        if not subject_exists or not project.subject_pdf_sha256:
            status.update("SUBJECT · MISSING")
            return
        if self.provider is None:
            status.update(f"SUBJECT · HASHED · {project.subject_pdf_sha256[:8]}")
            return
        result = compare_subject_hashes(
            project.subject_pdf_sha256,
            project.subject_reference_sha256,
        )
        if result == "Up to date":
            status.update(
                translate("SUBJECT · [green]CURRENT[/] · {source}", self.language).format(
                    source=translate("42 API", self.language)
                )
            )
        elif result == "Hash differs":
            status.update(
                translate("SUBJECT · [yellow]UPDATE?[/] · {source}", self.language).format(
                    source=translate("42 API", self.language)
                )
            )
        else:
            status.update(f"SUBJECT · HASHED · {project.subject_pdf_sha256[:8]}")


    def _open_selected_subject_pdf(self) -> None:
        """Open the selected project's subject in TDF or the OS PDF application."""
        project = self.projects.get(self.selected_project_key or "")
        if project is None:
            self.notify("Select a project first.", severity="warning")
            return
        operations=SubjectMixin._subject_operations(self)
        subject_path,_,exists=operations.inspect(project.local_path,project.subject_pdf_path)
        if not exists:
            self.notify("The subject PDF is not available yet.", severity="warning")
            return

        if self.favorite_subject_viewer == "tdf":
            executable = operations.viewer("tdf")
            if executable is None:
                self.notify(
                    "TDF was not found on PATH. Install it or select System default in Settings.",
                    severity="error",
                )
                return
            if self.activity_refresh_timer is not None:
                self.activity_refresh_timer.pause()
            button = self.query_one("#open-subject", Button)
            pointer = button.styles.pointer
            try:
                button.styles.pointer = "default"
                self.screen.update_pointer_shape()
                with self.suspend():
                    result = operations.run_tdf(executable,subject_path)
            except OSError as error:
                self.notify(f"Could not open subject with TDF: {error}", severity="error")
                return
            finally:
                button.styles.pointer = pointer
                self.screen.update_pointer_shape()
                if self.activity_refresh_timer is not None:
                    self.activity_refresh_timer.resume()
                self.refresh(layout=True)
            if result.returncode:
                self.notify(f"TDF exited with status {result.returncode}.", severity="error")
            return

        try:
            operations.open_system(subject_path)
        except SubjectViewerUnavailable as error:
            self.notify(str(error),severity="error")
            return
        except OSError as error:
            self.notify(f"Could not open the subject PDF: {error}", severity="error")


    def _start_due_subject_checks(self) -> None:
        """Schedule periodic checking and optional downloading outside the UI thread."""
        if not self.is_mounted:
            return
        if any(worker.group == "subject-pdf-check" and not worker.is_finished for worker in self.workers):
            return
        self.run_worker(
            self._check_due_subjects_in_background,
            name="periodic-subject-check",
            group="subject-pdf-check",
            exclusive=True,
            thread=True,
        )


    def _check_due_subjects_in_background(self) -> None:
        operations=SubjectMixin._subject_operations(self)
        context=(getattr(self,'account_generation',None),getattr(self,'account_id',None),id(self.provider))
        def current():
            return (getattr(self,'is_mounted',True) and context==(
                getattr(self,'account_generation',None),getattr(self,'account_id',None),id(self.provider)))
        def publish(callback,*args):
            # Recheck on the UI thread, after the callback waited in its queue.
            if current():callback(*args)
        def pending(slug,state):
            if current():self.call_from_thread(publish,self._report_subject_worker_state,slug,state)
        results,errors=operations.sync_due(self.provider,self.subject_check_interval_seconds,pending,current=current)
        if current():self.call_from_thread(publish,self._report_automatic_subject_checks,results,errors)


    def _report_subject_worker_state(self, slug: str, state: str) -> None:
        for project in self.projects.values():
            if project.slug == slug:
                project._subject_worker_state = state
                if self.selected_project_key == project.ui_key:
                    self._refresh_subject_status(project)
        if state == "pending":
            # Keep queued downloads responsive independently of the much longer
            # interval used to check PDFs that have already been downloaded.
            retry = getattr(self, "_subject_pending_timer", None)
            if retry is not None:
                retry.stop()
            self._subject_pending_timer = self.set_timer(
                self.SUBJECT_PENDING_POLL_SECONDS, self._start_due_subject_checks,
            )


    def _report_automatic_subject_checks(
        self,
        results: list[tuple[int, str, str, str | None, str | None, datetime, bool]],
        errors: list[tuple[str, str]],
    ) -> None:
        """Update visible project status and surface only changes/errors."""
        for project_id, slug, path, digest, reference, checked, changed in results:
            project = next((p for p in self.projects.values() if p.id == project_id), None)
            if project is None:
                continue
            project._subject_worker_state = None
            project.subject_pdf_path = path
            project.subject_pdf_sha256 = digest
            project.subject_reference_sha256 = reference
            project.subject_checked_at = checked
            if self.selected_project_key == project.ui_key:
                self._refresh_subject_status(project)
            if changed:
                self.notify(f"{project.name}: subject PDF or reference changed.", severity="warning", timeout=10)
        for slug, error in errors:
            project = next((p for p in self.projects.values() if p.slug == slug), None)
            name = project.name if project is not None else slug
            self.notify(f"{name}: subject check failed: {error}", severity="error", timeout=10)
