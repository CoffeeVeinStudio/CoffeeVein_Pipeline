from .kitsu_client import GazuClient
import gazu

class ShotManager:
    def __init__(self, client: GazuClient):
        #self.client = client
        pass
    
    def create_shot(self, project: str | dict, sequence: str | dict, shot_name: str) -> dict:
        """Skapar en ny shot i Gazu.

        Args:
            project (str | dict): projektet som shoten ska tillhöra.
            sequence (str | dict): sekvensen som shoten ska tillhöra.
            shot_name (str): namnet på shoten.

        Returns:
            dict: shotinformation om den skapade shoten.
        """
        return gazu.shot.new_shot(project, sequence, shot_name)
    
    def get_shot(self, shot_id: str) -> dict:
        """Hämtar en shot baserat på dess ID.

        Args:
            shot_id (str): ID på shoten.

        Returns:
            dict: shotinformation om den specifika shoten.
        """
        return gazu.shot.get_shot(shot_id)

    def get_shot_by_name(self, sequence: str | dict, shot_name: str) -> dict:
        """Hämtar information om en specifik shot.

        Args:
            sequence (str | dict): sekvensen som shoten tillhör.
            shot_name (str): namnet på shoten.

        Returns:
            dict: shotinformation om den specifika shoten.
        """
        return gazu.shot.get_shot_by_name(sequence, shot_name)
    
    def list_shots_in_sequence(self, sequence: str | dict) -> list:
        """Listar alla shots i en sekvens.

        Args:
            sequence (str | dict): sekvensen som shoten tillhör.

        Returns:
            list: en lista med shots.
        """
        return gazu.shot.all_shots_for_sequence(sequence)

    def list_shots_in_project(self, project: str | dict) -> list:
        """Listar alla shots i ett projekt.

        Args:
            project (str | dict): projektet som shoten tillhör.

        Returns:
            list: en lista med shots.
        """
        return gazu.shot.all_shots_for_project(project)
    
    def update_shot(self, shot_id: str | dict, **kwargs) -> dict:
        """Uppdaterar en shot.

        Args:
            shot_id (str | dict): ID på shoten.
            **kwargs: Uppdateringsparametrar.

        Returns:
            dict: shotinformation om den uppdaterade shoten.
        """
        return gazu.shot.update_shot_data(shot_id, data=kwargs)

        
