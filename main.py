# main.py
import subprocess
import logging
from datetime import datetime
from yutampo_addon import YutampoAddon

# Configuration du logging
logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger("Yutampo_ha_addon")


def log_startup_message():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"Démarrage de l'addon Yutampo HA - {timestamp}"
    border = "*" * (len(msg) + 4)
    framed_message = f"\n{border}\n* {msg} *\n{border}"
    # Exécuter bashio::log.info dans un shell avec l'environnement chargé
    command = f"/usr/bin/with-contenv bash -c 'source /etc/bashio/bashio.sh && bashio::log.info \"{framed_message}\"'"
    subprocess.run(command, shell=True, check=True)


if __name__ == "__main__":
    log_startup_message()
    addon = YutampoAddon(config_path="/data/options.json")
    addon.start()
