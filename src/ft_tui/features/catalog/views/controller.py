"""Textual scheduling and presentation for the headless catalog use cases."""
import asyncio
from functools import partial
import httpx
from ft_tui.ui.components import Select, Button


class ProjectCatalogControllerMixin:
    def _cancel_catalog_requests(self):
        self._catalog_generation = getattr(self, '_catalog_generation', 0) + 1
        self._catalog_next = []
        self._branch_cursor = None
        self._branch_snapshot = None
        self._catalog_snapshot = None

    def _catalog_scope(self):
        return self.catalog_service.scope(self.account_id, self.account_campuses)

    def _resolved_curriculum(self, curriculum):
        return self.catalog_service.resolve(curriculum, self.account_id, self._catalog_scope())

    def _request_catalog_refresh(self):
        scope = self._catalog_scope()
        if getattr(self, '_catalog_request', None) == (
                self.provider, self.account_generation, scope, self._catalog_generation):
            return
        if scope and self.catalog_service.cached(scope):
            return
        if self.provider is not None:
            self.run_worker(
                partial(self._refresh_catalog_context, self.provider, self.account_generation),
                group='catalog', exclusive=True,
            )

    async def _refresh_catalog_context(self, provider, account_generation, more=False, *, force=False):
        scope = self._catalog_scope()
        if scope is None:
            self.catalog_status = 'Choose a campus in Settings.'
            await self._reload_project_catalog()
            return
        self._catalog_generation = getattr(self, '_catalog_generation', 0) + 1
        token, account = self._catalog_generation, self.account_id
        request = (provider, account_generation, scope, token)
        self._catalog_request = request

        def current():
            return (provider is self.provider and account_generation == self.account_generation
                    and token == self._catalog_generation and account == self.account_id
                    and scope == self._catalog_scope())

        try:
            if not more:
                curriculum = await self.catalog_service.refresh_account(provider, account, scope, current)
                if curriculum is None:
                    return
                # Preserve the displayed curriculum until its replacement catalog is ready.
                next_curriculum = self._resolved_curriculum(curriculum)
                track = next_curriculum.get('selected_track', {}).get('track')
                self._catalog_next, self._catalog_snapshot = [], None
                self.catalog_status = 'Choose your Common Core track in Settings.' if not track else f'{track} + shared'
                self._branch_cursor = None
                if track:
                    try:
                        branches = await self.catalog_service.load_branches(provider, scope, track, current)
                        if branches is None:
                            return
                        self._branch_cursor = branches.get('next_cursor')
                        self._branch_snapshot = branches.get('snapshot_id')
                        self._set_branch_options(branches['items'])
                    except Exception:
                        self._branch_cursor = None
            snapshot = await self.catalog_service.refresh_catalog(provider, scope, current, force=force)
            if snapshot is None:
                return
            if snapshot.meta is not None:
                self.catalog_status = f"Saved catalog · {snapshot.meta.get('collected_at', '')}"
                if snapshot.meta.get('stale'):
                    self.catalog_status += ' · stale'
            self._catalog_snapshot, self._catalog_next = snapshot.snapshot_id, []
            if current():
                await self._reload_project_catalog()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            if current():
                pending = False
                if isinstance(error, httpx.HTTPStatusError):
                    try:
                        pending = error.response.json().get('error') == 'catalog_pending'
                    except (ValueError, AttributeError):
                        pass
                self.catalog_status = 'Loading campus graph…' if pending else 'Catalog unavailable. Showing saved data.'
                if pending:
                    def retry():
                        if current():
                            self.run_worker(
                                partial(self._refresh_catalog_context, provider, account_generation, force=force),
                                group='catalog', exclusive=True,
                            )
                    self.set_timer(30, retry)
                self._catalog_next = []
                await self._reload_project_catalog()
        finally:
            if getattr(self, '_catalog_request', None) == request:
                self._catalog_request = None
            if current():
                self.query_one('#catalog-more', Button).disabled = not getattr(self, '_catalog_next', [])
                self.query_one('#catalog-more-branches', Button).disabled = not getattr(self, '_branch_cursor', None)

    def _set_branch_options(self, items, append=False):
        self._branch_items = list(getattr(self, '_branch_items', [])) + items if append else list(items)
        selector = self.query_one('#project-branch', Select)
        previous = selector.value
        options = [('All branches', 'all')] + [
            (item.get('label') or ', '.join(map(str, item['root_project_ids'])), item['branch_id'])
            for item in self._branch_items
        ]
        with self.prevent(Select.Changed):
            selector.set_options(options)
            selector.value = previous if previous in {value for _, value in options} else 'all'

    async def _load_more_branches(self):
        scope = self._catalog_scope()
        track = self.project_curriculum.get('selected_track', {}).get('track')
        cursor = getattr(self, '_branch_cursor', None)
        account_generation, catalog_generation = self.account_generation, self._catalog_generation
        if not scope or not track or not cursor or not self.provider:
            return
        provider = self.provider
        def current():
            return (provider is self.provider and account_generation == self.account_generation
                    and catalog_generation == self._catalog_generation and scope == self._catalog_scope())
        try:
            page = await self.catalog_service.load_branches(
                provider, scope, track, current, cursor=cursor, snapshot=self._branch_snapshot,
                items=self._branch_items,
            )
            if page is None:
                return
            self._set_branch_options(page['items'])
            self._branch_cursor = page.get('next_cursor')
            self.query_one('#catalog-more-branches', Button).disabled = not self._branch_cursor
        except Exception:
            self.notify('Branches unavailable.', severity='warning')

    async def _load_selected_catalog_detail(self, project):
        scope, provider = self._catalog_scope(), self.provider
        generation, catalog_generation = self.account_generation, self._catalog_generation
        key = project.ui_key
        if (not scope or not provider or project.official_project_id is None
                or self.selected_project_key != key):
            return
        def current():
            return (provider is self.provider and generation == self.account_generation
                    and catalog_generation == self._catalog_generation and scope == self._catalog_scope()
                    and self.selected_project_key == key)
        try:
            detail = await self.catalog_service.load_detail(
                provider, scope, project.official_project_id, project.catalog_data.get('snapshot_id'), current,
            )
            if detail is not None:
                project._catalog_data = detail
                self._render_project_details(project)
        except Exception:
            pass
