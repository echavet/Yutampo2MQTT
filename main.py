import requests
import time
import json
import logging
import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL
from threading import Timer

# Configuration du logging
logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger("Yutampo_ha_addon")

# Définition du schéma de configuration
CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=300): cv.positive_int,
}, extra=vol.ALLOW_EXTRA)

BASE_URL = "https://www.csnetmanager.com"
SESSION = requests.Session()
USERNAME = None
PASSWORD = None

def authenticate():
    """Authentification et création de session."""
    LOGGER.info("Tentative d'authentification...")
    login_page = SESSION.get(f"{BASE_URL}/login")
    csrf_token = extract_csrf_token(login_page.text)
    
    data = {
        "_csrf": csrf_token,
        "username": USERNAME,
        "password_unsanitized": PASSWORD,
        "password": PASSWORD
    }
    
    response = SESSION.post(f"{BASE_URL}/login", data=data)
    if response.status_code == 200:
        LOGGER.info("Authentification réussie.")
        return True
    LOGGER.error(f"Échec de l'authentification. Code HTTP: {response.status_code}")
    return False

def extract_csrf_token(html):
    """Extraction du token CSRF du formulaire de connexion."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    token = soup.find("input", {"name": "_csrf"})
    if token:
        return token["value"]
    LOGGER.warning("Impossible d'extraire le token CSRF.")
    return ""

def handle_api_response(response):
    """Gère la réponse API et réauthentifie si nécessaire."""
    if response.status_code == 302:
        LOGGER.warning("Session expirée, réauthentification requise.")
        authenticate()
        return None
    if response.status_code == 200:
        return response.json()
    LOGGER.error(f"Échec de la requête API. Code HTTP: {response.status_code}")
    return None

def get_device_status():
    """Récupération des informations sur l'état des équipements."""
    LOGGER.debug("Récupération de l'état des appareils...")
    response = SESSION.get(f"{BASE_URL}/data/elements")
    return handle_api_response(response)

def send_command(indoor_id, setting_temp, run_stop=None):
    """Envoi d'une commande pour modifier la température du chauffe-eau."""
    LOGGER.info(f"Envoi d'une commande pour indoorId {indoor_id}, temp: {setting_temp}, run_stop: {run_stop}")
    csrf_token = extract_csrf_token(SESSION.get(f"{BASE_URL}/login").text)
    data = {
        "indoorId": indoor_id,
        "settingTempDHW": setting_temp,
        "_csrf": csrf_token
    }
    if run_stop is not None:
        data["runStopDHW"] = run_stop
    
    response = SESSION.post(f"{BASE_URL}/data/indoor/heat_setting", json=data)
    return handle_api_response(response)

class HitachiWaterHeater(Entity):
    """Entité Home Assistant pour surveiller le chauffe-eau Hitachi."""
    def __init__(self, hass, name, device_id, indoor_id, scan_interval):
        self.hass = hass
        self._name = name
        self._device_id = device_id
        self._indoor_id = indoor_id
        self._state = None
        self._scan_interval = scan_interval
        LOGGER.info(f"Création de l'entité {self._name} (device_id: {self._device_id}, indoor_id: {self._indoor_id})")
        self.schedule_update()
    
    @property
    def name(self):
        return self._name
    
    @property
    def state(self):
        return self._state
    
    def update(self):
        LOGGER.debug(f"Mise à jour de l'entité {self._name}...")
        data = get_device_status()
        if data:
            for device in data["data"]["elements"]:
                if device["deviceId"] == self._device_id:
                    self._state = device["currentTemperature"]
                    LOGGER.info(f"État mis à jour pour {self._name}: {self._state}°C")
                    break
        self.schedule_update()
    
    def set_temperature(self, temperature):
        LOGGER.info(f"Modification de la température de {self._name} à {temperature}°C")
        send_command(self._indoor_id, temperature)
    
    def turn_on(self):
        LOGGER.info(f"Activation de {self._name}")
        send_command(self._indoor_id, self._state, run_stop=1)
    
    def turn_off(self):
        LOGGER.info(f"Désactivation de {self._name}")
        send_command(self._indoor_id, self._state, run_stop=0)
    
    def schedule_update(self):
        LOGGER.debug(f"Programmation de la prochaine mise à jour pour {self._name} dans {self._scan_interval} secondes.")
        Timer(self._scan_interval, self.update).start()
