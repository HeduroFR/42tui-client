"""Project operations delegate persistence and Git work through explicit ports."""
from .ports import ProjectRepository,Checkout

class ProjectService:
    def __init__(self,repository:ProjectRepository,checkout:Checkout):
        self.repository=repository
        self.checkout=checkout
    def save_settings(self,project_id,values,*,catalog,progress):
        return self.repository.save_settings(project_id,values,catalog=catalog,progress=progress)
    def setup_checkout(self,path,**kwargs):return self.checkout(path,**kwargs)
