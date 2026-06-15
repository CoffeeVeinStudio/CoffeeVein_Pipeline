import os
from pathlib import Path

def create_project_structure(project, template, config):
    """Skapar mappstrukturen baserat på den laddade mallen."""
    
    if isinstance(project, dict):
        project = project['name']
    
    for folder in template.keys():
        path = Path(config['projects_root']) / project / folder
        os.makedirs(path, exist_ok=True)


def create_shot_structure(project: str | dict, sequence: str | dict, shot_name: str, template, config):
    """Skapar en grundläggande shot-struktur i Gazu baserat på mallen."""
    
    if isinstance(project, dict):
        project = project['name']
    if isinstance(sequence, dict):
        sequence = sequence['name']
        
    for folder in template.keys():
        path = Path(config['projects_root']) / project / "Work" / sequence / shot_name / folder
        os.makedirs(path, exist_ok=True)