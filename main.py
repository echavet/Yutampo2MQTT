# main.py
import os
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
    # Utilisation de os.system pour exécuter la commande bashio
    os.system(f"bashio::log.info '{framed_message}'")


if __name__ == "__main__":
    log_startup_message()
    addon = YutampoAddon(config_path="/data/options.json")
    addon.start()
