# api_client.py
import requests
from bs4 import BeautifulSoup
from device import Device
import logging

class ApiClient:
    BASE_URL = "https://www.csnetmanager.com"

    def __init__(self, config):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.session = requests.Session()
        self.username = config["username"]
        self.password = config["password"]
        self.csrf_token = None  # Pour stocker le token CSRF après authentification

    def authenticate(self):
        self.logger.info("Tentative d'authentification...")
        login_page = self.session.get(f"{self.BASE_URL}/login")
        self.csrf_token = self._extract_csrf_token(login_page.text)

        data = {
            "_csrf": self.csrf_token,
            "username": self.username,
            "password_unsanitized": self.password,
            "password": self.password
        }

        response = self.session.post(f"{self.BASE_URL}/login", data=data)
        if response.status_code == 200:
            self.logger.info("Authentification réussie.")
            return True
        self.logger.error(f"Échec de l'authentification. Code HTTP: {response.status_code}")
        return False

    def _extract_csrf_token(self, html):
        soup = BeautifulSoup(html, "html.parser")
        token = soup.find("input", {"name": "_csrf"})
        return token["value"] if token else ""

    def get_devices(self):
        raw_data = self.get_raw_data()
        if not raw_data or "data" not in raw_data or "elements" not in raw_data["data"]:
            return None
        return [Device(str(element["deviceId"]), element["deviceName"]) for element in raw_data["data"]["elements"]]

    def get_raw_data(self):
        self.logger.debug("Récupération de l'état des appareils...")
        response = self.session.get(f"{self.BASE_URL}/data/elements")
        if response.status_code == 302:
            self.logger.warning("Session expirée, réauthentification requise.")
            if self.authenticate():
                response = self.session.get(f"{self.BASE_URL}/data/elements")
            else:
                return None
        if response.status_code != 200:
            self.logger.error(f"Échec de la requête API. Code HTTP: {response.status_code}")
            return None
        try:
            return response.json()
        except Exception as e:
            self.logger.error(f"Erreur lors du parsing JSON: {str(e)}")
            return None

    def set_heat_setting(self, indoor_id, run_stop_dhw):
        """Envoie une commande pour modifier l'état du chauffe-eau (on/off)."""
        self.logger.info(f"Modification de l'état du chauffe-eau pour indoorId={indoor_id}, runStopDHW={run_stop_dhw}")
        
        # Vérifier que le token CSRF est disponible
        if not self.csrf_token:
            self.logger.warning("Token CSRF non disponible, tentative de réauthentification...")
            if not self.authenticate():
                self.logger.error("Échec de la réauthentification pour obtenir le token CSRF.")
                return False

        data = {
            "indoorId": indoor_id,
            "runStopDHW": run_stop_dhw,  # 0 pour off, 1 pour on
            "_csrf": self.csrf_token
        }

        try:
            response = self.session.post(f"{self.BASE_URL}/data/indoor/heat_setting", data=data)
            if response.status_code == 200 or response.status_code == 302:  # 302 peut indiquer une redirection après succès
                self.logger.info("Commande d'état envoyée avec succès.")
                return True
            else:
                self.logger.error(f"Échec de la commande d'état. Code HTTP: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi de la commande d'état: {str(e)}")
            return False
