import pprint 
import sys
from pathlib import Path
PIPELINE_ROOT = Path(__file__).parent.parent
VENDOR_PATH = PIPELINE_ROOT / "shared" / "vendor"

if str(PIPELINE_ROOT)  not in sys.path:
    sys.path.insert(0, str(PIPELINE_ROOT))
if str(VENDOR_PATH)  not in sys.path:
    sys.path.insert(0, str(VENDOR_PATH))


from shared.lib import load_config, load_env, load_template, create_project_structure, create_shot_structure
from backend import GazuClient, ProjectManager, SequenceManager, ShotManager


config = load_config()
env = load_env()

client = GazuClient(config, env)
proman = ProjectManager(client, config)
seqman = SequenceManager(client)
shoman = ShotManager(client)
pipeline_service = PipelineService(config, load_template, ProjectManager, SequenceManager, ShotManager)

project = proman.list_projects()[1]
sequences = seqman.list_sequences(project)[0]


#create_project_structure(project['name'], load_template("project"), config)
for shot in shoman.list_shots_in_project(project):
    print(shot['name'])
#    create_shot_structure(project, sequences, shot['name'], load_template("shot"), config)
#project_name = "TestProject2"
#production_type = "short" #short, featurefilm, tvshow.
#production_style = "commercial"
#
#for project in pm.list_projects():
#        print(project['name'])