"""Single owner of note editor selection and sidebar request generation."""
from dataclasses import dataclass

@dataclass
class WorklogState:
    selected_note_id:int|None=None
    previewing:bool=False
    notes_revision:int=0
