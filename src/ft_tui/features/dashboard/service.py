"""Compose dashboard values from explicit snapshots and read-only capabilities."""
from datetime import datetime, timedelta
from collections.abc import Callable
from ft_tui.features.catalog.read_models import curriculum_projects
from ft_tui.shared.activity import IDLE_TIMEOUT_SECONDS
from .models import DashboardProject, ProfileStats, Journey, Deadline, Activity, DashboardViewModel
from .ports import DashboardReader


class DashboardService:
    def __init__(self, reader: DashboardReader, *, folder_exists: Callable[[str | None], bool]):
        self.reader = reader
        self.folder_exists = folder_exists

    @staticmethod
    def sorted_projects(projects, activity, active_project_id):
        rows = list(projects)
        rows.sort(key=lambda project: project.name.casefold())
        rows.sort(key=lambda project: activity.get(project.id) or datetime.min, reverse=True)
        rows.sort(key=lambda project: project.id == active_project_id, reverse=True)
        order = {'in_progress': 0, 'available': 1, 'completed': 2, 'done': 2}
        rows.sort(key=lambda project: order.get(project.status.casefold(), 3))
        return rows

    def activity(self, now):
        latest, heartbeat = self.reader.activity()
        active = None
        if heartbeat is not None:
            project_id, at = heartbeat
            age = (now.replace(tzinfo=None) - at).total_seconds()
            if 0 <= age <= IDLE_TIMEOUT_SECONDS:
                active = project_id
        return Activity(latest, active)

    def compose(self, *, projects, profile, goals, curriculum, activity,
                active_project_id, selected_project_key, now):
        rows = [DashboardProject.from_project(project) for project in projects]
        ordered = self.sorted_projects(rows, activity, active_project_id)
        resumable = [p for p in rows if p.status.casefold() not in {'completed', 'done', 'finished', 'locked'}]
        active = next((p for p in resumable if p.id == active_project_id), None)
        recent = None
        if active is not None:
            resume, label = active, 'ACTIVE NOW'
        else:
            recent = max((p for p in resumable if p.id in activity), key=lambda p: activity[p.id], default=None)
            resume = (recent or next((p for p in resumable if p.ui_key == selected_project_key), None)
                      or next(iter(self.sorted_projects(resumable, activity, active_project_id)), None))
            label = 'RECENT ACTIVITY' if recent is not None else 'READY TO RESUME'
        seconds = self.reader.tracked(resume.id) if resume is not None and resume.id is not None else 0.0
        resume_has_folder = bool(resume is not None and self.folder_exists(resume.local_path))
        setup = tuple(p for p in ordered if p.status.casefold() in {'available', 'in_progress'}
                      and not self.folder_exists(p.local_path))
        keys = {}
        for p in rows:
            keys.setdefault(p.id, p.ui_key)
        notes = tuple((note_id, keys.get(local_id, f'local:{local_id}'), name, title, at)
                      for note_id, local_id, name, title, at in self.reader.recent_notes())
        today = now.date()
        monday = today - timedelta(days=today.weekday())
        weeks = tuple(monday-timedelta(weeks=offset) for offset in range(3, -1, -1))
        days = {week+timedelta(days=day): 0.0 for week in weeks for day in range(7)}
        for at, credited in self.reader.heartbeats_since(datetime.combine(weeks[0], datetime.min.time())):
            if at.date() in days:
                days[at.date()] += credited
        week_seconds = {week: sum(days[week+timedelta(days=i)] for i in range(7)) for week in weeks}
        journey_scope = 'specialization' if goals.get('status') == 'available' and goals.get('cc_validated') is True else 'all'
        selected = curriculum_projects(rows, curriculum=curriculum, scope=journey_scope)
        counts = {name: sum(p.status.casefold() == name for p in selected)
                  for name in ('completed', 'done', 'in_progress', 'available', 'locked')}
        next_project = next((p for p in self.sorted_projects(selected, activity, active_project_id)
                             if p.status.casefold() in {'in_progress', 'available'}), None)
        journey = Journey(len(selected), counts['completed']+counts['done'], counts['in_progress'],
                          counts['available'], counts['locked'],
                          next_project.name if next_project else 'All catalog projects completed')
        deadline = self.deadline_summary(curriculum, ordered)
        stats = ProfileStats(
            profile.get('wallet') if type(profile.get('wallet')) is int and profile['wallet'] >= 0 else None,
            profile.get('correction_point') if type(profile.get('correction_point')) is int and profile['correction_point'] >= 0 else None,
            profile.get('location') if isinstance(profile.get('location'), str) and profile['location'].strip() else None,
        )
        return DashboardViewModel(stats, resume, seconds, resume_has_folder, label, active is not None,
                                  recent is not None, setup, notes, weeks, days, week_seconds, journey,
                                  deadline)

    @staticmethod
    def deadline_summary(curriculum, ordered):
        evidence = curriculum.get('selected_rank', {})
        rank, track = evidence.get('rank'), curriculum.get('selected_track', {}).get('track')
        known = type(rank) is int and evidence.get('source') in {'quest', 'project'}
        completed = evidence.get('completed') is True
        milestone = 'Common Core completed' if completed else f'Rank {rank:02d}' if known else 'Unavailable'
        candidates = [p for p in ordered if known and not completed and track
                      and p.catalog_data.get('rank') == rank and p.catalog_data.get('track') in {track, 'shared'}
                      and p.status in {'in_progress', 'available'}]
        next_up = next((p for p in candidates if p.status == 'in_progress'), next(iter(candidates), None))
        next_label = 'Common Core completed' if completed else 'Unavailable'
        if next_up is not None:
            state = 'In progress' if next_up.status == 'in_progress' else 'Available'
            next_label = f'{next_up.name} · {state}'
        return Deadline(milestone, next_label)
