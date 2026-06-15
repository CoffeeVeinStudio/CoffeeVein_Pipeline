from .kitsu_client import GazuClient
import gazu


class SequenceManager:
    def __init__(self, client: GazuClient):    
        self.client = client
    
    def create_sequence(self, project: str | dict, sequence_name: str) -> dict:
        """Skapar en ny sekvens i Gazu.

        Args:
            project (str | dict): projektet som sekvensen tillhör.
            sequence_name (str): namnet på sekvensen.

        Returns:
            dict: sekvensinformation om den skapade sekvensen.
        """
        return gazu.shot.new_sequence(project, sequence_name)
    
    def get_sequence(self, sequence_id: str) -> dict:
        """Hämtar information om en specifik sekvens.

        Args:
            sequence_id (str): ID på sekvensen.

        Returns:
            dict: sekvensinformation om den specifika sekvensen.
        """
        return gazu.shot.get_sequence(sequence_id)
    
    def get_sequence_by_name(self, project: str | dict, sequence_name: str) -> dict:
        """Hämtar en sekvens baserat på dess namn.

        Args:
            project (str | dict): projektet som sekvensen tillhör.
            sequence_name (str): namnet på sekvensen.

        Returns:
            dict: sekvensinformation om den specifika sekvensen.
        """
        return gazu.shot.get_sequence_by_name(project, sequence_name)
    
    def list_sequences(self, project_id: str | dict) -> list:
        """Listar alla sekvenser i ett projekt.

        Args:
            project_id (str | dict): projektet som sekvensen tillhör.

        Returns:
            list: en lista med sekvenser.
        """
        return gazu.shot.all_sequences_for_project(project_id)
    
    def update_sequence(self, sequence_id: str | dict, **kwargs) -> dict:
        """Uppdaterar en sekvens.

        Args:
            sequence_id (str | dict): ID på sekvensen.
            **kwargs: Uppdateringsparametrar.

        Returns:
            dict: Den uppdaterade sekvensinformationen.
        """
        return gazu.shot.update_sequence_data(sequence_id, **kwargs)
    
    def delete_sequence(self, sequence_id: str | dict, force: bool = False) -> str:
        """Tar bort en sekvens.
        Om force är True, kommer sekvensen att tas bort även om den innehåller shots.

        Args:
            sequence_id (str | dict): ID på sekvensen.
            force (bool, optional): _description_. Defaults to False.

        Returns:
            str: _description_
        """
        return gazu.shot.remove_sequence(sequence_id, force)
        