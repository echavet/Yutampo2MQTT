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
            LOGGER.error(
                f"Échec récupération page login pour CSRF. Code: {login_page.status_code}"
            )
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
LOGGER.debug(
    f"Valeur de MQTT_PASSWORD: '{'*' * len(MQTT_PASSWORD) if MQTT_PASSWORD else 'None'}'"
)

if not all([MQTT_HOST, MQTT_PORT, MQTT_USER, MQTT_PASSWORD]):
    LOGGER.error(
        "Les informations du broker MQTT sont incomplètes. Arrêt du programme."
    )
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
    """Envoie une requête POST pour contrôler le chauffe-eau."""
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
            "_csrf": CSRF_TOKEN,  # Gardons _csrf pour l'instant, mais testons avec XSRF-TOKEN si nécessaire
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

        response = SESSION.post(
            f"{BASE_URL}/data/indoor/heat_setting", data=payload, headers=headers
        )

        if response.status_code == 200:
            try:
                resp_json = response.json()
                if resp_json.get("status") == "success":
                    LOGGER.info(
                        f"Commande exécutée pour {device_id}: temp={new_temp}°C, mode={new_mode}"
                    )
                    return True
                else:
                    LOGGER.error(f"Réponse API non réussie : {resp_json}")
                    return False
            except requests.exceptions.JSONDecodeError:
                LOGGER.error(f"Réponse non JSON : {response.text}")
                return False
        elif response.status_code in (302, 403):
            LOGGER.warning(
                f"Erreur {response.status_code}, réauthentification requise..."
            )
            if authenticate():
                return send_control_request(device_id, parent_id, new_temp, new_mode)
            else:
                LOGGER.error("Échec de la réauthentification.")
                return False
        else:
            LOGGER.error(
                f"Échec mise à jour. Code: {response.status_code}, Réponse: {response.text}"
            )
            return False
    except Exception as e:
        LOGGER.error(f"Erreur lors de l'envoi de la requête POST : {str(e)}")
        return False


def on_message(client, userdata, msg):
    try:
        LOGGER.info(f"Message reçu sur le topic {msg.topic}: {msg.payload.decode()}")
        device_id = msg.topic.split("/")[2]

        if device_id not in DEVICES:
            LOGGER.error(f"Device {device_id} inconnu dans DEVICES.")
            return

        parent_id = DEVICES[device_id]["parentId"]
        current_mode = DEVICES[device_id]["mode"]
        current_temp = DEVICES[device_id]["settingTemperature"]

        if msg.topic.endswith("/set"):  # Commande de température
            try:
                new_temp = float(msg.payload.decode())
            except ValueError:
                LOGGER.error(
                    f"Payload invalide pour température : {msg.payload.decode()}. Doit être un nombre."
                )
                return
            if not (30 <= new_temp <= 60):
                LOGGER.warning(
                    f"Température demandée {new_temp} hors plage (30-60°C). Ignorée."
                )
                return
            if send_control_request(
                device_id, parent_id, new_temp=new_temp, new_mode=None
            ):
                DEVICES[device_id]["settingTemperature"] = new_temp
                publish_device_state(
                    device_id,
                    new_temp,
                    DEVICES[device_id]["currentTemperature"],
                    current_mode,
                )

        elif msg.topic.endswith("/mode/set"):  # Commande d'état
            new_mode = msg.payload.decode()
            if new_mode not in ("heat", "off"):
                LOGGER.warning(
                    f"Mode invalide : {new_mode}. Doit être 'heat' ou 'off'."
                )
                return
            if send_control_request(
                device_id, parent_id, new_temp=None, new_mode=new_mode
            ):
                DEVICES[device_id]["mode"] = new_mode
                publish_device_state(
                    device_id,
                    current_temp,
                    DEVICES[device_id]["currentTemperature"],
                    new_mode,
                )
    except Exception as e:
        LOGGER.error(f"Erreur dans on_message : {str(e)}")


mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
mqtt_client.loop_start()


def authenticate():
    LOGGER.info("Tentative d'authentification...")
    if not fetch_csrf_token():
        LOGGER.error("Échec récupération token CSRF.")
        return False

    data = {
        "_csrf": CSRF_TOKEN,
        "username": USERNAME,
        "password_unsanitized": PASSWORD,
        "password": PASSWORD,
    }

    response = SESSION.post(f"{BASE_URL}/login", data=data)
    if response.status_code == 200 or response.status_code == 302:
        LOGGER.info("Authentification réussie.")
        # Suivre la redirection pour récupérer le cookie XSRF-TOKEN
        if response.status_code == 302:
            redirect_url = response.headers.get("Location", f"{BASE_URL}/")
            response = SESSION.get(redirect_url)
            LOGGER.debug(f"Cookies après redirection : {SESSION.cookies.get_dict()}")
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

    if response.status_code != 200:
        LOGGER.warning(f"Code HTTP: {response.status_code}")
        LOGGER.debug(f"Réponse: {response.text}")
        LOGGER.debug("Session expirée? Réauthentification...")

        if authenticate():
            response = SESSION.get(f"{BASE_URL}/data/elements")
        else:
            LOGGER.error("Échec de la réauthentification.")
            return None

    if response.status_code != 200:
        LOGGER.error(
            f"Échec de la requête API. Code HTTP: {response.status_code}, Contenu: {response.text[:200]}"
        )
        return None

    try:
        device_data = response.json()
        if not isinstance(device_data, dict) or "data" not in device_data:
            LOGGER.error("Structure JSON inattendue dans la réponse.")
            return None
        LOGGER.debug("Données récupérées avec succès.")
        return device_data
    except requests.exceptions.JSONDecodeError as e:
        LOGGER.error(
            f"Erreur de parsing JSON : {str(e)}. Contenu reçu : {response.text[:200]}"
        )
        return None


