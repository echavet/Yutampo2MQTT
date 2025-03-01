import requests
import time
import json
import os
import logging
import paho.mqtt.client as mqtt
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
from bs4 import BeautifulSoup

DEVICES = {}
CSRF_TOKEN = None

# Codes ANSI pour les couleurs
class Colors:
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    RESET = "\033[0m"

# Configuration du logging
logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger("Yutampo_ha_addon")

def fetch_csrf_token():
    """Récupère un nouveau token CSRF depuis la page de login."""
    global CSRF_TOKEN
    try:
        login_page = SESSION.get(f"{BASE_URL}/login")
        if login_page.status_code != 200:
            LOGGER.error(f"Échec récupération page login pour CSRF. Code: {login_page.status_code}")
            return False
        CSRF_TOKEN = extract_csrf_token(login_page.text)
        if not CSRF_TOKEN:
            LOGGER.error("Token CSRF non trouvé dans la page de login.")
            return False
        LOGGER.debug(f"Nouveau token CSRF récupéré : {CSRF_TOKEN}")
        return True
    except Exception as e:
        LOGGER.error(f"Erreur lors de la récupération du CSRF token : {str(e)}")
        return False

def log_startup_message():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"Démarrage de l'addon Yutampo HA - {timestamp}"
    border = "*" * (len(msg) + 4)
    framed_message = (
        f"\n{Colors.BLUE}{border}{Colors.RESET}\n"
        f"{Colors.BLUE}* {Colors.GREEN}{msg}{Colors.BLUE} *{Colors.RESET}\n"
        f"{Colors.BLUE}{border}{Colors.RESET}"
    )
    LOGGER.info(framed_message)

log_startup_message()

# Lire la configuration de Home Assistant
CONFIG_PATH = "/data/options.json"
if not os.path.exists(CONFIG_PATH):
    LOGGER.error("Fichier de configuration introuvable !")
    exit(1)

with open(CONFIG_PATH, "r") as config_file:
    config = json.load(config_file)

USERNAME = config.get("username")
PASSWORD = config.get("password")
SCAN_INTERVAL = config.get("scan_interval", 300)

BASE_URL = "https://www.csnetmanager.com"
SESSION = requests.Session()

# Récupération des informations du broker MQTT
MQTT_HOST = os.getenv("MQTTHOST")
LOGGER.debug(f"Valeur de MQTT_HOST: '{MQTT_HOST}'")

MQTT_PORT = os.getenv("MQTTPORT", 1883)
LOGGER.debug(f"Valeur de MQTT_PORT: '{MQTT_PORT}'")

MQTT_USER = os.getenv("MQTTUSER")
LOGGER.debug(f"Valeur de MQTT_USER: '{MQTT_USER}'")

MQTT_PASSWORD = os.getenv("MQTTPASSWORD")
LOGGER.debug(f"Valeur de MQTT_PASSWORD: '{'*' * len(MQTT_PASSWORD) if MQTT_PASSWORD else 'None'}'")

if not all([MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD]):
    LOGGER.error("Les informations du broker MQTT sont incomplètes. Arrêt du programme.")
    exit(1)

MQTT_PORT = int(MQTT_PORT)
LOGGER.debug(f"MQTT_PORT converti en int: {MQTT_PORT}")

mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        LOGGER.info("Connecté au broker MQTT")
        client.subscribe("yutampo/climate/+/set")
        client.subscribe("yutampo/climate/+/mode/set")
    else:
        LOGGER.error(f"Échec de la connexion au broker MQTT, code de retour : {rc}")

def send_control_request(device_id, parent_id, new_temp=None, new_mode=None):
    try:
        if not CSRF_TOKEN:
            LOGGER.warning("Token CSRF non disponible, tentative de récupération...")
            if not authenticate():
                LOGGER.error("Échec récupération token CSRF via authentification.")
                return False

        if not fetch_csrf_token():
            LOGGER.error("Échec récupération token CSRF avant POST.")
            return False

        current_mode = DEVICES[device_id]["mode"]
        current_temp = DEVICES[device_id]["settingTemperature"]

        if new_temp is None:
            new_temp = current_temp
        if new_mode is None:
            new_mode = current_mode

        # Payload aligné avec l'application officielle
        payload = {
            "indoorId": str(parent_id),
            "settingTempDHW": str(new_temp),
            "_csrf": CSRF_TOKEN,
        }
        # Inclure runStopDHW uniquement pour les commandes ON/OFF
        if new_mode != current_mode:
            payload["runStopDHW"] = "1" if new_mode == "heat" else "0"

        LOGGER.debug(f"Envoi POST URLEncoded avec payload : {payload}")
        LOGGER.debug(f"Cookies actuels : {SESSION.cookies.get_dict()}")

        headers = {
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:135.0) Gecko/20100101 Firefox/135.0",
            "accept": "*/*",
            "accept-language": "fr,fr-FR;q=0.8,en-US;q=0.5,en;q=0.3",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-requested-with": "XMLHttpRequest",
            "origin": "https://www.csnetmanager.com",
        }

        response = SESSION.post(f"{BASE_URL}/data/indoor/heat_setting", data=payload, headers=headers)

        if response.status_code == 200:
            try:
                resp_json = response.json()
                if resp_json.get("status") == "success":
                    LOGGER.info(f"Commande exécutée pour {device_id}: temp={new_temp}°C, mode={new_mode}")
                    return True
                else:
                    LOGGER.error(f"Réponse API non réussie : {resp_json}")
                    return False
            except requests.exceptions.JSONDecodeError:
                LOGGER.error(f"Réponse non JSON : {response.text}")
                return False
        elif response.status_code in (302, 403):
            LOGGER.warning(f"Erreur {response.status_code}, réauthentification requise...")
            if authenticate():
                return send_control_request(device_id, parent_id, new_temp, new_mode)
            else:
                LOGGER.error("Échec de la réauthentification.")
                return False
        else:
            LOGGER.error(f"Échec mise à jour. Code: {response.status_code}, Réponse: {response.text}")
            return False
    except Exception as e:
        LOGGER.error(f"Erreur lors de l'envoi de la requête POST : {str(e)}")
        return False

def on_message(client,
