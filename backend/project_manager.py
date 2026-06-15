from .kitsu_client import GazuClient
from shared.lib import folder_manager, utils

import gazu



class ProjectManager:
    def __init__(self, client: GazuClient, config: dict):
        self.client = client
        self.config = config

    def create_project(self, project_name: str, production_type: str = "short", production_style: str = "commercial") -> dict:
        """Skapar ett nytt projekt i Gazu och skapar mappstrukturen baserat på mallen.

        Args:
            project_name (str): _description_
            production_type (str, optional): _description_. Defaults to "short". Alternativ: short, featurefilm, tvshow.
            production_style (str, optional): _description_. Defaults to "commercial". Alternativ: 2d, 3d, 2d3d, ar, vfx, stop-motion, motion-design, archviz, commercial, catalog, immersive, nft, video-game, vr.

        Returns:
            dict: _description_
        """
        
        project = gazu.project.new_project(project_name, production_type=production_type, production_style=production_style)
        folder_manager.create_project_structure(project_name, utils.load_template("project"), self.config)
        return project
    
    def get_project(self, project_id: int) -> dict:
        """Hämtar information om ett specifikt projekt.

        Args:
            project_id (int): _description_

        Returns:
            dict: _description_
        """
        return gazu.project.get_project(project_id)

    def list_projects(self) -> list:
        """Listar alla aktiva projekt.

        Returns:
            list: _description_
        """
        return gazu.project.all_open_projects()


    def update_project(self, project_id: int, **kwargs) -> dict:
        """Uppdaterar ett projekt.

        Args:
            project_id (int): _description_
            **kwargs: _description_

        Returns:
            dict: _description_
        """
        return gazu.project.update_project(project_id, **kwargs)
    
    