def publish_discovery_config(device_id, device_name):
    discovery_topic = f"homeassistant/climate/{device_id}/config"
    payload = {
        "name": device_name,
        "unique_id": device_id,
        "modes": ["off", "heat"],
        "mode_state_topic": f"yutampo/climate/{device_id}/mode",
        "mode_command_topic": f"yutampo/climate/{device_id}/mode/set",
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
            "model": "RS32",
        },
    }
    mqtt_client.publish(discovery_topic, json.dumps(payload), retain=True)
    LOGGER.info(f"Configuration MQTT Discovery publiée pour l'appareil {device_name}")


def publish_device_state(device_id, temperature, current_temperature, mode="heat"):
    mqtt_client.publish(
        f"yutampo/climate/{device_id}/temperature_state", temperature, retain=True
    )
    mqtt_client.publish(
        f"yutampo/climate/{device_id}/current_temperature",
        current_temperature,
        retain=True,
    )
    mqtt_client.publish(f"yutampo/climate/{device_id}/mode", mode, retain=True)
    LOGGER.debug(
        f"Publication MQTT pour {device_id}: mode={mode}, consigne={temperature}°C, actuel={current_temperature}°C"
    )


def update_data():
    LOGGER.info("Mise à jour des données...")
    device_data = get_device_status()
    if device_data and "data" in device_data and "elements" in device_data["data"]:
        for element in device_data["data"]["elements"]:
            device_id = str(element["deviceId"])
            parent_id = element["parentId"]
            setting_temp = element["settingTemperature"]
            current_temp = element["currentTemperature"]
            on_off = element.get("onOff", "N/A")
            mode_field = element.get("mode", "N/A")
            real_mode = element.get("realMode", "N/A")
            operation_status = element.get("operationStatus", "N/A")
            run_stop_dhw = element.get("runStopDHW", "N/A")

            LOGGER.debug(
                f"Device {device_id}: onOff={on_off}, mode={mode_field}, "
                f"realMode={real_mode}, operationStatus={operation_status}, "
                f"runStopDHW={run_stop_dhw}"
            )

            # Utiliser onOff pour déterminer l'état
            mode = "heat" if on_off == 1 else "off"
            LOGGER.debug(f"Mode calculé pour {device_id}: {mode}")

            DEVICES[device_id] = {
                "parentId": parent_id,
                "settingTemperature": setting_temp,
                "currentTemperature": current_temp,
                "mode": mode,
            }
            LOGGER.debug(f"Device {device_id} mis à jour : {DEVICES[device_id]}")

            publish_device_state(device_id, setting_temp, current_temp, mode)
    else:
        LOGGER.warning("Aucune donnée valide reçue lors de la mise à jour.")


if __name__ == "__main__":
    if not authenticate():
        LOGGER.error("Impossible de s'authentifier. Arrêt de l'add-on.")
        exit(1)

    device_data = get_device_status()
    if (
        not device_data
        or "data" not in device_data
        or "elements" not in device_data["data"]
    ):
        LOGGER.error("Impossible de récupérer les données initiales des appareils.")
        exit(1)

    for element in device_data["data"]["elements"]:
        device_id = str(element["deviceId"])
        parent_id = element["parentId"]
        setting_temp = element["settingTemperature"]
        current_temp = element["currentTemperature"]
        on_off = element.get("onOff", "N/A")
        mode_field = element.get("mode", "N/A")
        real_mode = element.get("realMode", "N/A")
        operation_status = element.get("operationStatus", "N/A")
        run_stop_dhw = element.get("runStopDHW", "N/A")

        LOGGER.debug(
            f"Device {device_id}: onOff={on_off}, mode={mode_field}, "
            f"realMode={real_mode}, operationStatus={operation_status}, "
            f"runStopDHW={run_stop_dhw}"
        )

        mode = "heat" if on_off == 1 else "off"
        LOGGER.debug(f"Mode calculé pour {device_id}: {mode}")

        DEVICES[device_id] = {
            "parentId": parent_id,
            "settingTemperature": setting_temp,
            "currentTemperature": current_temp,
            "mode": mode,
        }
        LOGGER.debug(f"Device {device_id} initialisé : {DEVICES[device_id]}")

        publish_discovery_config(device_id, element["deviceName"])
        publish_device_state(device_id, setting_temp, current_temp, mode)

    scheduler = BackgroundScheduler()
    scheduler.start()

    scheduler.add_job(
        update_data,
        trigger=IntervalTrigger(seconds=SCAN_INTERVAL),
        next_run_time=datetime.now(),
    )

    LOGGER.info(
        "Le planificateur est en cours d'exécution. Appuyez sur Ctrl+C pour arrêter."
    )
    try:
        while True:
            time.sleep(1)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        mqtt_client.loop_stop()
        LOGGER.info("Arrêt du programme.")
