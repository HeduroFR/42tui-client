"""Note and local time operations independent of the app and database engine."""
from .ports import WorklogRepository

class WorklogService:
    def __init__(self,repository:WorklogRepository):self.repository=repository
    def notes(self,project_id,limit=None):return self.repository.notes(project_id,limit)
    def note(self,note_id):return self.repository.note(note_id)
    def save_note(self,project_id,note_id,title,content):
        title=title.strip()
        if not title:raise ValueError('A note title is required.')
        return self.repository.save_note(project_id,note_id,title,content)
    def delete_note(self,note_id):self.repository.delete_note(note_id)
    def timer(self,project_id):return self.repository.timer(project_id)
    def toggle_timer(self,project_id):return self.repository.toggle_timer(project_id)
    def heartbeat(self,path,**kwargs):return self.repository.heartbeat(path,**kwargs)
