import requests
import time
import json
import os
import logging
import paho.mqtt.client as mqtt
from bs4 import BeautifulSoup

# Configuration du logging
logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger("Yutampo_ha_addon")

# Lire la configuration de Home Assistant
CONFIG_PATH = "/data/options.json"  # Fichier JSON généré par HA
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

# Récupération des informations du broker MQTT depuis les variables d'environnement
MQTT_HOST = os.getenv('MQTT_HOST')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_USER = os.getenv('MQTT_USERNAME')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')

# Vérification que toutes les informations sont disponibles
if not all([MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD]):
    LOGGER.error("Les informations du broker MQTT sont incomplètes.")
    exit(1)

# Configuration du client MQTT
mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        LOGGER.info("Connecté au broker MQTT")
        # S'abonner aux topics de commande
        client.subscribe("yutampo/climate/+/set")
    else:
        LOGGER.error(f"Échec de la connexion au broker MQTT, code de retour : {rc}")

mqtt_client.on_connect = on_connect

def on_message(client, userdata, msg):
    LOGGER.info(f"Message reçu sur le topic {msg.topic}: {msg.payload.decode()}")
    # Traiter les commandes reçues ici
    # Par exemple, extraire l'ID de l'appareil et la nouvelle consigne de température
    # et appeler l'API Yutampo pour mettre à jour la température de consigne

mqtt_client.on_message = on_message

# Connexion au broker MQTT
mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
mqtt_client.loop_start()

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
    soup = BeautifulSoup(html, "html.parser")
    token = soup.find("input", {"name": "_csrf"})
    return token["value"] if token else ""

def get_device_status():
    """Récupération des informations sur l'état des équipements."""
    LOGGER.debug("Récupération de l'état des appareils...")
    response = SESSION.get(f"{BASE_URL}/data/elements")
    if response.status_code == 302:
        LOGGER.warning("Session expirée, réauthentification requise.")
        authenticate()
        return None
    if response.status_code == 200:
        return response.json()
    LOGGER.error(f"Échec de la requête API. Code HTTP: {response.status_code}")
    return None

def publish_discovery_config(device_id, device_name):
    """Publication de la configuration MQTT Discovery pour Home Assistant."""
    discovery_topic = f"homeassistant/climate/{device_id}/config"
    payload = {
        "name": device_name,
        "unique_id": device_id,
        "modes": ["off", "heat"],
        "current_temperature_topic": f"yutampo/climate/{device_id}/current_temperature",
        "temperature_command_topic": f"yutampo/climate/{device_id}/set",
        "temperature_state_topic": f"yutampo/climate/{device_id}/temperature_state",
        "min_temp": 30,
        "max_temp": 60,
        "temp_step": 0.5,
        "device": {
            "identifiers": [device_id],
            "name": device_name,
            "manufacturer": "Yutampo",
            "model": "RS32"
        }
    }
    mqtt_client.publish(discovery_topic, json.dumps(payload), retain=True)
    LOGGER.info(f"Configuration MQTT Discovery publiée pour l'appareil {device_name}")

def publish_device_state(device_id, temperature, current_temperature):
    """Publication de l'état de l'appareil."""
    mqtt_client.publish(f"yutampo/climate/{device_id}/temperature_state", temperature, retain=True)
    mqtt_client.publish(f"yutampo/climate/{device_id}/current_temperature", current_temperature, retain=True)
    LOGGER.info(f"État publié pour l'appareil {device_id}: consigne={temperature}°C, température actuelle={current_temperature}°C")

def main_loop():
    """Boucle principale pour récupérer les données périodiquement."""
    if not authenticate():
        LOGGER.error("Impossible de s'authentifier. Arrêt de l'add-on.")
        exit(1)

    device_id = "yutampo_rs32_1"
    device_name = "Yutampo Chauffe-Eau"

    # Publier la configuration MQTT Discovery au démarrage
    publish_discovery_config(device_id, device_name)

    while True:
        LOGGER.info("Mise à jour des données...")
        device_data = get_device_status()
        if device_data:
            # Extraire les informations nécessaires de device_data
            # Par exemple :
            # current_temperature
::contentReference[oaicite:0]{index=0}
 
