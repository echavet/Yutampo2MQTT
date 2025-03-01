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

DEVICES = {}  # Stocke device_id -> {parentId, settingTemperature, currentTemperature, mode}

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
MQTT_HOST = os.getenv('MQTTHOST')
LOGGER.debug(f"Valeur de MQTT_HOST: '{MQTT_HOST}'")

MQTT_PORT = os.getenv('MQTTPORT', 1883)  # Note : valeur par défaut 1883, déjà converti en int plus tard
LOGGER.debug(f"Valeur de MQTT_PORT: '{MQTT_PORT}'")

MQTT_USER = os.getenv('MQTTUSER')
LOGGER.debug(f"Valeur de MQTT_USER: '{MQTT_USER}'")

MQTT_PASSWORD = os.getenv('MQTTPASSWORD')
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
        device_id = msg.topic.split('/')[2]  # Ex. yutampo/climate/4103/set
        new_temp = float(msg.payload.decode())

        if not (30 <= new_temp <= 60):
            LOGGER.warning(f"Température demandée {new_temp} hors plage (30-60°C). Ignorée.")
            return

        if device_id not in DEVICES:
            LOGGER.error(f"Device {device_id} inconnu dans DEVICES.")
            return

        # Récupérer parentId et le dernier état
        parent_id = DEVICES[device_id]["parentId"]
        current_mode = DEVICES[device_id]["mode"]

        # Récupérer le token CSRF actuel
        login_page = SESSION.get(f"{BASE_URL}/login")
        csrf_token = extract_csrf_token(login_page.text)

        # Construire la requête POST
        payload = {
            "indoorId": parent_id,
            "settingTempDHW": new_temp,
            "runStopDHW": 1 if current_mode == "heat" else 0,  # Garde l'état actuel
            "_csrf": csrf_token
            # "id", "updatedOn", "orderStatus" omis car probablement gérés par le serveur
        }
        LOGGER.debug(f"Envoi POST avec payload : {payload}")
        
        response = SESSION.post(f"{BASE_URL}/data/indoor/heat_setting", json=payload)
        
        if response.status_code == 200:
            try:
                resp_json = response.json()
                if resp_json.get("status") == "success":
                    LOGGER.info(f"Température mise à jour pour {device_id} à {new_temp}°C")
                    # Mettre à jour DEVICES et republier
                    DEVICES[device_id]["settingTemperature"] = new_temp
                    publish_device_state(device_id, new_temp, DEVICES[device_id]["currentTemperature"], current_mode)
                else:
                    LOGGER.error(f"Réponse API non réussie : {resp_json}")
            except requests.exceptions.JSONDecodeError:
                LOGGER.error(f"Réponse non JSON : {response.text[:200]}")
        elif response.status_code == 302:
            LOGGER.warning("Session expirée, réauthentification requise.")
            if authenticate():
                response = SESSION.post(f"{BASE_URL}/data/indoor/heat_setting", json=payload)
                if response.status_code == 200 and response.json().get("status") == "success":
                    LOGGER.info(f"Température mise à jour après réauth pour {device_id} à {new_temp}°C")
                    DEVICES[device_id]["settingTemperature"] = new_temp
                    publish_device_state(device_id, new_temp, DEVICES[device_id]["currentTemperature"], current_mode)
                else:
                    LOGGER.error(f"Échec après réauth. Code: {response.status_code}, Réponse: {response.text[:200]}")
            else:
                LOGGER.error("Échec de la réauthentification.")
        else:
            LOGGER.error(f"Échec mise à jour. Code: {response.status_code}, Réponse: {response.text[:200]}")
    except ValueError:
        LOGGER.error(f"Payload invalide : {msg.payload.decode()}. Doit être un nombre.")
    except Exception as e:
        LOGGER.error(f"Erreur dans on_message : {str(e)}")
        

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
    """Récupération des informations sur l'état des équipements."""
    LOGGER.debug("Récupération de l'état des appareils...")
    response = SESSION.get(f"{BASE_URL}/data/elements")
    
    if response.status_code == 302:
        LOGGER.warning("Session expirée, réauthentification requise.")
        if authenticate():
            LOGGER.debug("Réauthentification réussie, nouvelle tentative...")
            response = SESSION.get(f"{BASE_URL}/data/elements")
        else:
            LOGGER.error("Échec de la réauthentification.")
            return None
    
    if response.status_code != 200:
        LOGGER.error(f"Échec de la requête API. Code HTTP: {response.status_code}, Contenu: {response.text[:200]}")
        return None
    
    try:
        device_data = response.json()
        LOGGER.debug("Données récupérées avec succès.")
        return device_data
    except requests.exceptions.JSONDecodeError as e:
        LOGGER.error(f"Erreur de parsing JSON : {str(e)}. Contenu reçu : {response.text[:200]}")
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
    LOGGER.debug(f"Publication MQTT pour {device_id}: mode={mode}, consigne={temperature}°C, actuel={current_temperature}°C")

def update_data():
    LOGGER.info("Mise à jour des données...")
    device_data = get_device_status()
    if device_data and "data" in device_data and "elements" in device_data["data"]:
        for element in device_data["data"]["elements"]:
            device_id = str(element["deviceId"])
            parent_id = element["parentId"]
            setting_temp = element["settingTemperature"]
            current_temp = element["currentTemperature"]
            on_off = element.get("onOff", 0)
            mode = "heat" if on_off == 1 else "off"  # À ajuster si nécessaire
            
            # Mettre à jour les infos
            DEVICES[device_id] = {
                "parentId": parent_id,
                "settingTemperature": setting_temp,
                "currentTemperature": current_temp,
                "mode": mode
            }
            LOGGER.debug(f"Device {device_id} mis à jour : {DEVICES[device_id]}")
            
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
        device_id = str(element["deviceId"])
        parent_id = element["parentId"]
        setting_temp = element["settingTemperature"]
        current_temp = element["currentTemperature"]
        on_off = element.get("onOff", 0)
        mode = "heat" if on_off == 1 else "off"
        
        # Mémoriser les infos
        DEVICES[device_id] = {
            "parentId": parent_id,
            "settingTemperature": setting_temp,
            "currentTemperature": current_temp,
            "mode": mode
        }
        LOGGER.debug(f"Device {device_id} initialisé : {DEVICES[device_id]}")
        
        publish_discovery_config(device_id, element["deviceName"])
        publish_device_state(device_id, setting_temp, current_temp, mode)

    # Initialiser le planificateur
    scheduler = BackgroundScheduler()
    scheduler.start()

    scheduler.add_job(
        update_data,
        trigger=IntervalTrigger(seconds=SCAN_INTERVAL),
        next_run_time=datetime.now()
    )

    LOGGER.info("Le planificateur est en cours d'exécution. Appuyez sur Ctrl+C pour arrêter.")
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        mqtt_client.loop_stop()
        LOGGER.info("Arrêt du programme.")
