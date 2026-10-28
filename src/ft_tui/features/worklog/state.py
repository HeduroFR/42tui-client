"""Single owner of note editor selection and sidebar request generation."""
from dataclasses import dataclass

@dataclass
class WorklogState:
    selected_note_id:int|None=None
    previewing:bool=False
    notes_revision:int=0
    project_key:str|None=None
    saved_contents:tuple[str,str]=("", "")
    prompt_pending:bool=False
