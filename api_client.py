# api_client.py
import requests
from bs4 import BeautifulSoup
from device import Device
import logging
import json


class ApiClient:
    BASE_URL = "https://www.csnetmanager.com"

    def __init__(self, config):
        self.logger = logging.getLogger("Yutampo_ha_addon")
        self.session = requests.Session()
        self.username = config["username"]
        self.password = config["password"]
        self.csrf_token = None

    def authenticate(self):
        self.logger.info("Tentative d'authentification...")
        if not self._fetch_csrf_token():
            self.logger.error("Échec récupération token CSRF.")
            return False

        data = {
            "_csrf": self.csrf_token,
            "username": self.username,
            "password_unsanitized": self.password,
            "password": self.password,
        }

        response = self.session.post(f"{self.BASE_URL}/login", data=data)
        if response.status_code == 200 or response.status_code == 302:
            self.logger.info("Authentification réussie.")
            if response.status_code == 302:
                redirect_url = response.headers.get("Location", f"{self.BASE_URL}/")
                response = self.session.get(redirect_url)
                self.logger.debug(
                    f"Cookies après redirection : {self.session.cookies.get_dict()}"
                )
            return True
        self.logger.error(
            f"Échec de l'authentification. Code HTTP: {response.status_code}"
        )
        return False

    def _fetch_csrf_token(self):
        try:
            login_page = self.session.get(f"{self.BASE_URL}/login")
            if login_page.status_code != 200:
                self.logger.error(
                    f"Échec récupération page login pour CSRF. Code: {login_page.status_code}"
                )
                return False
            self.csrf_token = self._extract_csrf_token(login_page.text)
            if not self.csrf_token:
                self.logger.error("Token CSRF non trouvé dans la page de login.")
                return False
            self.logger.debug(f"Nouveau token CSRF récupéré : {self.csrf_token}")
            return True
        except Exception as e:
            self.logger.error(
                f"Erreur lors de la récupération du CSRF token : {str(e)}"
            )
            return False

    def _extract_csrf_token(self, html):
        soup = BeautifulSoup(html, "html.parser")
        token = soup.find("input", {"name": "_csrf"})
        return token["value"] if token else ""

    def _reset_session_and_authenticate(self):
        """Renouvelle la session et effectue une authentification complète."""
        self.logger.debug("Renouvellement de la session et réauthentification...")
        self.session = requests.Session()
        return self.authenticate()

    def _handle_response(self, response, attempt, max_retries):
        """Vérifie la réponse HTTP et JSON, retourne les données ou None si échec."""
        if response.status_code != 200:
            self.logger.warning(
                f"Code HTTP inattendu: {response.status_code}. Réponse: {response.text[:200]}"
            )
            return None

        content_type = response.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            self.logger.error(
                f"Réponse inattendue (non JSON) : Content-Type={content_type}, Contenu={response.text[:200]}"
            )
            return None

        try:
            data = response.json()
            if not isinstance(data, dict) or "data" not in data:
                self.logger.error("Structure JSON inattendue dans la réponse.")
                return None
            self.logger.debug("Données JSON récupérées avec succès.")
            return data
        except json.JSONDecodeError as e:
            self.logger.error(
                f"Erreur lors du parsing JSON : {str(e)}. Contenu reçu : {response.text[:200]}"
            )
            return None

    def get_devices(self):
        raw_data = self.get_raw_data()
        if not raw_data or "data" not in raw_data or "elements" not in raw_data["data"]:
            return None
        return [
            Device(str(element["deviceId"]), element["deviceName"], element["parentId"])
            for element in raw_data["data"]["elements"]
        ]

    def get_raw_data(self, max_retries=3):
        attempt = 0
        while attempt < max_retries:
            attempt += 1
            self.logger.debug(
                f"Tentative {attempt}/{max_retries} : Récupération de l'état des appareils..."
            )
            try:
                response = self.session.get(f"{self.BASE_URL}/data/elements")
                data = self._handle_response(response, attempt, max_retries)
                if data is not None:
                    return data

                # Si échec, renouveler la session et réauthentifier dès la première erreur
                if not self._reset_session_and_authenticate():
                    self.logger.error("Échec de la réauthentification.")
                    if attempt == max_retries:
                        return None
                    continue

                # Nouvelle tentative après réauthentification
                response = self.session.get(f"{self.BASE_URL}/data/elements")
                data = self._handle_response(response, attempt, max_retries)
                if data is not None:
                    return data

                if attempt == max_retries:
                    self.logger.error("Échec après toutes les tentatives.")
                    return None
            except Exception as e:
                self.logger.error(f"Erreur lors de la requête API : {str(e)}")
                if not self._reset_session_and_authenticate():
                    self.logger.error("Échec de la réauthentification après exception.")
                    if attempt == max_retries:
                        return None
                continue
        return None

    def set_heat_setting(self, indoor_id, run_stop_dhw=None, setting_temp_dhw=None):
        self.logger.info(
            f"Modification de l'état/temp pour indoorId={indoor_id}, runStopDHW={run_stop_dhw}, settingTempDHW={setting_temp_dhw}"
        )

        if not self._fetch_csrf_token():
            self.logger.error("Échec récupération token CSRF avant POST.")
            return False

        payload = {
            "indoorId": str(indoor_id),
            "_csrf": self.csrf_token,
        }
        if setting_temp_dhw is not None:
            payload["settingTempDHW"] = str(int(setting_temp_dhw))
        if run_stop_dhw is not None:
            payload["runStopDHW"] = str(run_stop_dhw)

        headers = {
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0",
            "accept": "*/*",
            "accept-language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest",
            "origin": "https://www.csnetmanager.com",
        }

        try:
            response = self.session.post(
                f"{self.BASE_URL}/data/indoor/heat_setting",
                data=payload,
                headers=headers,
            )
            if response.status_code == 200:
                try:
                    resp_json = response.json()
                    if resp_json.get("status") == "success":
                        self.logger.info("Commande exécutée avec succès.")
                        return True
                    else:
                        self.logger.error(f"Réponse API non réussie : {resp_json}")
                        return False
                except requests.exceptions.JSONDecodeError:
                    self.logger.error(f"Réponse non JSON : {response.text}")
                    return False
            elif response.status_code in (302, 403):
                self.logger.warning(
                    f"Erreur {response.status_code}, réauthentification requise..."
                )
                if (
                    self._reset_session_and_authenticate()
                ):  # Utilisation de la méthode factorisée
                    return self.set_heat_setting(
                        indoor_id, run_stop_dhw, setting_temp_dhw
                    )
                else:
                    self.logger.error("Échec de la réauthentification.")
                    return False
            else:
                self.logger.error(
                    f"Échec mise à jour. Code: {response.status_code}, Réponse: {response.text}"
                )
                return False
        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi de la requête POST : {str(e)}")
            return False
