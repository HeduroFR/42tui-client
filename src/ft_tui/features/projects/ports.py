"""Persistence and local checkout capabilities for project workflows."""
from typing import Protocol

class ProjectRepository(Protocol):
    def save_settings(self,project_id:int,values:dict,*,catalog:dict,progress:dict): ...

class Checkout(Protocol):
    def __call__(self,path,**kwargs): ...
