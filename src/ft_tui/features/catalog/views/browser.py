"""Paged catalog browser with exclusive Common Core track filtering."""
from ft_tui.features.catalog.read_models import curriculum_projects
from ft_tui.shared.fuzzy_search import fuzzy_score
from ft_tui.ui.components import Button, Input, ListView, ProjectEntry, ProjectRankHeader, Select, Static


class ProjectBrowserMixin:
    @staticmethod
    def _project_view_options(cursus_id):
        return [
            ('My 42 projects', 'relevant'), ('All projects', 'all'),
            ('Registerable projects', 'eligible'), ('Specializations', 'specialization'),
            ('Active and local projects', 'active'),
        ]

    def _load_project_browser_preferences(self):
        with self.session_factory() as session:
            cursus = self._configured_cursus_id(session)
            if getattr(self, '_browser_cursus_id', object()) == cursus:
                return
            self._browser_cursus_id = cursus
        with self.prevent(Select.Changed):
            selector = self.query_one('#project-view', Select)
            options = self._project_view_options(cursus)
            selector.set_options(options)
            selector.value = 'relevant'

    def _visible_projects(self):
        view = self.query_one('#project-view', Select).value
        kind = self.query_one('#project-kind', Select).value
        projects = curriculum_projects(
            self._sorted_projects(self.projects.values()), curriculum=self.project_curriculum,
            scope=view, active_project_id=self.active_project_id, cursus_id=self._browser_cursus_id, kind=kind,
        )
        query = self.query_one('#project-search', Input).value.strip().casefold()
        branch = self.query_one('#project-branch', Select).value if view == 'specialization' else 'all'
        revealed = self.projects.get(getattr(self, '_revealed_project_key', None))
        if revealed is not None and view == 'all' and kind == 'all' and not query and revealed not in projects:
            projects.append(revealed)
        branch_items = next((item['project_ids'] for item in getattr(self, '_branch_items', [])
                             if item['branch_id'] == branch), [])
        scores = {project.ui_key: fuzzy_score(query, project.name, project.slug) for project in projects}
        filtered = [
            project for project in projects
            if scores[project.ui_key] is not None
            and (kind == 'all' or project.catalog_data.get('kind') == kind)
            and (branch == 'all' or project.official_project_id in branch_items)
        ]

        return sorted(filtered, key=lambda project: (
            self._project_rank(project) is None, self._project_rank(project) or 0,
            project.catalog_data.get('kind') != 'exam',
            scores[project.ui_key], project.name.casefold(), project.ui_key,
        ))

    @staticmethod
    def _project_rank(project):
        rank = project.catalog_data.get('rank')
        return rank if type(rank) is int else None

    def _rank_group_key(self, rank):
        scope = self._catalog_scope()
        return (self.account_id, self._browser_cursus_id, scope.campus_id if scope else None,
                self.query_one('#project-view', Select).value, rank)

    def _expanded_projects(self, projects):
        context = self._rank_group_key(None)[:-1]
        expanded = getattr(self, '_expanded_project_ranks', set())
        return [project for project in projects if (*context, self._project_rank(project)) in expanded]

    def _project_entries(self, projects):
        entries = []
        groups = {}
        context = self._rank_group_key(None)[:-1]
        for project in projects:
            groups.setdefault(self._project_rank(project), []).append(project)
        for rank, group in groups.items():
            key = (*context, rank)
            collapsed = key not in getattr(self, '_expanded_project_ranks', set())
            entries.append(ProjectRankHeader(rank, group, key, collapsed=collapsed))
            if not collapsed:
                entries.extend(ProjectEntry(project, active=self.active_project_id is not None
                                            and project.id == self.active_project_id) for project in group)
        return entries

    async def _toggle_project_rank(self, header):
        expanded = getattr(self, '_expanded_project_ranks', set())
        if header.group_key in expanded:
            expanded.remove(header.group_key)
        else:
            expanded.add(header.group_key)
        self._expanded_project_ranks = expanded
        await self._refresh_project_list(self.selected_project_key, _preferred_group=header.group_key)

    async def _clear_project_browser_selection(self, message):
        self.selected_project_key = None
        self._clear_project_details()
        self.query_one('#details-content', Static).update(message)
        for selector in ('#open-project-editor', '#project-timer-toggle', '#open-subject', '#new-project-note'):
            self.query_one(selector, Button).disabled = True
        await self.query_one('#project-notes-list', ListView).clear()

    async def _refresh_project_list(self, preferred_key=None, *, _current=None, _preferred_group=None):
        current = _current or (lambda: True)
        if not current():
            return []
        self._project_filter_value = self.query_one('#project-view', Select).value
        specialized = self._project_filter_value == 'specialization'
        self.query_one('#project-branch', Select).styles.display = 'block' if specialized else 'none'
        self.query_one('#catalog-more', Button).styles.display = 'block' if getattr(self, '_catalog_next', []) else 'none'
        has_branches = specialized and getattr(self, '_branch_cursor', None)
        self.query_one('#catalog-more-branches', Button).styles.display = 'block' if has_branches else 'none'
        projects = self._visible_projects()
        listing = self.query_one('#project-list-view', ListView)
        if not listing.is_attached:
            return []
        if _preferred_group is None and isinstance(listing.highlighted_child, ProjectRankHeader):
            _preferred_group = listing.highlighted_child.group_key
        groups = {}
        for project in projects:
            groups.setdefault(self._project_rank(project), []).append(project)
        context = self._rank_group_key(None)[:-1]
        expanded = getattr(self, '_expanded_project_ranks', set())
        expected = []
        for rank, group in groups.items():
            key = (*context, rank)
            expected.append(('rank', key, key not in expanded))
            if key in expanded:
                expected.extend(('project', project.ui_key) for project in group)
        actual = [
            ('rank', row.group_key, row.collapsed) if isinstance(row, ProjectRankHeader)
            else ('project', row.key) if isinstance(row, ProjectEntry) else None
            for row in listing.children
        ]
        if actual == expected:
            # Account refreshes often change status/details without changing rows.
            # Preserve the mounted widgets, scroll position and highlight.
            for row in listing.children:
                if isinstance(row, ProjectRankHeader):
                    row.update_projects(groups[row.rank])
                elif isinstance(row, ProjectEntry):
                    row.active = row.project.id == self.active_project_id and self.active_project_id is not None
                    row.update_project(self.projects[row.key])
        else:
            # Do not render the temporary empty list between clear and extend.
            with self.batch_update(), listing.prevent(ListView.Highlighted):
                await listing.clear()
                if not current() or not listing.is_attached:
                    return []
                await listing.extend(self._project_entries(projects))
        if not current() or not listing.is_attached:
            return []
        self.query_one('#project-count', Static).update(f'{len(projects)} loaded')
        self.query_one('#project-empty', Static).styles.display = 'none' if projects else 'block'
        if projects:
            rows = list(listing.children)
            target = next((i for i, row in enumerate(rows)
                           if isinstance(row, ProjectRankHeader) and row.group_key == _preferred_group), None)
            if target is None:
                target = next((i for i, row in enumerate(rows)
                               if isinstance(row, ProjectEntry) and row.key == preferred_key), None)
            if target is None:
                target = next((i for i, row in enumerate(rows) if isinstance(row, ProjectEntry)), 0)
            listing.index = target
            entry = rows[target]
            if isinstance(entry, ProjectEntry):
                self._show_project(entry.project)
                self.query_one('#new-project-note', Button).disabled = entry.project.id is None
            elif self.selected_project_key not in {project.ui_key for project in projects}:
                await self._clear_project_browser_selection('Select a project from the list.')
        else:
            message = ('Choose your Common Core track in Settings.'
                       if not self.project_curriculum.get('selected_track', {}).get('track')
                       else 'No projects match this view.')
            await self._clear_project_browser_selection(message)
        return projects
