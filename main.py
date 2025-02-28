import requests
import time
import json
import os
import logging

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

def main_loop():
    """Boucle principale pour récupérer les données périodiquement."""
    if not authenticate():
        LOGGER.error("Impossible de s'authentifier. Arrêt de l'add-on.")
        exit(1)

    while True:
        LOGGER.info("Mise à jour des données...")
        get_device_status()
        time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main_loop()
