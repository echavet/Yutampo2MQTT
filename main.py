# main.py
import logging
from datetime import datetime
from yutampo_addon import YutampoAddon

# Configuration du logging
logging.basicConfig(level=logging.DEBUG)
LOGGER = logging.getLogger("Yutampo_ha_addon")

# Codes ANSI pour les couleurs
class Colors:
    GREEN = '\033[92m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

def log_startup_message():
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"Démarrage de l'addon Yutampo HA - {timestamp}"
    border = "*" * (len(msg) + 4)
    framed_message = (
        f"{Colors.BLUE}{border}{Colors.RESET}\n"
        f"{Colors.BLUE}* {Colors.GREEN}{msg}{Colors.BLUE} *{Colors.RESET}\n"
        f"{Colors.BLUE}{border}{Colors.RESET}"
    )
    LOGGER.info(framed_message)

if __name__ == "__main__":
    log_startup_message()
    addon = YutampoAddon(config_path="/data/options.json")
    addon.start()
