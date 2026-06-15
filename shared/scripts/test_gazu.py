import sys
sys.path.insert(0, r"D:\CoffeeVeinStudio\Pipeline\shared\vendor")

import pprint
import gazu

gazu.client.set_host("http://192.168.50.119:8012/api")

gazu.log_in("admin@example.com", "mysecretpassword")

projects = gazu.project.all_open_projects()
project = projects[0]  # Tar första projektet, "Test"

shots = gazu.shot.all_shots_for_project(project)
shots = gazu.shot.all_shots_for_project(project)
for shot in shots:
    sequence = gazu.shot.get_sequence(shot["parent_id"])
    #print(shot["name"], sequence["name"])

pprint.pprint(project)