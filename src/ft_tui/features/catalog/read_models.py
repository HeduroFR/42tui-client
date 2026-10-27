"""Project selection uses published ranks; registration uses API IDs only."""


def curriculum_section(curriculum):
    rank = curriculum.get('selected_rank', {})
    return ('specialization' if rank.get('source') == 'quest' and rank.get('completed') is True
            else 'common-core')


def curriculum_projects(projects, *, curriculum=None, scope='relevant', active_project_id=None, cursus_id=None,
                        kind='all'):
    projects, curriculum = list(projects), curriculum or {}
    track = curriculum.get('selected_track', {}).get('track')
    rank = curriculum.get('selected_rank', {}).get('rank')
    registration = curriculum.get('registration', {})
    eligible = (set(registration.get('project_ids', []))
                if registration.get('status') == 'available' and not registration.get('stale', True) else set())

    def selected(project):
        return bool(track and project.catalog_data.get('track') in (track, 'shared'))

    def active(project):
        return (project.local_path or project.status == 'in_progress'
                or active_project_id is not None and project.id == active_project_id)

    if scope == 'relevant':
        if kind != 'all':
            return [project for project in projects if selected(project) and project.catalog_data.get('kind') == kind]
        local = [project for project in projects if project.official_project_id is None and active(project)]
        if not track:
            return local
        return local + [
            project for project in projects if project not in local and (
                project.progress_data and project.catalog_data.get('track') in (None, track, 'shared')
                or selected(project) and (
                    type(rank) is int and project.catalog_data.get('rank') in (rank, rank + 1)
                    or type(rank) is not int and project.catalog_data.get('section') == curriculum_section(curriculum)
                )
            )
        ]
    if scope == 'eligible':
        return [project for project in projects if project.official_project_id in eligible]
    if scope == 'active':
        return [project for project in projects if active(project)]
    if scope == 'specialization':
        return [project for project in projects if selected(project)
                and project.catalog_data.get('section') == 'specialization']
    if scope == 'all':
        return [project for project in projects if selected(project)
                and project.catalog_data.get('section') == curriculum_section(curriculum)]
    return []
