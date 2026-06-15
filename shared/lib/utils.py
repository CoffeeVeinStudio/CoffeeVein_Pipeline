import sys
from pathlib import Path

VENDOR_PATH = Path(__file__).parent.parent / "vendor"
if str(VENDOR_PATH)  not in sys.path:
    sys.path.insert(0, str(VENDOR_PATH))

import yaml


def load_config() -> dict:
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def load_env() -> dict:
    env_path = Path(__file__).parent / ".env"
    env_vars = {}
    with open(env_path, "r") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                key, value = line.strip().split("=", 1)
                env_vars[key] = value
    return env_vars


def load_template(type: str) -> dict:
    """Laddar YAML-mallen för grundstrukturen.
    
     Alternativ för type: "project", "shot"
     
     Mallen används för att skapa mappstrukturen i Gazu.  
     Mallen kan utökas i framtiden för att inkludera mer komplexa strukturer, t.ex. sekvenser och shots.
     
    
     Förväntas vara en dict där nycklarna är mappnamn och värdena kan vara tomma eller innehålla ytterligare information.
     
    
     Exempel på mallstruktur:
     project_template.yaml:
     ```
     Incoming: {}
     Reference: {}
     Work: {}
     ```
     
     shot_template.yaml:
     ```
     2D: {}
     3D: {}
     Reference: {}
     Source: {}
     Output: {}
     Deliveries: {}
     ```
        """
    
    config = load_config()
    
    match type:
        case "project":
            file_path = Path(config["pipeline_root"])/"shared"/"templates"/"project_template.yaml"
                
        case "shot":
            file_path = Path(config["pipeline_root"])/"shared"/"templates"/"shot_template.yaml"
                
        case _:
            raise ValueError(f"Okänd malltyp: {type}")
        
    if not Path.is_file(file_path):
        raise FileNotFoundError("Mallfilen hittades inte. Kontrollera sökvägen.")
    
    with open(file_path, "r") as f:
        template = yaml.safe_load(f)

    if not isinstance(template, dict):
        raise ValueError("Mallfilen saknar en giltig struktur. Förväntades vara en dict.")
    
    return template


