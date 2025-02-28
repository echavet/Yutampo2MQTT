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

# Codes ANSI pour les couleurs
class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    RESET = '\033[0m'


# Configuration du logging
logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger("Yutampo_ha_addon")


# Fonction pour créer un message encadré
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



# Afficher le message de démarrage dès le début
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

# Récupération des informations du broker MQTT avec logs de débogage
MQTT_HOST = os.getenv('MQTT_HOST')
LOGGER.debug(f"Valeur de MQTT_HOST: '{MQTT_HOST}'")

MQTT_PORT = os.getenv('MQTT_PORT', 1883)  # Note : valeur par défaut 1883, déjà converti en int plus tard
LOGGER.debug(f"Valeur de MQTT_PORT: '{MQTT_PORT}'")

MQTT_USER = os.getenv('MQTT_USERNAME')
LOGGER.debug(f"Valeur de MQTT_USER: '{MQTT_USER}'")

MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
LOGGER.debug(f"Valeur de MQTT_PASSWORD: '{'*' * len(MQTT_PASSWORD) if MQTT_PASSWORD else 'None'}'")  # Masque le mot de passe

# Vérification des variables
if not all([MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD]):
    LOGGER.error("Les informations du broker MQTT sont incomplètes. Arrêt du programme.")
    exit(1)

# Conversion explicite de MQTT_PORT en int après le log (car os.getenv retourne une string)
MQTT_PORT = int(MQTT_PORT)
LOGGER.debug(f"MQTT_PORT converti en int: {MQTT_PORT}")

# Configuration du client MQTT
mqtt_client = mqtt.Client()
mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        LOGGER.info("Connecté au broker MQTT")
        client.subscribe("yutampo/climate/+/set")
    else:
        LOGGER.error(f"Échec de la connexion au broker MQTT, code de retour : {rc}")

def on_message(client, userdata, msg):
    try:
        LOGGER.info(f"Message reçu sur le topic {msg.topic}: {msg.payload.decode()}")
        # Extraction de l'ID du device depuis le topic
        device_id = msg.topic.split('/')[2]
        new_temp = float(msg.payload.decode())
        
        # Ici vous devriez ajouter la logique pour envoyer la nouvelle température via l'API
        # Par exemple :
        # payload = {"deviceId": device_id, "settingTemperature": new_temp}
        # SESSION.post(f"{BASE_URL}/api/set_temperature", json=payload)
        
        # Pour l'instant, on met juste à jour l'état MQTT
        mqtt_client.publish(f"yutampo/climate/{device_id}/temperature_state", new_temp, retain=True)
    except Exception as e:
        LOGGER.error(f"Erreur lors du traitement du message: {str(e)}")

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Connexion au broker MQTT
mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
mqtt_client.loop_start()

def authenticate():
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
    soup = BeautifulSoup(html, "html.parser")
    token = soup.find("input", {"name": "_csrf"})
    return token["value"] if token else ""

def get_device_status():
    LOGGER.debug("Récupération de l'état des appareils...")
    response = SESSION.get(f"{BASE_URL}/data/elements")
    if response.status_code == 302:
        LOGGER.warning("Session expirée, réauthentification requise.")
        if authenticate():
            response = SESSION.get(f"{BASE_URL}/data/elements")
        else:
            return None
    if response.status_code == 200:
        return response.json()
    LOGGER.error(f"Échec de la requête API. Code HTTP: {response.status_code}")
    return None

def publish_discovery_config(device_id, device_name):
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
        "temp_step": 1,
        "device": {
            "identifiers": [device_id],
            "name": device_name,
            "manufacturer": "Yutampo",
            "model": "RS32"
        }
    }
    mqtt_client.publish(discovery_topic, json.dumps(payload), retain=True)
    LOGGER.info(f"Configuration MQTT Discovery publiée pour l'appareil {device_name}")

def publish_device_state(device_id, temperature, current_temperature, mode="heat"):
    mqtt_client.publish(f"yutampo/climate/{device_id}/temperature_state", temperature, retain=True)
    mqtt_client.publish(f"yutampo/climate/{device_id}/current_temperature", current_temperature, retain=True)
    mqtt_client.publish(f"yutampo/climate/{device_id}/mode", mode, retain=True)
    LOGGER.info(f"État publié pour {device_id}: consigne={temperature}°C, actuel={current_temperature}°C")

def update_data():
    LOGGER.info("Mise à jour des données...")
    device_data = get_device_status()
    if device_data and "data" in device_data and "elements" in device_data["data"]:
        for element in device_data["data"]["elements"]:
            device_id = str(element["deviceId"])
            setting_temp = element["settingTemperature"]
            current_temp = element["currentTemperature"]
            mode = "heat" if element["onOff"] == 1 else "off"
            
            publish_device_state(device_id, setting_temp, current_temp, mode)
    else:
        LOGGER.warning("Aucune donnée valide reçue lors de la mise à jour.")




if __name__ == "__main__":
    if not authenticate():
        LOGGER.error("Impossible de s'authentifier. Arrêt de l'add-on.")
        exit(1)

    # Récupération initiale des données pour découvrir les appareils
    device_data = get_device_status()
    if not device_data or "data" not in device_data or "elements" not in device_data["data"]:
        LOGGER.error("Impossible de récupérer les données initiales des appareils.")
        exit(1)

    # Publication de la configuration pour chaque appareil trouvé
    for element in device_data["data"]["elements"]:
        device_id = str(element["deviceId"])  # Converti en string pour MQTT
        device_name = element["deviceName"]
        publish_discovery_config(device_id, device_name)
        # Publication initiale de l'état
        publish_device_state(device_id, 
                           element["settingTemperature"], 
                           element["currentTemperature"],
                           "heat" if element["onOff"] == 1 else "off")

    # Initialiser le planificateur
    scheduler = BackgroundScheduler()
    scheduler.start()

    # Planifier la tâche de mise à jour
    scheduler.add_job(
        update_data,
        trigger=IntervalTrigger(seconds=SCAN_INTERVAL),
        next_run_time=datetime.now()
    )

    LOGGER.info("Le planificateur est en cours d'exécution. Appuyez sur Ctrl+C pour arrêter.")
    try:
        while True:
            time.sleep(1)  # Plus léger que pass
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        mqtt_client.loop_stop()
        LOGGER.info("Arrêt du programme.")
