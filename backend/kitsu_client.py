
import gazu

from requests.exceptions import ConnectionError, ConnectTimeout
from gazu.exception import AuthFailedException



class GazuClient:
    def __init__(self, config: dict, env: dict):
        self.config = config
        self.env = env
        self.set_gazu_host()
        if not self.is_logged_in():
            self.log_in_gazu()
        
    def set_gazu_host(self) -> None:
        gazu.client.set_host(self.config['kitsu_host'])
    
    def is_logged_in(self):
        try:
            return gazu.user.is_authenticated()
        except ConnectionError:
            return False

    def log_in_gazu(self):
        try:
            gazu.log_in(self.env['KITSU_EMAIL'], self.env['KITSU_PASSWORD'])
            
        except AuthFailedException as e:
            raise AuthFailedException(f"Inloggning misslyckades. Kontrollera dina Kitsu-uppgifter. Fel: {e}")
        except ConnectTimeout as e:
            raise ConnectTimeout(f"Anslutning till Kitsu timeout. Kontrollera att Kitsu-servern är igång och att nätverket fungerar. Fel: {e}")
        except ConnectionError as e:
            raise ConnectionError(f"Kunde inte ansluta till Kitsu. Kontrollera din nätverksanslutning och Kitsu-serverns status. Fel: {e}")

