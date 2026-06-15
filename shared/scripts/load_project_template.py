import sys
if "D:\CoffeeVeinStudio\Pipeline\shared\vendor" not in sys.path:
    sys.path.insert(0, r"D:\CoffeeVeinStudio\Pipeline\shared\vendor")

import os
import yaml
import gazu

import pprint

def init_gazu():
    gazu.client.set_host("http://vonsydow.local:8012/api")
    gazu.log_in("admin@example.com", "mysecretpassword")


def create_gazu_project(project_name: str, production_type: str = "short", production_style: str = "commercial"):
    """Skapar ett nytt projekt i Gazus system."""
    init_gazu()
    project = gazu.project.new_project(project_name, production_type=production_type, production_style=production_style)
    print(f"Skapade Gazu-projekt: {project['name']} (ID: {project['id']})")
    return project


def load_project_template(type: str) -> dict:
    """Laddar YAML-mallen för grundstrukturen."""
    match type:
        case "project":
            file_path = r"D:/CoffeeVeinStudio/Pipeline/shared/templates/project_template.yaml"
                
        case "shot":
            file_path = r"D:/CoffeeVeinStudio/Pipeline/shared/templates/shot_template.yaml"
                
        case _:
            raise ValueError(f"Okänd malltyp: {type}")
        
    if not os.path.isfile(file_path):
        raise FileNotFoundError("Mallfilen hittades inte. Kontrollera sökvägen.")
    
    with open(file_path, "r") as f:
        template = yaml.safe_load(f)

    if not isinstance(template, dict):
        raise ValueError("Mallfilen saknar en giltig struktur. Förväntades vara en dict.")
    
    return template


def create_project_structure(base_path, project_name, template):
    """Skapar mappstrukturen baserat på den laddade mallen."""
    for folder in template.keys():
        path = os.path.join(base_path, project_name, folder)
        os.makedirs(path, exist_ok=True)
        print(f"Skapade mapp: {path}")


def create_shot_structure(project_id, template):
    """Skapar en grundläggande shot-struktur i Gazu baserat på mallen."""
    for folder in template.keys():
        # Här kan du implementera logik för att skapa sekvenser och shots i Gazu
        print(f"Skulle skapa sekvens/shot för: {folder} i projekt ID: {project_id}")


def _test_create_project():
    project_base_path = r"D:/CoffeeVeinStudio/Projects/"
    project_name = "NewProject"
    production_type = "short" #short, featurefilm, tvshow.
    production_style = "commercial" #2d, 3d, 2d3d, ar, vfx, stop-motion, motion-design, archviz, commercial, catalog, immersive, nft, video-game, vr.
    template = load_project_template("project")
    
    create_project_structure(project_base_path, project_name, template)
    create_gazu_project(project_name, production_type, production_style)

def _gazu_help():
    init_gazu()
    help(gazu.project.new_project)

def _test_create_shot():
    init_gazu()
    project_id = 123  # Ersätt med ett giltigt projekt-ID
    template = load_project_template("shot")
    create_shot_structure(project_id, template)

if __name__ == "__main__":
    #_gazu_help()
    #_test_create_project()
    _test_create_shot()
    