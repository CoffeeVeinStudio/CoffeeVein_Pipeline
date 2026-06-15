from shared.lib import folder_manager, utils

class PipelineService:
    def __init__(self, config, project_manager, sequence_manager, shot_manager):
        self.config = config
        self.project_manager = project_manager
        self.sequence_manager = sequence_manager
        self.shot_manager = shot_manager

    def create_project(self, project_name: str, production_type: str = "short", production_style: str = "commercial"):
        # Ladda projektmallen
        template = utils.load_template("project")
        # Skapa projektet i Gazu
        project = self.project_manager.create_project(project_name, production_type, production_style)
        # Skapa mappstrukturen baserat på mallen
        folder_manager.create_project_structure(project_name, template, self.config)
        return project

    def create_shot(self, project_name, sequence, shot_name):
        # Ladda shotmallen
        template = utils.load_template("shot")
        # Skapa shot-strukturen
        folder_manager.create_shot_structure(project_name, sequence, shot_name, template, self.config)